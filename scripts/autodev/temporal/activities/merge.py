# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
"""merge_pr_activity for autodev-train pipeline."""

import asyncio
import contextlib
import json
import os
import shutil
import time as _time

from temporalio import activity

from .. import db
from ._base import (
    BOT_EMAIL,
    BOT_NAME,
    MAIN_REPO,
    REPO_SLUG,
    _arun,
    _agh,
    _is_critical_check,
    _log,
    _run,
)


def _do_rebase(pr_number: int, worktree: str, main: str, branch: str,
               wf_id: str = "", run_id: str = "") -> bool:
    """Fetch latest main, set up a fresh worktree, rebase branch onto main, and push.

    Runs in a thread via asyncio.to_thread — uses module-level _log instead of
    activity.logger because ContextVar may not propagate into threads. (HIGH-6 fix)
    wf_id/run_id are included in log messages for correlation when N PRs rebase in parallel. (M4 fix)

    Returns True if the file tree changed after rebase (caller posts a PR warning comment).
    Raises RuntimeError on any git failure; caller should run `git rebase --abort` and retry.
    """
    # Retry on .git/index.lock — concurrent implement/fix_ci activities may race on MAIN_REPO. (M5 fix)
    for _fi in range(3):
        try:
            _run(["git", "fetch", "origin", "main", branch], cwd=main)
            break
        except RuntimeError as _fe:
            if "index.lock" in str(_fe).lower() and _fi < 2:
                _time.sleep(5 * (_fi + 1))
            else:
                raise
    # Capture expected remote SHA immediately after fetch — prevents --force-with-lease from
    # clobbering a concurrent push that lands between our fetch and push. (H6 fix)
    try:
        _expected_sha = _run(
            ["git", "rev-parse", f"refs/remotes/origin/{branch}"], cwd=main
        ).strip()
    except RuntimeError:
        _expected_sha = ""
    # Prune stale worktree metadata before (re-)creating the worktree. (HIGH worktree fix)
    try:
        _run(["git", "worktree", "prune"], cwd=main)
    except RuntimeError:
        pass
    try:
        _run(["git", "worktree", "remove", "--force", worktree], cwd=main)
    except RuntimeError:
        pass
    shutil.rmtree(worktree, ignore_errors=True)
    _run(["git", "worktree", "add", "-B", branch, worktree, f"origin/{branch}"], cwd=main)

    pre_rebase_tree = _run(["git", "rev-parse", "HEAD^{tree}"], cwd=worktree)
    _run(["git", "rebase", "origin/main"], cwd=worktree, env={
        **os.environ,
        "GIT_AUTHOR_NAME": BOT_NAME, "GIT_AUTHOR_EMAIL": BOT_EMAIL,
        "GIT_COMMITTER_NAME": BOT_NAME, "GIT_COMMITTER_EMAIL": BOT_EMAIL,
    })
    post_rebase_tree = _run(["git", "rev-parse", "HEAD^{tree}"], cwd=worktree)
    tree_changed = pre_rebase_tree != post_rebase_tree
    if tree_changed:
        _log.warning(
            "PR #%d [wf=%s run=%s]: rebase changed file tree (%s → %s) — review was on pre-rebase diff",
            pr_number, wf_id[:12], run_id[:8], pre_rebase_tree[:8], post_rebase_tree[:8],
        )
    # Push with force-with-lease; if rejected (concurrent push), caller will retry.
    _push_lease = (
        f"--force-with-lease=refs/heads/{branch}:{_expected_sha}"
        if _expected_sha else "--force-with-lease"
    )
    _run(["git", "push", "origin", branch, _push_lease], cwd=worktree)
    return tree_changed


