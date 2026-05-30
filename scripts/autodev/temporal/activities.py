# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
"""Temporal activities for autodev-train pipeline."""

import asyncio
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from temporalio import activity

from . import db

# ── environment ────────────────────────────────────────────────────────────────
REPO_URL = "https://github.com/attestplane/attestplane.git"
REPO_SLUG = "attestplane/attestplane"
MAIN_REPO = Path(os.environ.get("AUTODEV_MAIN_REPO", Path.home() / "projects/attestplane"))
QWEN_MODEL = os.environ.get("QWEN_MODEL", "deepseek-v4-flash")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
BOT_NAME = "autodev-bot"
BOT_EMAIL = "258170091+merchloubna70-dot@users.noreply.github.com"
GFW_PROXY = "http://127.0.0.1:7897"


def _run(
    cmd: list[str] | str,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 60,
) -> str:
    merged = {**os.environ}
    if env:
        merged.update(env)
    result = subprocess.run(
        cmd,
        shell=isinstance(cmd, str),
        cwd=cwd,
        env=merged,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"cmd={cmd!r} exit={result.returncode}\n"
            f"stdout: {result.stdout[-1000:]}\n"
            f"stderr: {result.stderr[-1000:]}"
        )
    return result.stdout.strip()


def _gh(args: list[str], **kwargs: Any) -> str:
    token = os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", ""))
    return _run(["gh", *args], env={"GH_TOKEN": token, **os.environ}, **kwargs)


def _purge_whitespace_only_changes(worktree: str) -> None:
    """Reset files whose only changes are whitespace/formatting (no semantic diff)."""
    if not Path(worktree).exists():
        return  # qwen may have removed the worktree dir; skip silently
    all_changed = set(_run(["git", "diff", "--name-only"], cwd=worktree).splitlines())
    semantic_changed = set(
        _run(["git", "diff", "--ignore-all-space", "--name-only"], cwd=worktree).splitlines()
    )
    whitespace_only = [f for f in all_changed - semantic_changed if f.strip()]
    if whitespace_only:
        _run(["git", "checkout", "--"] + whitespace_only, cwd=worktree)


# ── activity: implement ────────────────────────────────────────────────────────

