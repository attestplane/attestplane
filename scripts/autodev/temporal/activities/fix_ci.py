# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
"""fix_ci_activity for autodev-train pipeline."""

import asyncio
import json
import os
import re
import shutil
import time as _time
from pathlib import Path

from temporalio import activity

from .. import db
from ..llm_router import is_quota_exhausted, is_rate_limit_error, router
from ._base import (
    BOT_EMAIL,
    BOT_NAME,
    GFW_PROXY,
    MAIN_REPO,
    REPO_SLUG,
    _arun,
    _arun_git_fetch,
    _agh,
    _build_subprocess_env,
)


# ── activity: fix_ci ──────────────────────────────────────────────────────────

@activity.defn(name="fix_ci")
async def fix_ci_activity(issue_number: int, pr_number: int) -> dict:
    """Wait for CI on a freshly-created PR; if it fails, run Qwen to fix the errors.

    Returns {"ci_passed": bool, "fixed": bool}.
    Called once between create_pr and review_pr. merge_pr_activity re-checks CI
    independently before the final squash-merge, so a False/"not fixed" here only
    means we skip the fast-path — the PR stays open for review.
    """
    # C3 fix: on retry (attempt > 1), a previous attempt already ran the LLM and
    # committed a fix.  Re-running LLM would push another commit on top.
    # Instead, just snapshot the current CI state and return.
    _attempt_num = activity.info().attempt
    if _attempt_num > 1:
        activity.logger.info(
            "fix_ci retry attempt=%d for PR #%d — polling CI only, skipping LLM re-run",
            _attempt_num, pr_number,
        )
        # Check both mergeStateStatus AND individual check completions to avoid the ~30s
        # window after a push where GitHub still reports the previous commit's CLEAN state.
        # Only return ci_passed=True when all checks are COMPLETED with no failures. (H4 fix)
        try:
            _retry_info = json.loads(await _agh(
                ["pr", "view", str(pr_number), "--repo", REPO_SLUG,
                 "--json", "mergeStateStatus,statusCheckRollup"]
            ))
            if _retry_info.get("mergeStateStatus") == "CLEAN":
                _retry_checks = _retry_info.get("statusCheckRollup", [])
                _all_done = all(c.get("status") == "COMPLETED" for c in _retry_checks)
                # CANCELLED/TIMED_OUT checks are also non-passing: treat as failures. (L2 fix)
                _any_failed = any(
                    c.get("conclusion") in ("FAILURE", "CANCELLED", "TIMED_OUT")
                    for c in _retry_checks
                )
                # All-SKIPPED means CI didn't actually run (path-filtered); don't report as passed. (M3 fix)
                _all_skipped = bool(_retry_checks) and all(
                    c.get("conclusion") == "SKIPPED" for c in _retry_checks
                )
                if _retry_checks and _all_done and not _any_failed and not _all_skipped:
                    return {"ci_passed": True, "fixed": False}
        except RuntimeError:
            pass
        return {"ci_passed": False, "fixed": False}

    branch = (await _agh(
        ["pr", "view", str(pr_number), "--repo", REPO_SLUG, "--json", "headRefName", "--jq", ".headRefName"]
    )).strip()

    # ── wait for CI to complete (up to 20 minutes) ─────────────────────────────
    ci_wait_deadline = _time.monotonic() + 1200
    _stuck_queued_deadline: float | None = None  # M3: detect runners that never pick up jobs
    checks: list = []
    while True:
        activity.heartbeat({"phase": "wait_ci", "pr": pr_number})
        pr_info = json.loads(await _agh(
            ["pr", "view", str(pr_number), "--repo", REPO_SLUG,
             "--json", "mergeStateStatus,statusCheckRollup"]
        ))
        merge_state = pr_info.get("mergeStateStatus", "UNKNOWN")
        checks = pr_info.get("statusCheckRollup", [])

        if not checks:
            # Check deadline BEFORE sleeping so a permanently check-free PR doesn't loop forever. (H3 fix)
            if _time.monotonic() > ci_wait_deadline:
                activity.logger.warning(
                    "No CI checks registered for PR #%d after deadline — skipping fix", pr_number
                )
                return {"ci_passed": False, "fixed": False}
            await asyncio.sleep(15)
            continue

        pending = [c for c in checks if c.get("status") not in ("COMPLETED",)]
        _in_progress = [c for c in pending if c.get("status") == "IN_PROGRESS"]

        # M3: track how long checks have been stuck in QUEUED with no runner pickup.
        if _in_progress:
            _stuck_queued_deadline = None  # runner picked up work — reset stuck detector
        elif pending and _stuck_queued_deadline is None:
            _stuck_queued_deadline = _time.monotonic() + 300  # 5 min without any IN_PROGRESS

        if pending and _stuck_queued_deadline and _time.monotonic() > _stuck_queued_deadline:
            activity.logger.warning(
                "PR #%d: %d check(s) stuck in QUEUED for >5min with no IN_PROGRESS — runner offline?",
                pr_number, len(pending),
            )
            return {"ci_passed": False, "fixed": False}

        if merge_state == "CLEAN" and not pending:
            activity.logger.info("CI passed for PR #%d (CLEAN) — no fix needed", pr_number)
            return {"ci_passed": True, "fixed": False}

        if not pending:
            activity.logger.info("CI failed for PR #%d (state=%s) — will attempt Qwen fix", pr_number, merge_state)
            break

        if _time.monotonic() > ci_wait_deadline:
            if pending:
                activity.logger.warning(
                    "Timed out waiting for CI on PR #%d with %d check(s) still pending — skipping LLM fix",
                    pr_number, len(pending),
                )
                return {"ci_passed": False, "fixed": False}
            activity.logger.warning("Timed out waiting for CI on PR #%d — attempting fix anyway", pr_number)
            break

        await asyncio.sleep(30)

    # ── extract CI error logs ──────────────────────────────────────────────────
    failed_checks = [c for c in checks if c.get("conclusion") == "FAILURE"]
    # C3 fix: CANCELLED/TIMED_OUT/NEUTRAL checks have no actionable log for Qwen.
    if not failed_checks:
        _other = {c.get("conclusion") for c in checks if c.get("conclusion") not in ("SUCCESS", "SKIPPED")}
        activity.logger.warning(
            "PR #%d: no FAILURE checks (other conclusions: %s) — no actionable log for Qwen fix",
            pr_number, ", ".join(str(x) for x in _other) or "none",
        )
        return {"ci_passed": False, "fixed": False}

    error_summary = ""
    seen_run_ids: set[str] = set()
    for check in failed_checks[:5]:
        # Heartbeat before each log fetch — each call can block up to 90s; heartbeat_timeout=3min. (C1 fix)
        activity.heartbeat({"phase": "fetch_ci_log", "check": check.get("name", "")[:50]})
        check_name = check.get("name", "unknown")
        details_url = check.get("detailsUrl", "")
        m = re.search(r"/actions/runs/(\d+)", details_url)
        run_id = m.group(1) if m else ""
        if not run_id or run_id in seen_run_ids:
            continue
        seen_run_ids.add(run_id)
        try:
            # Single 90s call — stays within the 3-min heartbeat budget (heartbeat just above). (C1 fix)
            raw_log = await _agh(
                ["run", "view", run_id, "--log-failed", "--repo", REPO_SLUG],
                timeout=90,
            )
            cleaned: list[str] = []
            for raw_ln in raw_log.splitlines():
                parts = raw_ln.split("\t", 2)
                cln = parts[2] if len(parts) == 3 else raw_ln
                ts_idx = cln.find("Z ")
                cln = cln[ts_idx + 2:] if ts_idx != -1 else cln
                cleaned.append(cln)
            kept = [
                ln for ln in cleaned
                if any(kw in ln.lower() for kw in
                       ["error", "failed", "e402", "assert", "found", "✗",
                        "ruff", "mypy", "biome", "markdownlint", "lychee", "typeerror",
                        "importerror", "attributeerror", "raise ", 'file "', ">       ",
                        "errors", "short test summary", "pytest", "assertionerror",
                        "##[error]", "allowlist", "manifest", "unused", "type: ignore"])
            ]
            error_summary += f"\n### {check_name}\n" + "\n".join(kept[:80]) + "\n"
        except RuntimeError:
            error_summary += f"\n### {check_name}\n(log unavailable)\n"

    if not error_summary.strip():
        activity.logger.warning("No extractable CI errors for PR #%d — skipping Qwen fix", pr_number)
        return {"ci_passed": False, "fixed": False}

    # ── run Qwen on a fresh worktree of the branch ───────────────────────────
    main = str(MAIN_REPO)
    worktree = f"/tmp/aw-cifix-{issue_number}"
    try:
        await _arun_git_fetch("origin", branch, cwd=main)  # M5: retry on index.lock contention
        if Path(worktree).exists():
            try:
                await _arun(["git", "worktree", "remove", "--force", worktree], cwd=main)
            except RuntimeError:
                pass
            shutil.rmtree(worktree, ignore_errors=True)
        await _arun(["git", "worktree", "add", "-B", branch, worktree, f"origin/{branch}"], cwd=main)

        fix_prompt = (
            f"CI checks failed on PR branch '{branch}'. Fix ONLY the failing CI errors listed below.\n"
            "Rules:\n"
            "1. Do NOT change any business logic.\n"
            "2. Fix linting (ruff E402: move module docstring BEFORE `from __future__ import annotations`), "
            "import ordering (biome: sort named imports alphabetically), "
            "test assertions that need updating to match the new implementation, "
            "and markdown lint (MD012 extra blank lines, MD052 bracket labels → escape with backslash).\n"
            "3. Do NOT touch .github/workflows/, CHANGELOG.md, or REUSE/SPDX headers.\n"
            f"\n## CI Error Log\n{error_summary[:4000]}\n"
        )

        _providers = router.providers_for("fix_ci")
        _last_err: Exception | None = None
        for _p in _providers:
            activity.logger.info(
                "fix_ci_activity attempt=%d provider=%s model=%s blacklist=%s",
                activity.info().attempt, _p.name, _p.model, router.blacklist_state(),
            )
            try:
                _fix_env = _build_subprocess_env(
                    OPENAI_API_KEY=_p.api_key,
                    https_proxy=GFW_PROXY,
                    http_proxy=GFW_PROXY,
                    **({"CODEX_HOME": os.environ["CODEX_HOME"]} if "CODEX_HOME" in os.environ else {}),
                )
                # Qwen runs up to 30 min — heartbeat every 60s in background to satisfy
                # heartbeat_timeout=3min. (C1 fix)
                activity.heartbeat({"phase": "qwen_fix_starting", "provider": _p.name})

                async def _hb_loop(_pr: int = pr_number) -> None:
                    while True:
                        await asyncio.sleep(60)
                        try:
                            activity.heartbeat({"phase": "qwen_fix", "pr": _pr})
                        except Exception:
                            return

                _hb_task = asyncio.create_task(_hb_loop())
                try:
                    await _arun(
                        [
                            "qwen",
                            "-m", _p.model,
                            "--auth-type", "openai",
                            "--openai-base-url", _p.base_url,
                            "--approval-mode", "yolo",
                            fix_prompt,
                        ],
                        cwd=worktree,
                        env=_fix_env,
                        timeout=1800,
                    )
                finally:
                    _hb_task.cancel()
                    try:
                        await _hb_task
                    except asyncio.CancelledError:
                        pass
                _last_err = None
                break
            except RuntimeError as _e:
                if is_rate_limit_error(str(_e)):
                    activity.logger.warning("fix_ci provider %s rate-limited, blacklisting", _p.name)
                    router.blacklist(_p.name, until_midnight=is_quota_exhausted(str(_e)))
                    _last_err = _e
                    continue
                raise
        if _last_err is not None:
            raise _last_err

        # Run ruff on all changed .py files in the worktree (not just sdk/python). (H13 fix)
        changed_py_post_fix = [
            f for f in (await _arun(["git", "diff", "HEAD", "--name-only"], cwd=worktree)).splitlines()
            if f.endswith(".py")
        ]
        if changed_py_post_fix:
            for ruff_cmd in [
                ["python3.11", "-m", "ruff", "check", "--fix", *changed_py_post_fix],
                ["python3.11", "-m", "ruff", "format", *changed_py_post_fix],
            ]:
                try:
                    await _arun(ruff_cmd, cwd=worktree)
                except RuntimeError as e:
                    activity.logger.warning("ruff post-fix: %s", str(e)[:200])

        porcelain = await _arun(["git", "status", "--porcelain"], cwd=worktree)
        if porcelain.strip():
            await _arun(["git", "add", "-A"], cwd=worktree)
            await _arun(
                ["git", "commit", "--signoff", "-m",
                 f"fix(ci): auto-fix CI errors for issue #{issue_number}"],
                cwd=worktree,
                env={
                    **os.environ,
                    "GIT_AUTHOR_NAME": BOT_NAME,
                    "GIT_AUTHOR_EMAIL": BOT_EMAIL,
                    "GIT_COMMITTER_NAME": BOT_NAME,
                    "GIT_COMMITTER_EMAIL": BOT_EMAIL,
                },
            )
            await _arun(["git", "push", "origin", branch, "--force-with-lease"], cwd=worktree)
            activity.logger.info("CI fix committed and pushed for PR #%d", pr_number)
            db.log_event(issue_number, "fix_ci", "completed", f"pr={pr_number} fixed=True")
            return {"ci_passed": False, "fixed": True}
        else:
            activity.logger.warning("Qwen produced no changes for CI fix on PR #%d", pr_number)
            db.log_event(issue_number, "fix_ci", "completed", f"pr={pr_number} fixed=False")
            return {"ci_passed": False, "fixed": False}

    except Exception as exc:
        activity.logger.error("fix_ci failed for PR #%d: %s", pr_number, exc)
        db.log_event(issue_number, "fix_ci", "failed", str(exc)[:300])
        if is_rate_limit_error(str(exc)):
            return {"ci_passed": False, "fixed": False}
        raise
    finally:
        try:
            await _arun(["git", "worktree", "remove", "--force", worktree], cwd=main)
        except Exception:
            pass