@contextlib.asynccontextmanager
async def _merge_lock_async(workflow_id: str, run_id: str, pr_number: int = 0,
                            poll: int = 15, timeout: int = 600):
    """Async merge lock: yields when the SQLite merge lock is acquired.

    Uses asyncio.sleep so the event loop is never blocked while waiting.
    acquire/release are offloaded to thread so SQLite I/O doesn't block the loop.
    Timeout 600s (was 1200s): leaves 900s for rebase+post-rebase CI+merge within the
    45-minute merge_pr activity budget. (H5 fix)

    M1 known limitation: the lock is held for the entire rebase + post-rebase CI wait +
    squash-merge sequence, which can span several minutes under slow CI. This serializes
    all PR merges globally. A future improvement would be to release after rebase and
    re-acquire just before `gh pr merge` to reduce contention.
    """
    deadline = _time.monotonic() + timeout
    acquired = await asyncio.to_thread(db.acquire_merge_lock, workflow_id, run_id, pr_number)
    while not acquired:
        if _time.monotonic() > deadline:
            raise RuntimeError(f"merge lock timeout after {timeout}s (pr={pr_number})")
        activity.heartbeat({"phase": "wait_lock", "pr": pr_number})
        await asyncio.sleep(poll)
        acquired = await asyncio.to_thread(db.acquire_merge_lock, workflow_id, run_id, pr_number)
    try:
        yield
    finally:
        await asyncio.to_thread(db.release_merge_lock, workflow_id, run_id)


@activity.defn(name="merge_pr")
async def merge_pr_activity(issue_number: int, pr_number: int) -> dict:
    """Squash-merge the PR. Waits for CI (via mergeStateStatus), then rebases and merges."""
    try:
        return await _merge_pr_impl(issue_number, pr_number)
    except Exception as exc:
        # Log the error but do NOT set stage="failed" — Temporal will retry via _retry_5.
        # On retry, _merge_pr_impl checks pr_state=="MERGED" for idempotency. (M4 fix)
        try:
            db.log_event(issue_number, "merge", "error", f"merge_pr unexpected: {str(exc)[:300]}")
        except Exception:
            pass
        raise