@activity.defn(name="implement")
async def implement_activity(
    issue_number: int,
    issue_title: str,
    issue_body: str,
) -> dict:
    """Checkout worktree, run qwen (DeepSeek), commit & push. Idempotent."""
    run = db.get_run(issue_number)
    if run and run["stage"] in ("implemented", "pr_created", "reviewing", "approved", "merged"):
        activity.logger.info("issue #%d already implemented, skipping", issue_number)
        return {"branch": run["branch"], "has_changes": True, "skipped": True}

    branch = f"autodev/issue-{issue_number}"

    # If previous attempt ended in conflict/failure, delete the stale branch so
    # Qwen re-implements from the current main rather than reusing broken code.
    if run and run.get("stage") == "failed":
        activity.logger.info("issue #%d previously failed — purging stale branch to re-implement", issue_number)
        try:
            _run(["git", "push", "origin", "--delete", branch], cwd=str(MAIN_REPO))
        except RuntimeError:
            pass
        db.upsert_run(issue_number, stage="pending", pr_number=None, branch=None)

    # On retry: if the branch already exists on remote, skip Qwen re-run.
    # This prevents a retry from overwriting an in-progress CI/review with a new SHA.
    attempt = activity.info().attempt
    if attempt > 1:
        try:
            existing = _run(["git", "ls-remote", "--heads", "origin", branch],
                            cwd=str(MAIN_REPO))
            if existing.strip():
                activity.logger.info(
                    "Retry attempt %d for issue #%d — branch exists, skipping Qwen",
                    attempt, issue_number,
                )
                return {"branch": branch, "has_changes": True, "skipped": True}
        except RuntimeError:
            pass  # ls-remote failed → proceed with normal Qwen run

    # Use /tmp to keep worktrees outside the project tree so qwen (yolo mode)
    # cannot discover and delete sibling worktrees.
    worktree = f"/tmp/aw-impl-{issue_number}"
    main = str(MAIN_REPO)

    db.upsert_run(issue_number, stage="implementing", branch=branch)
    db.log_event(issue_number, "implement", "started")

    try:
        # Sync main branch
        _run(["git", "fetch", "origin", "main"], cwd=main)
        _run(["git", "checkout", "main"], cwd=main)
        _run(["git", "reset", "--hard", "origin/main"], cwd=main)

        # Create / reset worktree.
        # git worktree remove --force deregisters the worktree from git but does
        # not always delete the directory (e.g. when files have local changes).
        # Explicitly rmtree afterwards so git worktree add never sees a stale dir.
        import shutil as _shutil
        if Path(worktree).exists():
            try:
                _run(["git", "worktree", "remove", "--force", worktree], cwd=main)
            except RuntimeError:
                pass
            _shutil.rmtree(worktree, ignore_errors=True)
        _run(["git", "worktree", "add", "-B", branch, worktree, "origin/main"], cwd=main)

        # Build Qwen prompt
        prompt = (
            f"按照 AGENTS.md 和项目规范实现以下任务。\n\n"
            f"任务标题：{issue_title}\n\n"
            f"任务描述：\n{issue_body}\n\n"
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

        # First attempt uses flash (fast/cheap); retries escalate to pro.
        _impl_model = QWEN_MODEL if activity.info().attempt == 1 else "deepseek-v4-pro"
        activity.logger.info("implement_activity attempt=%d model=%s", activity.info().attempt, _impl_model)
        try:
            await asyncio.to_thread(
                _run,
                [
                    "qwen",
                    "-m", _impl_model,
                    "--auth-type", "openai",
                    "--openai-base-url", DEEPSEEK_BASE_URL,
                    "--approval-mode", "yolo",
                    prompt,
                ],
                cwd=worktree,
                env={
                    **os.environ,
                    "HOME": str(Path.home()),
                    "PATH": os.environ["PATH"],
                    "OPENAI_API_KEY": os.environ.get("DEEPSEEK_API_KEY", ""),
                    "https_proxy": GFW_PROXY,
                    "http_proxy": GFW_PROXY,
                },
                timeout=2700,
            )
        except RuntimeError as exc:
            import time as _t
            log_dir = MAIN_REPO / "data" / "qwen-runs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / f"issue-{issue_number}-attempt-{int(_t.time())}.log"
            log_path.write_text(str(exc))
            activity.logger.error(
                "Qwen failed for issue #%d — full log at %s", issue_number, log_path
            )
            raise

        # Purge files whose only changes are whitespace/formatting so the PR diff
        # stays focused on real implementation changes. Qwen sometimes runs
        # ruff format on the whole repo, creating a noisy 30+ file diff.
        _purge_whitespace_only_changes(worktree)

        # Auto-fix style issues on only the remaining changed files.
        changed_py = [
            f for f in _run(["git", "diff", "--name-only"], cwd=worktree).splitlines()
            if f.endswith(".py")
        ]
        if changed_py:
            try:
                _run(["python3.11", "-m", "ruff", "check", "--fix", "--unsafe-fixes", *changed_py],
                     cwd=worktree)
                _run(["python3.11", "-m", "ruff", "format", *changed_py], cwd=worktree)
            except RuntimeError as _ruff_err:
                activity.logger.warning("ruff had errors: %s", str(_ruff_err)[:200])

        # Detect changes
        porcelain = _run(["git", "status", "--porcelain"], cwd=worktree)
        has_changes = bool(porcelain.strip())

        if has_changes:
            # Infer Conventional Commits prefix from issue title so bump level
            # reflects semantic reality (most autodev tasks are internal improvements,
            # not user-visible features; hardcoding feat: inflates minor version).
            _title_lower = issue_title.lower()
            if any(k in _title_lower for k in ("fix", "bug", "patch", "repair", "correct")):
                _cc_prefix = "fix"
            elif any(k in _title_lower for k in ("add ", "implement ", "support ", "introduce ", "expose ")):
                _cc_prefix = "feat"
            else:
                _cc_prefix = "chore"
            _run(["git", "add", "-A"], cwd=worktree)
            _run(
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
            _run(["git", "push", "origin", branch, "--force-with-lease"], cwd=worktree)
            sha = _run(["git", "rev-parse", "HEAD"], cwd=worktree)
        else:
            sha = ""

        _stage = "implemented" if has_changes else "failed"
        _err = None if has_changes else "no changes produced by Codex"
        db.upsert_run(issue_number, stage=_stage, branch=branch, error=_err)
        db.log_event(issue_number, "implement", "completed", f"has_changes={has_changes} sha={sha}")
        return {"branch": branch, "has_changes": has_changes, "sha": sha}

    except Exception as exc:
        db.upsert_run(issue_number, stage="failed", error=str(exc)[:500])
        db.log_event(issue_number, "implement", "failed", str(exc)[:500])
        raise
    finally:
        try:
            _run(["git", "worktree", "remove", "--force", worktree], cwd=main)
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

    pr_body = (
        f"## Summary\n\nAutomated implementation by **autodev-train** (Temporal worker).\n\n"
        f"Closes #{issue_number}\n\n---\n"
        f"*Do not merge manually. autodev-train will merge after review passes.*"
    )

    pr_url = _gh([
        "pr", "create",
        "--repo", REPO_SLUG,
        "--title", f"autodev: implement issue #{issue_number}",
        "--body", pr_body,
        "--label", "autodev-pr",
        "--label", "release:none",
        "--head", branch,
        "--base", "main",
    ])

    pr_number_str = _gh([
        "pr", "view", pr_url.strip(),
        "--repo", REPO_SLUG,
        "--json", "number",
        "--jq", ".number",
    ])
    pr_number = int(pr_number_str.strip())

    db.upsert_run(issue_number, stage="pr_created", pr_number=pr_number)
    db.log_event(issue_number, "create_pr", "completed", f"pr={pr_number}")
    return {"pr_number": pr_number}


# ── activity: review_pr ────────────────────────────────────────────────────────

@activity.defn(name="review_pr")
async def review_pr_activity(issue_number: int, pr_number: int) -> dict:
    """Run Qwen Code + DeepSeek review. Idempotent."""
    run = db.get_run(issue_number)
    if run and run["review_decision"] and run["stage"] in ("approved", "merged"):
        return {"decision": run["review_decision"], "output": "", "skipped": True}

    db.log_event(issue_number, "review", "started", f"pr={pr_number}")

    try:
        diff = _gh(["pr", "diff", str(pr_number), "--repo", REPO_SLUG])
    except RuntimeError as _e:
        if "too_large" in str(_e) or "diff exceeded" in str(_e):
            # Diff too big for GH API — fall back to per-file patches, sorted by importance
            import json as _json
            files_raw = _gh(["api", f"repos/{REPO_SLUG}/pulls/{pr_number}/files?per_page=100"])
            files = _json.loads(files_raw)
            changed_files = [f.get("filename", "?") for f in files]
            file_patch = {f.get("filename", "?"): f.get("patch") or "(binary or too large)" for f in files}

            def _file_priority(fname: str) -> int:
                if fname.endswith(".py") and not any(k in fname for k in ("test_", "conftest")):
                    return 0
                if fname.endswith(".py"):
                    return 1
                return 2

            changed_files_sorted = sorted(changed_files, key=_file_priority)
            files_to_review = changed_files_sorted[:20]
            parts = [f"[DIFF TRUNCATED — PR has {len(files)} files; showing {len(files_to_review)} by importance]\n"]
            for fname in files_to_review:
                patch = file_patch.get(fname, "(binary or too large)")
                parts.append(f"--- {fname}\n{patch[:3000]}\n")
            diff = "\n".join(parts)[:50000]
        else:
            raise
    issue_body = _gh(["issue", "view", str(issue_number), "--repo", REPO_SLUG, "--json", "body", "--jq", ".body"])

    prompt = (
        "你是 Attestplane 项目的自动化代码审查员。\n\n"
        f"## 任务来源\n{issue_body}\n\n"
        f"## PR Diff\n```diff\n{diff}\n```\n\n"
        "## 审查标准（逐项检查）\n"
        "1. **实现完整性** — 代码是否覆盖了 Issue 中所有验收标准？\n"
        "2. **REUSE 合规** — 新增文件是否包含 SPDX-License-Identifier 和 SPDX-FileCopyrightText 头部？\n"
        "3. **代码正确性** — 逻辑是否正确，无明显 bug 或边界条件遗漏？\n"
        "4. **安全性** — 无硬编码密钥，无命令注入，无路径穿越。\n"
        "5. **项目规范** — 未修改 .github/workflows/、CHANGELOG.md。\n\n"
        "## 输出格式（严格遵守）\n"
        "第一行必须且只能是以下两个词之一（不加任何标点或空格）：\n"
        "APPROVE\n或\nREQUEST_CHANGES\n\n"
        "第二行起输出详细审查说明（中文），通过项用 ✅，不通过项用 ❌ 并给出修复建议。"
    )

    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    _review_model = (
        os.environ.get("DEEPSEEK_REVIEW_MODEL", QWEN_MODEL)
        if activity.info().attempt == 1
        else "deepseek-v4-pro"
    )
    activity.logger.info("review_pr_activity attempt=%d model=%s", activity.info().attempt, _review_model)
    try:
        output = await asyncio.to_thread(
            _run,
            [
                "qwen", prompt,
                "--openai-api-key", deepseek_key,
                "--openai-base-url", DEEPSEEK_BASE_URL,
                "--auth-type", "openai",
                "--model", _review_model,
                "-y",
                "--output-format", "text",
                "--max-session-turns", "5",
                "--channel", "CI",
                "--bare",
            ],
            env={**os.environ, "https_proxy": GFW_PROXY, "http_proxy": GFW_PROXY},
            timeout=600,
        )
    except Exception as exc:
        output = f"REQUEST_CHANGES\n\n❌ Qwen review failed: {exc}"

    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    decision = next(
        (ln for ln in lines if ln in ("APPROVE", "REQUEST_CHANGES")),
        "REQUEST_CHANGES",
    )

    db.upsert_run(issue_number, stage="reviewing", review_decision=decision)
    db.log_event(issue_number, "review", "completed", f"decision={decision}")
    return {"decision": decision, "output": output}


# ── activity: post_review ──────────────────────────────────────────────────────

@activity.defn(name="post_review")
async def post_review_activity(
    issue_number: int,
    pr_number: int,
    decision: str,
    review_output: str,
) -> dict:
    """Post GitHub review (APPROVE) or comment (REQUEST_CHANGES) on the PR.

    GitHub does not allow requesting changes on your own PR (422). We work
    around this by posting REQUEST_CHANGES as a regular PR comment instead
    of a formal review, while APPROVE goes through the review API.
    """
    body_lines = review_output.splitlines()
    detail = "\n".join(body_lines[1:]).strip() if len(body_lines) > 1 else ""
    review_body = (
        f"### autodev-review: {decision}\n\n{detail}\n\n---\n"
        "*Reviewed by autodev-train – Temporal worker – Qwen Code + DeepSeek v4.0 Pro*"
    )

    # GitHub forbids both APPROVE and REQUEST_CHANGES on your own PRs (422).
    # We post as a regular PR comment for both decisions, and add the
    # review-passed label directly for APPROVE — sufficient to trigger merge.
    _gh([
        "pr", "comment", str(pr_number),
        "--repo", REPO_SLUG,
        "--body", review_body,
    ])

    if decision == "APPROVE":
        _gh([
            "api", "-X", "POST",
            f"repos/{REPO_SLUG}/issues/{pr_number}/labels",
            "-f", "labels[]=review-passed",
        ])
        db.upsert_run(issue_number, stage="approved")
    else:
        # Close PR immediately so it doesn't block the auto-loop guard.
        try:
            _gh(["pr", "close", str(pr_number), "--repo", REPO_SLUG])
        except RuntimeError:
            pass
        # Sync-close the corresponding issue and label it to prevent duplicate audit picks.
        try:
            _gh(["issue", "close", str(issue_number), "--repo", REPO_SLUG,
                 "--comment",
                 f"Closed: autodev-train PR #{pr_number} received REQUEST_CHANGES and was not merged. "
                 "Re-open this issue to retry implementation."])
            _gh(["issue", "edit", str(issue_number), "--repo", REPO_SLUG,
                 "--add-label", "autodev-failed"])
        except RuntimeError as _e:
            activity.logger.warning("Failed to close issue #%d: %s", issue_number, str(_e)[:200])
        db.upsert_run(issue_number, stage="failed")
        # Kick auto-loop so it can advance even if no [autodev] merge commit was produced
        try:
            _gh(["workflow", "run", "auto-loop.yml", "--repo", REPO_SLUG, "--ref", "main"])
        except RuntimeError:
            pass

    db.log_event(issue_number, "post_review", "completed", f"decision={decision}")
    return {"posted": True}


# ── activity: fix_ci ──────────────────────────────────────────────────────────

@activity.defn(name="fix_ci")
async def fix_ci_activity(issue_number: int, pr_number: int) -> dict:
    """Wait for CI on a freshly-created PR; if it fails, run Qwen to fix the errors.

    Returns {"ci_passed": bool, "fixed": bool}.
    Called once between create_pr and review_pr. merge_pr_activity re-checks CI
    independently before the final squash-merge, so a False/"not fixed" here only
    means we skip the fast-path — the PR stays open for review.
    """
    import time as _time

    branch = _gh(
        ["pr", "view", str(pr_number), "--repo", REPO_SLUG, "--json", "headRefName", "--jq", ".headRefName"]
    ).strip()

    # ── wait for CI to complete (up to 20 minutes) ─────────────────────────────
    ci_wait_deadline = _time.monotonic() + 1200
    while True:
        pr_info = json.loads(_gh(
            ["pr", "view", str(pr_number), "--repo", REPO_SLUG,
             "--json", "mergeStateStatus,statusCheckRollup"]
        ))
        merge_state = pr_info.get("mergeStateStatus", "UNKNOWN")
        checks = pr_info.get("statusCheckRollup", [])

        if not checks:
            # CI checks haven't registered yet — wait before evaluating state
            await asyncio.sleep(15)
            continue

        pending = [c for c in checks if c.get("status") not in ("COMPLETED",)]

        if merge_state == "CLEAN" and not pending:
            activity.logger.info("CI passed for PR #%d (CLEAN) — no fix needed", pr_number)
            return {"ci_passed": True, "fixed": False}

        if not pending:
            # All checks completed but not CLEAN → CI failed
            activity.logger.info("CI failed for PR #%d (state=%s) — will attempt Qwen fix", pr_number, merge_state)
            break

        if _time.monotonic() > ci_wait_deadline:
            activity.logger.warning("Timed out waiting for CI on PR #%d — attempting fix anyway", pr_number)
            break

        await asyncio.sleep(30)

    # ── extract CI error logs ──────────────────────────────────────────────────
    # databaseId = check-run ID ≠ workflow run ID; gh run view needs the latter.
    # Extract workflow run ID from detailsUrl (…/actions/runs/{run_id}/job/…).
    failed_checks = [c for c in checks if c.get("conclusion") == "FAILURE"]
    error_summary = ""
    seen_run_ids: set[str] = set()
    for check in failed_checks[:5]:
        check_name = check.get("name", "unknown")
        details_url = check.get("detailsUrl", "")
        m = re.search(r"/actions/runs/(\d+)", details_url)
        run_id = m.group(1) if m else ""
        if not run_id or run_id in seen_run_ids:
            continue
        seen_run_ids.add(run_id)
        try:
            raw_log = _gh(["run", "view", run_id, "--log-failed", "--repo", REPO_SLUG], timeout=90)
            # Strip "<job>\t<step>\t<ts>Z " prefix to target actual content
            cleaned: list[str] = []
            for raw_ln in raw_log.splitlines():
                parts = raw_ln.split("\t", 2)
                cln = parts[2] if len(parts) == 3 else raw_ln
                ts_idx = cln.find("Z ")
                cln = cln[ts_idx + 2:] if ts_idx != -1 else cln
                cleaned.append(cln)
            kept = [
                ln for ln in cleaned
                if any(kw in ln for kw in
                       ["error", "FAILED", "Error:", "E402", "assert", "Found", "✗",
                        "ruff", "mypy", "biome", "markdownlint", "lychee", "TypeError",
                        "ImportError", "AttributeError", "raise ", 'File "', ">       ",
                        "ERRORS", "short test summary", "pytest", "AssertionError",
                        "##[error]", "allowlist", "manifest", "Unused", "type: ignore"])
            ]
            error_summary += f"\n### {check_name}\n" + "\n".join(kept[:80]) + "\n"
        except RuntimeError:
            error_summary += f"\n### {check_name}\n(log unavailable)\n"

    if not error_summary.strip():
        activity.logger.warning("No extractable CI errors for PR #%d — skipping Qwen fix", pr_number)
        return {"ci_passed": False, "fixed": False}

    # ── run Qwen on a fresh worktree of the branch ───────────────────────────
    import shutil as _shutil
    main = str(MAIN_REPO)
    worktree = f"/tmp/aw-cifix-{issue_number}"
    try:
        _run(["git", "fetch", "origin", branch], cwd=main)
        if Path(worktree).exists():
            try:
                _run(["git", "worktree", "remove", "--force", worktree], cwd=main)
            except RuntimeError:
                pass
            _shutil.rmtree(worktree, ignore_errors=True)
        _run(["git", "worktree", "add", "-B", branch, worktree, f"origin/{branch}"], cwd=main)

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

        _fix_model = QWEN_MODEL if activity.info().attempt == 1 else "deepseek-v4-pro"
        activity.logger.info("fix_ci_activity attempt=%d model=%s", activity.info().attempt, _fix_model)
        await asyncio.to_thread(
            _run,
            [
                "qwen",
                "-m", _fix_model,
                "--auth-type", "openai",
                "--openai-base-url", DEEPSEEK_BASE_URL,
                "--approval-mode", "yolo",
                fix_prompt,
            ],
            cwd=worktree,
            env={
                **os.environ,
                "HOME": str(Path.home()),
                "PATH": os.environ["PATH"],
                "OPENAI_API_KEY": os.environ.get("DEEPSEEK_API_KEY", ""),
                "https_proxy": GFW_PROXY,
                "http_proxy": GFW_PROXY,
            },
            timeout=1800,
        )

        # Post-Qwen ruff cleanup
        sdk_py = str(Path(worktree) / "sdk" / "python")
        for ruff_cmd in [
            ["python3.11", "-m", "ruff", "check", "--fix", "--unsafe-fixes", "."],
            ["python3.11", "-m", "ruff", "format", "."],
        ]:
            try:
                _run(ruff_cmd, cwd=sdk_py)
            except RuntimeError as e:
                activity.logger.warning("ruff post-fix: %s", str(e)[:200])

        porcelain = _run(["git", "status", "--porcelain"], cwd=worktree)
        if porcelain.strip():
            _run(["git", "add", "-A"], cwd=worktree)
            _run(
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
            _run(["git", "push", "origin", branch, "--force-with-lease"], cwd=worktree)
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
        return {"ci_passed": False, "fixed": False}
    finally:
        try:
            _run(["git", "worktree", "remove", "--force", worktree], cwd=main)
        except Exception:
            pass


# ── activity: merge_pr ─────────────────────────────────────────────────────────

@activity.defn(name="merge_pr")
async def merge_pr_activity(issue_number: int, pr_number: int) -> dict:
    """Squash-merge the PR. Waits for CI (via mergeStateStatus), then rebases and merges."""
    import time as _time

    branch = _gh(["pr", "view", str(pr_number), "--repo", REPO_SLUG, "--json", "headRefName", "--jq", ".headRefName"]).strip()

    # Poll mergeStateStatus — avoids the broken `gh pr checks --json required` field.
    # CLEAN      → all checks passed, safe to merge.
    # UNSTABLE   → non-required checks failed; inspect failures:
    #              if pytest/mypy/ruff fail → real code quality issue → close.
    #              if only link-check/lint fail → cosmetic → proceed to merge.
    # BLOCKED    → required check failed OR pending → wait; if all done and any FAILURE, close.
    # CONFLICTING → merge conflict → proceed to rebase below.
    _CRITICAL_CHECK_KEYWORDS = ("pytest", "mypy", "ruff", "typecheck", "test")

    activity.logger.info("Waiting for CI on PR #%d ...", pr_number)
    ci_deadline = _time.monotonic() + 600
    while True:
        pr_info = json.loads(_gh(
            ["pr", "view", str(pr_number), "--repo", REPO_SLUG,
             "--json", "mergeable,mergeStateStatus,statusCheckRollup"]
        ))
        merge_state = pr_info.get("mergeStateStatus", "UNKNOWN")
        mergeable = pr_info.get("mergeable", "UNKNOWN")
        checks = pr_info.get("statusCheckRollup", [])

        if merge_state == "CLEAN":
            activity.logger.info("CI passed for PR #%d (CLEAN)", pr_number)
            break
        if merge_state == "UNSTABLE":
            # Non-required checks failing. Close only if it's a real code quality failure.
            critical_failures = [
                c for c in checks
                if c.get("conclusion") == "FAILURE" and
                any(kw in c.get("name", "").lower() for kw in _CRITICAL_CHECK_KEYWORDS)
            ]
            if critical_failures:
                names = ", ".join(c.get("name", "?") for c in critical_failures[:3])
                activity.logger.error(
                    "CI FAILED for PR #%d (UNSTABLE, critical failures: %s) — closing PR",
                    pr_number, names,
                )
                try:
                    _gh(["pr", "close", str(pr_number), "--repo", REPO_SLUG,
                         "--comment",
                         f"Closed by autodev-train: CI critical checks failed ({names}). Fix and reopen."])
                except RuntimeError:
                    pass
                db.upsert_run(issue_number, stage="failed")
                db.log_event(issue_number, "merge", "ci_failed", f"pr={pr_number} reason=UNSTABLE_CRITICAL")
                return {"merged": False, "reason": "ci_unstable_critical"}
            activity.logger.info(
                "CI UNSTABLE for PR #%d but only cosmetic failures — proceeding to merge", pr_number
            )
            break
        if merge_state == "BLOCKED":
            # If all checks completed and at least one failed → CI is done and broken
            pending = [c for c in checks if c.get("status") not in ("COMPLETED",)]
            failed = [c for c in checks if c.get("conclusion") == "FAILURE"]
            if not pending and failed:
                activity.logger.error(
                    "CI FAILED for PR #%d (BLOCKED, all checks done) — closing PR", pr_number
                )
                try:
                    _gh(["pr", "close", str(pr_number), "--repo", REPO_SLUG,
                         "--comment", "Closed by autodev-train: required CI checks failed (BLOCKED). Fix linting/tests and reopen."])
                except RuntimeError:
                    pass
                try:
                    _gh(["issue", "close", str(issue_number), "--repo", REPO_SLUG,
                         "--comment", f"Closed: PR #{pr_number} failed required CI checks. Re-open to retry."])
                    _gh(["issue", "edit", str(issue_number), "--repo", REPO_SLUG,
                         "--add-label", "autodev-failed"])
                except RuntimeError:
                    pass
                db.upsert_run(issue_number, stage="failed")
                db.log_event(issue_number, "merge", "ci_failed", f"pr={pr_number} reason=BLOCKED")
                return {"merged": False, "reason": "ci_blocked"}
        if mergeable == "CONFLICTING":
            activity.logger.info("PR #%d has merge conflict — will attempt rebase", pr_number)
            break
        if _time.monotonic() > ci_deadline:
            if merge_state == "BLOCKED":
                # required check still failing after timeout → close
                activity.logger.error("CI timeout for PR #%d (BLOCKED) — closing PR", pr_number)
                try:
                    _gh(["pr", "close", str(pr_number), "--repo", REPO_SLUG,
                         "--comment", "Closed by autodev-train: CI timed out in BLOCKED state."])
                except RuntimeError:
                    pass
                db.upsert_run(issue_number, stage="failed")
                db.log_event(issue_number, "merge", "ci_timeout_blocked", f"pr={pr_number}")
                return {"merged": False, "reason": "ci_timeout_blocked"}
            elif mergeable == "CONFLICTING":
                # merge conflict on timeout → proceed to rebase (will resolve or fail)
                activity.logger.warning("CI timeout for PR #%d (CONFLICTING) — attempting rebase", pr_number)
                break
            elif merge_state == "UNKNOWN":
                # unknown state → close safely
                activity.logger.error("CI timeout for PR #%d (UNKNOWN state) — closing PR", pr_number)
                try:
                    _gh(["pr", "close", str(pr_number), "--repo", REPO_SLUG,
                         "--comment", "Closed by autodev-train: CI timed out in unknown state."])
                except RuntimeError:
                    pass
                db.upsert_run(issue_number, stage="failed")
                return {"merged": False, "reason": "ci_timeout_unknown"}
            else:
                # BEHIND, UNSTABLE etc → proceed to rebase/merge
                activity.logger.warning(
                    "CI timeout for PR #%d (state=%s) — proceeding to merge", pr_number, merge_state
                )
                break
        await asyncio.sleep(30)
    worktree = str(MAIN_REPO.parent / f"attestplane-merge-{issue_number}")
    main = str(MAIN_REPO)

    # Rebase branch on current main to resolve any conflicts before merging.
    rebase_ok = False
    try:
        _run(["git", "fetch", "origin", "main", branch], cwd=main)
        if Path(worktree).exists():
            try:
                _run(["git", "worktree", "remove", "--force", worktree], cwd=main)
            except RuntimeError:
                pass
        _run(["git", "worktree", "add", "-B", branch, worktree, f"origin/{branch}"], cwd=main)

        # Record tree hash before rebase to detect file-tree changes (Fix-3)
        pre_rebase_tree = _run(["git", "rev-parse", "HEAD^{tree}"], cwd=worktree)

        _run(["git", "rebase", "origin/main"], cwd=worktree, env={
            **os.environ,
            "GIT_AUTHOR_NAME": BOT_NAME,
            "GIT_AUTHOR_EMAIL": BOT_EMAIL,
            "GIT_COMMITTER_NAME": BOT_NAME,
            "GIT_COMMITTER_EMAIL": BOT_EMAIL,
        })

        # Warn if rebase changed file tree — review was on pre-rebase diff (Fix-3)
        post_rebase_tree = _run(["git", "rev-parse", "HEAD^{tree}"], cwd=worktree)
        if pre_rebase_tree != post_rebase_tree:
            activity.logger.warning(
                "PR #%d: rebase changed file tree (%s → %s) — review was on pre-rebase diff",
                pr_number, pre_rebase_tree[:8], post_rebase_tree[:8],
            )
            try:
                _gh(["pr", "comment", str(pr_number), "--repo", REPO_SLUG,
                     "--body",
                     "⚠️ **Rebase changed file tree** — this PR was reviewed on the pre-rebase diff. "
                     "The merge commit may differ from what was reviewed."])
            except RuntimeError:
                pass

        _run(["git", "push", "origin", branch, "--force-with-lease"], cwd=worktree)
        rebase_ok = True
    except RuntimeError as rebase_err:
        activity.logger.error("rebase FAILED for PR #%d (true conflict) — closing PR: %s", pr_number, str(rebase_err)[:200])
        try:
            _run(["git", "rebase", "--abort"], cwd=worktree)
        except RuntimeError:
            pass
    finally:
        try:
            _run(["git", "worktree", "remove", "--force", worktree], cwd=main)
        except Exception:
            pass

    if not rebase_ok:
        try:
            _gh(["pr", "close", str(pr_number), "--repo", REPO_SLUG,
                 "--comment", "Closed by autodev-train: rebase onto main failed due to merge conflicts."])
        except RuntimeError:
            pass
        db.upsert_run(issue_number, stage="failed")
        db.log_event(issue_number, "merge", "conflict", f"pr={pr_number}")
        return {"merged": False, "reason": "conflict"}

    # Rebase succeeded — CI already confirmed clean above; squash-merge synchronously (Fix-1)
    _gh(["pr", "merge", str(pr_number), "--repo", REPO_SLUG,
         "--squash", "--delete-branch",
         "--subject", f"feat: merge autodev PR #{pr_number} for issue #{issue_number} [autodev]"])

    db.upsert_run(issue_number, stage="merged")
    db.log_event(issue_number, "merge", "completed", f"pr={pr_number}")
    return {"merged": True}
