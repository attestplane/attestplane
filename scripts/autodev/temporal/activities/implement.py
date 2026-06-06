# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
"""implement_activity and create_pr_activity for autodev-train pipeline."""

import asyncio
import os
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
    _log,
    _purge_whitespace_only_changes,
)


# ── activity: implement ────────────────────────────────────────────────────────

@activity.defn(name="implement")
async def implement_activity(
    issue_number: int,
    issue_title: str,
    issue_body: str,
) -> dict:
    """Checkout worktree, run qwen (DeepSeek), commit & push. Idempotent."""
    run = db.get_run(issue_number)
    # no_changes: Qwen found nothing to do. Return has_changes=False so the
    # workflow short-circuits without creating a PR. (M3 fix)
    if run and run["stage"] == "no_changes":
        activity.logger.info("issue #%d previously produced no changes, skipping", issue_number)
        return {"branch": run.get("branch") or f"autodev/issue-{issue_number}", "has_changes": False, "skipped": True}
    if run and run["stage"] in ("implemented", "pr_created", "reviewing", "approved", "merged"):
        activity.logger.info("issue #%d already implemented, skipping", issue_number)
        return {"branch": run.get("branch") or f"autodev/issue-{issue_number}", "has_changes": True, "skipped": True}

    branch = f"autodev/issue-{issue_number}"

    # merge_conflict: merge step failed; delete the stale branch and re-implement fresh.
    # Always delete the remote branch (idempotent if already deleted by merge failure handler)
    # so that the retry-attempt skip logic (ls-remote check below) sees no existing branch
    # and proceeds with a clean implementation instead of reusing stale code. (C2 fix)
    if run and run.get("stage") == "merge_conflict":
        try:
            await _arun(["git", "push", "origin", "--delete", branch], cwd=str(MAIN_REPO))
            activity.logger.info("issue #%d merge_conflict — deleted stale remote branch %s", issue_number, branch)
        except RuntimeError:
            pass
        db.clear_run_for_retry(issue_number)  # M2 fix: clear stale SHA/PR/branch alongside stage reset
        db.upsert_run(issue_number, stage="pending")

    # If previous attempt ended in a true failure, delete the stale branch.
    elif run and run.get("stage") == "failed":
        activity.logger.info("issue #%d previously failed — purging stale branch to re-implement", issue_number)
        # Guard: if an open PR exists (e.g. a human pushed after the bot failure), skip delete
        # to preserve reviewer work. The issue will remain in a failed state until manual triage. (H8 fix)
        _branch_safe_to_delete = True
        try:
            _remote_heads = (await _arun(
                ["git", "ls-remote", "--heads", "origin", branch], cwd=str(MAIN_REPO)
            )).strip()
            if _remote_heads:
                _open_pr = (await _agh([
                    "pr", "list", "--repo", REPO_SLUG, "--head", branch, "--state", "open",
                    "--json", "number", "--jq", ".[0].number // empty",
                ])).strip()
                if _open_pr:
                    activity.logger.warning(
                        "issue #%d: open PR #%s on branch %s — skipping delete to preserve reviewer work",
                        issue_number, _open_pr, branch,
                    )
                    _branch_safe_to_delete = False
        except RuntimeError:
            pass
        if _branch_safe_to_delete:
            try:
                await _arun(["git", "push", "origin", "--delete", branch], cwd=str(MAIN_REPO))
            except RuntimeError:
                pass
            db.clear_run_for_retry(issue_number)
            db.upsert_run(issue_number, stage="pending")

    run = db.get_run(issue_number)

    # On retry: if the branch already exists on remote AND its HEAD SHA matches what
    # we recorded in DB (impl_commit_sha), skip Qwen re-run. (C3 fix)
    attempt = activity.info().attempt
    if attempt > 1:
        try:
            ls_out = await _arun(["git", "ls-remote", "--heads", "origin", branch],
                                 cwd=str(MAIN_REPO))
            if ls_out.strip():
                remote_sha = ls_out.split()[0] if ls_out.strip() else ""
                recorded_sha = (run or {}).get("impl_commit_sha", "")
                if recorded_sha and remote_sha and remote_sha == recorded_sha:
                    activity.logger.info(
                        "Retry attempt %d issue #%d — branch SHA %s matches DB, skipping",
                        attempt, issue_number, remote_sha[:12],
                    )
                    return {"branch": branch, "has_changes": True, "skipped": True}
                if remote_sha and not recorded_sha:
                    # Verify the remote tip was authored by our bot before accepting it.
                    # If a foreign actor pushed to the branch between attempts, we re-implement. (H2 fix)
                    try:
                        _remote_author = (await _arun(
                            ["git", "log", "-1", "--format=%ae", f"origin/{branch}"],
                            cwd=str(MAIN_REPO),
                        )).strip()
                        if _remote_author == BOT_EMAIL:
                            # Also verify the branch is still based on current main;
                            # if main advanced, re-implement to avoid merging stale work. (H2 fix)
                            try:
                                _mb = (await _arun(
                                    ["git", "merge-base", f"origin/{branch}", "origin/main"],
                                    cwd=str(MAIN_REPO),
                                )).strip()
                                _mt = (await _arun(
                                    ["git", "rev-parse", "origin/main"],
                                    cwd=str(MAIN_REPO),
                                )).strip()
                                if _mb != _mt:
                                    activity.logger.info(
                                        "Retry attempt %d issue #%d — branch behind main, re-implementing",
                                        attempt, issue_number,
                                    )
                                    # Fall through to Qwen re-implementation
                                else:
                                    activity.logger.info(
                                        "Retry attempt %d issue #%d — bot author + at main tip, skipping",
                                        attempt, issue_number,
                                    )
                                    return {"branch": branch, "has_changes": True, "skipped": True}
                            except RuntimeError:
                                # Can't check merge-base — skip conservatively (author already verified)
                                activity.logger.info(
                                    "Retry attempt %d issue #%d — bot author verified, skipping (merge-base unavailable)",
                                    attempt, issue_number,
                                )
                                return {"branch": branch, "has_changes": True, "skipped": True}
                        else:
                            activity.logger.warning(
                                "Retry attempt %d issue #%d — remote branch author %s ≠ BOT_EMAIL, re-implementing",
                                attempt, issue_number, _remote_author[:60],
                            )
                    except RuntimeError:
                        pass
                if remote_sha and recorded_sha and remote_sha != recorded_sha:
                    activity.logger.warning(
                        "Retry attempt %d issue #%d — remote SHA %s ≠ DB SHA %s, re-implementing",
                        attempt, issue_number, remote_sha[:12], recorded_sha[:12],
                    )
        except RuntimeError:
            pass

    worktree = f"/tmp/aw-impl-{issue_number}"
    main = str(MAIN_REPO)

    db.upsert_run(issue_number, stage="implementing", branch=branch)
    db.log_event(issue_number, "implement", "started")

    impl_succeeded = False
    try:
        await _arun_git_fetch("origin", "main", cwd=main)  # M5: retry on index.lock contention

        try:
            await _arun(["git", "worktree", "remove", "--force", worktree], cwd=main)
        except RuntimeError:
            pass
        shutil.rmtree(worktree, ignore_errors=True)
        await _arun(["git", "worktree", "add", "-B", branch, worktree, "origin/main"], cwd=main)

        # Sanitize issue body: truncate and escape the XML-like close tag to prevent
        # injected content from escaping the <task> block and overriding system instructions.
        # (M-inject fix)
        _safe_body = issue_body[:2000].replace("</task>", "[/task]")
        _safe_title = issue_title[:200]

        prompt = (
            f"按照 AGENTS.md 和项目规范实现以下任务。\n\n"
            f"<task>\n任务标题：{_safe_title}\n\n"
            f"任务描述：\n{_safe_body}\n</task>\n\n"
            "实施要求（严格遵守）：\n"
            "1. 严格按照 AGENTS.md 中的规范和约束执行\n"
            "2. 新建文件必须在文件头部添加 REUSE 合规头\n"
            "3. 不得修改 .github/workflows/ 目录下的任何文件\n"
            "4. 不得执行 git push、git tag、git merge、npm publish、twine upload\n"
            "5. 不得修改 CHANGELOG.md\n"
            "6. 只修改实现任务所需的最小文件集\n"
            "7. 严禁对整个仓库运行 ruff format .、black .、isort . 等批量格式化命令\n"
            "   只在新建或修改的具体文件上运行格式化\n"
            "8. 最小化 diff：不要重构与任务无关的代码，不要重命名无关变量或调整无关缩进\n"
            "9. 修改完成后，在提交前必须先运行验证命令并修复所有错误：\n"
            "   cd sdk/python && python3.11 -m pytest tests/ -q --tb=short 2>&1 | tail -20\n"
            "   python3.11 -m ruff check sdk/python/ && python3.11 -m mypy sdk/python/src/ --ignore-missing-imports\n"
            "   如有失败，继续修复直到通过，再执行 git add。\n"
            "10. 若验证命令持续失败超过 3 次，停止并输出 'VERIFICATION_FAILED: <原因>'。\n"
        )

        _impl_providers = router.providers_for("implement")
        _impl_last_err: Exception | None = None
        for _p in _impl_providers:
            activity.logger.info(
                "implement_activity attempt=%d provider=%s model=%s",
                activity.info().attempt, _p.name, _p.model,
            )
            try:
                # Use _build_subprocess_env to pass GIT_*/SSH essentials without leaking
                # all worker API keys (DEEPSEEK, GH_TOKEN, etc.) to qwen. (H1 fix)
                _qwen_env = _build_subprocess_env(
                    OPENAI_API_KEY=_p.api_key,
                    https_proxy=GFW_PROXY,
                    http_proxy=GFW_PROXY,
                    **({"CODEX_HOME": os.environ["CODEX_HOME"]} if "CODEX_HOME" in os.environ else {}),
                )
                await _arun(
                    [
                        "qwen",
                        "-m", _p.model,
                        "--auth-type", "openai",
                        "--openai-base-url", _p.base_url,
                        "--approval-mode", "yolo",
                        prompt,
                    ],
                    cwd=worktree,
                    env=_qwen_env,
                    timeout=2700,
                )
                _impl_last_err = None
                break
            except RuntimeError as _exc:
                if is_rate_limit_error(str(_exc)):
                    router.blacklist(_p.name, until_midnight=is_quota_exhausted(str(_exc)))
                    _impl_last_err = _exc
                    continue
                log_dir = Path.home() / ".cache" / "autodev" / "qwen-runs"
                log_dir.mkdir(parents=True, exist_ok=True)
                log_path = log_dir / f"issue-{issue_number}-attempt-{int(_time.time())}.log"
                log_path.write_text(str(_exc))
                activity.logger.error(
                    "Qwen failed for issue #%d — full log at %s", issue_number, log_path
                )
                raise
        if _impl_last_err is not None:
            log_dir = Path.home() / ".cache" / "autodev" / "qwen-runs"  # consistent with single-provider path (M1 fix)
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / f"issue-{issue_number}-attempt-{int(_time.time())}.log"
            log_path.write_text(str(_impl_last_err))
            activity.logger.error(
                "All implement providers exhausted for issue #%d — full log at %s",
                issue_number, log_path,
            )
            raise _impl_last_err

        # Auto-fix style issues first, THEN purge whitespace-only residue.
        # ruff format may reformat files leaving only whitespace diffs; purge cleans those up.
        # Use git diff HEAD (not bare diff) to include staged changes. (HIGH-3 / M-order fix)
        changed_py = [
            f for f in (await _arun(["git", "diff", "HEAD", "--name-only"], cwd=worktree)).splitlines()
            if f.endswith(".py")
        ]
        if changed_py:
            try:
                await _arun(["python3.11", "-m", "ruff", "check", "--fix", *changed_py],
                            cwd=worktree)
                await _arun(["python3.11", "-m", "ruff", "format", *changed_py], cwd=worktree)
            except RuntimeError as _ruff_err:
                activity.logger.warning("ruff had errors: %s", str(_ruff_err)[:200])

        # Purge any remaining whitespace-only diffs (including those introduced by ruff format).
        await asyncio.to_thread(_purge_whitespace_only_changes, worktree)

        porcelain = await _arun(["git", "status", "--porcelain"], cwd=worktree)
        has_changes = bool(porcelain.strip())

        if has_changes:
            _title_lower = issue_title.lower()
            if any(k in _title_lower for k in ("fix", "bug", "patch", "repair", "correct",
                                                "修复", "修正", "修bug", "修改", "修")):
                _cc_prefix = "fix"
            elif any(k in _title_lower for k in ("add ", "implement ", "support ", "introduce ", "expose ",
                                                  "添加", "新增", "实现", "支持", "新建", "接入", "增加")):
                _cc_prefix = "feat"
            else:
                _cc_prefix = "chore"
            await _arun(["git", "add", "-A"], cwd=worktree)
            await _arun(
                [
                    "git", "commit", "--signoff", "-m",
                    f"{_cc_prefix}: implement issue #{issue_number}\n\n"
                    "Automated implementation by autodev-train Temporal worker.",
                ],
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
            sha = await _arun(["git", "rev-parse", "HEAD"], cwd=worktree)
        else:
            sha = ""

        impl_succeeded = True
        _stage = "implemented" if has_changes else "no_changes"
        _err = None if has_changes else "no changes produced by Codex"
        _sha = sha.strip() if sha else None
        # Single atomic upsert for stage + SHA — eliminates the window between the
        # prior two-step write where a crash left stage="implementing" but SHA was set. (M6 fix)
        db.upsert_run(issue_number, stage=_stage, branch=branch,
                      impl_commit_sha=_sha, error=_err)
        db.log_event(issue_number, "implement", "completed", f"has_changes={has_changes} sha={sha}")
        return {"branch": branch, "has_changes": has_changes, "sha": sha}

    except Exception as exc:
        db.upsert_run(issue_number, stage="failed", error=str(exc)[:500])
        db.log_event(issue_number, "implement", "failed", str(exc)[:500])
        raise
    finally:
        # Always attempt cleanup so stale worktrees don't accumulate in /tmp. (MEDIUM-1 fix)
        try:
            await _arun(["git", "worktree", "remove", "--force", worktree], cwd=main)
        except Exception:
            pass


# ── activity: create_pr ────────────────────────────────────────────────────────

@activity.defn(name="create_pr")
async def create_pr_activity(issue_number: int, branch: str) -> dict:
    """Create GitHub PR. Idempotent."""
    run = db.get_run(issue_number)
    if run and run["pr_number"] and run["stage"] in ("pr_created", "reviewing", "approved", "merged"):
        activity.logger.info("PR already created for issue #%d", issue_number)
        return {"pr_number": run["pr_number"], "skipped": True}

    db.log_event(issue_number, "create_pr", "started")

    # Crash recovery: if we crashed after `gh pr create` but before `db.upsert_run`,
    # the branch already has an open PR on GitHub. (H4 fix)
    # Tolerate gh CLI errors here — worst case we retry the create and GH rejects the dupe.
    _existing_pr = ""
    try:
        _existing_pr = (await _agh([
            "pr", "list", "--repo", REPO_SLUG, "--head", branch,
            "--state", "open", "--json", "number", "--jq", ".[0].number // empty",
        ])).strip()
    except RuntimeError as _e:
        activity.logger.warning(
            "PR existence check failed (non-fatal, will attempt create): %s", str(_e)[:200]
        )
    if _existing_pr:
        pr_number = int(_existing_pr)
        activity.logger.info("Recovered existing PR #%d for branch %s", pr_number, branch)
        db.upsert_run(issue_number, stage="pr_created", pr_number=pr_number, error=None)
        db.log_event(issue_number, "create_pr", "recovered", f"pr={pr_number}")
        return {"pr_number": pr_number}

    pr_body = (
        f"## Summary\n\nAutomated implementation by **autodev-train** (Temporal worker).\n\n"
        f"Closes #{issue_number}\n\n---\n"
        f"*Do not merge manually. autodev-train will merge after review passes.*"
    )

    pr_url = await _agh([
        "pr", "create",
        "--repo", REPO_SLUG,
        "--title", f"autodev: implement issue #{issue_number}",
        "--body", pr_body,
        "--head", branch,
        "--base", "main",
    ])

    pr_number_str = await _agh([
        "pr", "view", pr_url.strip(),
        "--repo", REPO_SLUG,
        "--json", "number",
        "--jq", ".number",
    ])
    pr_number = int(pr_number_str.strip())

    # Add labels after creation so a missing label doesn't abort the PR create. (H3 fix)
    for _label in ("autodev-pr", "release:none"):
        try:
            await _agh(["pr", "edit", str(pr_number), "--repo", REPO_SLUG, "--add-label", _label])
        except RuntimeError:
            pass

    db.upsert_run(issue_number, stage="pr_created", pr_number=pr_number, error=None)
    db.log_event(issue_number, "create_pr", "completed", f"pr={pr_number}")
    return {"pr_number": pr_number}