async def _merge_pr_impl(issue_number: int, pr_number: int) -> dict:
    # M5 fix: gh may fail if the PR was closed/deleted between scheduling and execution.
    # Fall back to the conventional branch name so the caller can still report the error cleanly.
    try:
        branch = (await _agh(
            ["pr", "view", str(pr_number), "--repo", REPO_SLUG, "--json", "headRefName", "--jq", ".headRefName"]
        )).strip()
    except RuntimeError:
        branch = f"autodev/issue-{issue_number}"

    # Idempotency guard: PR may have been merged in a previous attempt. (H5 fix)
    try:
        pr_state = (await _agh([
            "pr", "view", str(pr_number), "--repo", REPO_SLUG,
            "--json", "state", "--jq", ".state",
        ])).strip()
        if pr_state.upper() == "MERGED":
            db.upsert_run(issue_number, stage="merged", error=None)
            db.log_event(issue_number, "merge", "already_merged", f"pr={pr_number}")
            activity.logger.info("PR #%d already merged — syncing DB and returning", pr_number)
            return {"merged": True, "skipped": True}
    except RuntimeError:
        pass

    activity.logger.info("Waiting for CI on PR #%d ...", pr_number)
    ci_deadline = _time.monotonic() + 900
    checks: list = []
    while True:
        activity.heartbeat({"phase": "wait_ci", "pr": pr_number})
        pr_info = json.loads(await _agh(
            ["pr", "view", str(pr_number), "--repo", REPO_SLUG,
             "--json", "mergeable,mergeStateStatus,statusCheckRollup"]
        ))
        merge_state = pr_info.get("mergeStateStatus", "UNKNOWN")
        mergeable = pr_info.get("mergeable", "UNKNOWN")
        checks = pr_info.get("statusCheckRollup", [])

        if merge_state == "CLEAN":
            if not checks:
                # GitHub reports CLEAN before any checks register (~30s delay after push). (H4 fix)
                await asyncio.sleep(15)
                continue
            activity.logger.info("CI passed for PR #%d (CLEAN)", pr_number)
            break
        if merge_state == "UNSTABLE":
            critical_failures = [
                c for c in checks
                if c.get("conclusion") == "FAILURE" and _is_critical_check(c.get("name", ""))
            ]
            if critical_failures:
                names = ", ".join(c.get("name", "?") for c in critical_failures[:3])
                activity.logger.error(
                    "CI FAILED for PR #%d (UNSTABLE, critical failures: %s) — closing PR",
                    pr_number, names,
                )
                try:
                    await _agh(["pr", "close", str(pr_number), "--repo", REPO_SLUG,
                                "--comment",
                                f"Closed by autodev-train: CI critical checks failed ({names}). Fix and reopen."])
                except RuntimeError:
                    pass
                db.upsert_run(issue_number, stage="failed",
                              error=f"CI UNSTABLE critical failures: {names}")
                db.log_event(issue_number, "merge", "ci_failed", f"pr={pr_number} reason=UNSTABLE_CRITICAL")
                return {"merged": False, "reason": "ci_unstable_critical"}
            activity.logger.info(
                "CI UNSTABLE for PR #%d but only cosmetic failures — proceeding to merge", pr_number
            )
            break
        if merge_state == "BLOCKED":
            pending = [c for c in checks if c.get("status") not in ("COMPLETED",)]
            failed = [c for c in checks if c.get("conclusion") == "FAILURE"]
            if not pending and failed:
                # All checks done and some failed (e.g., required check failed).
                activity.logger.error(
                    "CI FAILED for PR #%d (BLOCKED, all checks done) — closing PR", pr_number
                )
                try:
                    await _agh(["pr", "close", str(pr_number), "--repo", REPO_SLUG,
                                "--comment", "Closed by autodev-train: required CI checks failed (BLOCKED). Fix linting/tests and reopen."])
                except RuntimeError:
                    pass
                try:
                    await _agh(["issue", "close", str(issue_number), "--repo", REPO_SLUG,
                                "--comment", f"Closed: PR #{pr_number} failed required CI checks. Re-open to retry."])
                    await _agh(["issue", "edit", str(issue_number), "--repo", REPO_SLUG,
                                "--add-label", "autodev-failed"])
                except RuntimeError:
                    pass
                db.upsert_run(issue_number, stage="failed", error="CI BLOCKED: required checks failed")
                db.log_event(issue_number, "merge", "ci_failed", f"pr={pr_number} reason=BLOCKED")
                return {"merged": False, "reason": "ci_blocked"}
            # BLOCKED with pending checks or branch-out-of-date: keep waiting.
            # Explicit continue prevents fall-through to the CONFLICTING check which would
            # break out of the CI-wait loop prematurely if mergeable=="CONFLICTING" at the
            # same time as BLOCKED+pending. (M3 fix)
            await asyncio.sleep(30)
            continue
        if mergeable == "CONFLICTING":
            activity.logger.info("PR #%d has merge conflict — will attempt rebase", pr_number)
            break
        if _time.monotonic() > ci_deadline:
            if merge_state == "BLOCKED":
                activity.logger.error("CI timeout for PR #%d (BLOCKED) — closing PR", pr_number)
                try:
                    await _agh(["pr", "close", str(pr_number), "--repo", REPO_SLUG,
                                "--comment", "Closed by autodev-train: CI timed out in BLOCKED state."])
                except RuntimeError:
                    pass
                db.upsert_run(issue_number, stage="failed", error="CI timeout in BLOCKED state")
                db.log_event(issue_number, "merge", "ci_timeout_blocked", f"pr={pr_number}")
                return {"merged": False, "reason": "ci_timeout_blocked"}
            elif mergeable == "CONFLICTING":
                activity.logger.warning("CI timeout for PR #%d (CONFLICTING) — attempting rebase", pr_number)
                break
            elif merge_state == "UNKNOWN":
                activity.logger.error("CI timeout for PR #%d (UNKNOWN state) — closing PR", pr_number)
                try:
                    await _agh(["pr", "close", str(pr_number), "--repo", REPO_SLUG,
                                "--comment", "Closed by autodev-train: CI timed out in unknown state."])
                except RuntimeError:
                    pass
                db.upsert_run(issue_number, stage="failed", error="CI timeout in UNKNOWN state")
                return {"merged": False, "reason": "ci_timeout_unknown"}
            else:
                activity.logger.warning(
                    "CI timeout for PR #%d (state=%s) — proceeding to merge", pr_number, merge_state
                )
                break
        await asyncio.sleep(30)

    worktree = f"/tmp/aw-merge-{issue_number}"
    main = str(MAIN_REPO)
    info = activity.info()
    wf_id = info.workflow_id
    run_id = info.workflow_run_id

    rebase_ok = False
    tree_changed = False
    _last_rebase_err = ""  # M2 fix: capture last rebase error for DB error field
    async with _merge_lock_async(wf_id, run_id, pr_number=pr_number):
        # Re-check PR state AND refresh branch inside the lock — branch could theoretically
        # change during a long lock-wait if the PR was force-pushed externally. (M2/H5 fix)
        try:
            _pr_inner = json.loads(await _agh([
                "pr", "view", str(pr_number), "--repo", REPO_SLUG,
                "--json", "state,headRefName",
            ]))
            if _pr_inner.get("state", "").upper() == "MERGED":
                db.upsert_run(issue_number, stage="merged", error=None)
                db.log_event(issue_number, "merge", "already_merged_at_lock", f"pr={pr_number}")
                activity.logger.info("PR #%d merged between CI wait and lock — syncing DB", pr_number)
                return {"merged": True, "skipped": True}
            branch = _pr_inner.get("headRefName", branch)
        except RuntimeError:
            pass

        # Skip rebase if branch already contains the latest origin/main — happens when a
        # prior Temporal retry succeeded at rebase but failed during post-rebase CI wait. (M4 fix)
        try:
            _mb = (await asyncio.to_thread(
                _run, ["git", "merge-base", f"origin/{branch}", "origin/main"], cwd=main
            )).strip()
            _mt = (await asyncio.to_thread(
                _run, ["git", "rev-parse", "origin/main"], cwd=main
            )).strip()
            if _mb == _mt:
                activity.logger.info(
                    "PR #%d branch already at origin/main tip — skipping rebase [wf=%s]",
                    pr_number, wf_id[:12],
                )
                rebase_ok = True
        except RuntimeError:
            pass  # cannot determine merge-base; proceed with normal rebase

        for _attempt in range(2):
            if rebase_ok:
                break
            try:
                tree_changed = await asyncio.to_thread(_do_rebase, pr_number, worktree, main, branch, wf_id, run_id)
                rebase_ok = True
                break
            except Exception as rebase_err:
                _last_rebase_err = str(rebase_err).strip()[:300]  # C2 fix: catch all exceptions so lock is always released
                # git rebase --abort is a subprocess — offload to thread. (H1 fix)
                try:
                    await asyncio.to_thread(_run, ["git", "rebase", "--abort"], cwd=worktree)
                except RuntimeError:
                    pass
                if _attempt == 0:
                    activity.logger.warning(
                        "rebase attempt 1 failed for PR #%d — retrying once: %s",
                        pr_number, str(rebase_err)[:120],
                    )
                    await asyncio.sleep(30)
                else:
                    activity.logger.error(
                        "rebase FAILED for PR #%d (true conflict) — closing PR and issue: %s",
                        pr_number, str(rebase_err)[:200],
                    )

        # Single cleanup after both attempts — not inside the loop (C3 fix).
        try:
            await asyncio.to_thread(
                _run, ["git", "worktree", "remove", "--force", worktree], cwd=main
            )
        except Exception:
            pass

        if not rebase_ok:
            try:
                await _agh(["pr", "close", str(pr_number), "--repo", REPO_SLUG,
                            "--comment",
                            "Closed by autodev-train: rebase onto main failed due to merge conflicts."])
            except RuntimeError:
                pass
            # HIGH-7 fix: close the issue too so it doesn't silently stall on merge_conflict.
            try:
                await _agh(["issue", "close", str(issue_number), "--repo", REPO_SLUG,
                            "--comment",
                            f"Closed: autodev PR #{pr_number} could not be rebased onto main. "
                            "Re-open this issue to retry implementation from a fresh branch."])
                await _agh(["issue", "edit", str(issue_number), "--repo", REPO_SLUG,
                            "--add-label", "autodev-failed"])
            except RuntimeError:
                pass
            db.upsert_run(issue_number, stage="merge_conflict",
                          error=f"rebase conflict: {_last_rebase_err}" if _last_rebase_err
                          else "rebase conflict: branch diverged from main")
            db.log_event(issue_number, "merge", "conflict", f"pr={pr_number}")
            return {"merged": False, "reason": "conflict"}

        # Post a warning comment if the rebase changed the file tree (C4 note: tree_changed
        # is returned by _do_rebase; GitHub API call must stay on the event loop).
        if tree_changed:
            try:
                await _agh(["pr", "comment", str(pr_number), "--repo", REPO_SLUG, "--body",
                            "⚠️ **Rebase changed file tree** — squash commit may differ from what was reviewed."])
            except RuntimeError:
                pass

        # Wait for CI to re-run on the rebased commit before merging. (C4 fix)
        # Default 300s; override via AUTODEV_POST_REBASE_TIMEOUT for slow CI runners. (L4 fix)
        _post_rebase_deadline = _time.monotonic() + int(
            os.environ.get("AUTODEV_POST_REBASE_TIMEOUT", "300")
        )
        while True:
            activity.heartbeat({"phase": "wait_ci_post_rebase", "pr": pr_number})
            _post_state = json.loads(await _agh(
                ["pr", "view", str(pr_number), "--repo", REPO_SLUG,
                 "--json", "mergeStateStatus,statusCheckRollup"]  # H4 fix: also fetch checks
            ))
            _post_merge_state = _post_state.get("mergeStateStatus", "UNKNOWN")
            _post_checks = _post_state.get("statusCheckRollup", [])
            if _post_merge_state == "CLEAN" and _post_checks:
                activity.logger.info("CI CLEAN after rebase for PR #%d — proceeding to merge", pr_number)
                break
            if _post_merge_state == "CLEAN" and not _post_checks:
                # No checks registered yet — wait for GitHub to enqueue runners. (H4 fix)
                await asyncio.sleep(20)
                continue
            if _post_merge_state == "BLOCKED":
                activity.logger.error("CI BLOCKED after rebase for PR #%d — not merging", pr_number)
                db.upsert_run(issue_number, stage="failed", error="CI BLOCKED after rebase")
                db.log_event(issue_number, "merge", "ci_blocked_post_rebase", f"pr={pr_number}")
                return {"merged": False, "reason": "ci_blocked_post_rebase"}
            if _time.monotonic() > _post_rebase_deadline:
                # Do NOT merge on timeout — the rebased commit's CI hasn't validated the tree.
                # Temporal will retry merge_pr_activity, which re-enters this wait loop. (C3 fix)
                activity.logger.error(
                    "Post-rebase CI timeout for PR #%d (state=%s) — not merging; Temporal will retry",
                    pr_number, _post_merge_state,
                )
                return {"merged": False, "reason": "ci_timeout_post_rebase"}
            await asyncio.sleep(20)

        # Verify we still own the merge lock before the point of no return. (H4 fix)
        if not await asyncio.to_thread(db.verify_merge_lock, wf_id, run_id):
            activity.logger.error(
                "Lost merge lock for PR #%d before squash-merge — aborting to avoid split-brain",
                pr_number,
            )
            db.log_event(issue_number, "merge", "lost_lock_pre_merge", f"pr={pr_number}")
            return {"merged": False, "reason": "lost_lock_pre_merge"}

        try:
            await _agh(["pr", "merge", str(pr_number), "--repo", REPO_SLUG,
                        "--squash", "--delete-branch",
                        "--subject",
                        f"feat: merge autodev PR #{pr_number} for issue #{issue_number} [autodev]",
                        "--body",
                        f"Automated squash-merge by autodev-train.\n\nCloses #{issue_number}"])
        except RuntimeError as _merge_err:
            # GitHub rejects the merge if another worker merged concurrently (TOCTOU window
            # between verify_merge_lock and this call). Re-check before propagating. (H5 fix)
            try:
                _post = json.loads(await _agh([
                    "pr", "view", str(pr_number), "--repo", REPO_SLUG, "--json", "state"
                ]))
                if _post.get("state", "").upper() == "MERGED":
                    activity.logger.info(
                        "PR #%d already merged (concurrent worker) — treating as success", pr_number
                    )
                else:
                    raise _merge_err
            except RuntimeError:
                raise _merge_err

    db.upsert_run(issue_number, stage="merged", error=None)
    db.log_event(issue_number, "merge", "completed", f"pr={pr_number}")
    return {"merged": True}
