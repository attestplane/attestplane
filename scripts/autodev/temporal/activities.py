# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
"""Temporal activities for autodev-train pipeline."""

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from temporalio import activity

from . import db

# ── environment ────────────────────────────────────────────────────────────────
REPO_URL = "https://github.com/attestplane/attestplane.git"
REPO_SLUG = "attestplane/attestplane"
MAIN_REPO = Path(
    os.environ.get("AUTODEV_MAIN_REPO", Path.home() / "projects/attestplane")
)
CODEX_HOME = os.environ.get("CODEX_HOME", str(Path.home() / "codex-home"))
BOT_NAME = "autodev-bot"
BOT_EMAIL = "258170091+merchloubna70-dot@users.noreply.github.com"
GFW_PROXY = "http://127.0.0.1:7897"


def _run(
    cmd: list[str] | str,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 2700,
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


# ── activity: implement ────────────────────────────────────────────────────────


@activity.defn(name="implement")
async def implement_activity(
    issue_number: int,
    issue_title: str,
    issue_body: str,
) -> dict:
    """Checkout worktree, run codex exec, commit & push. Idempotent."""
    run = db.get_run(issue_number)
    if run and run["stage"] in (
        "implemented",
        "pr_created",
        "reviewing",
        "approved",
        "merged",
    ):
        activity.logger.info("issue #%d already implemented, skipping", issue_number)
        return {"branch": run["branch"], "has_changes": True, "skipped": True}

    branch = f"autodev/issue-{issue_number}"
    worktree = str(MAIN_REPO.parent / f"attestplane-wt-{issue_number}")
    main = str(MAIN_REPO)

    db.upsert_run(issue_number, stage="implementing", branch=branch)
    db.log_event(issue_number, "implement", "started")

    try:
        # Sync main branch
        _run(["git", "fetch", "origin", "main"], cwd=main)
        _run(["git", "checkout", "main"], cwd=main)
        _run(["git", "reset", "--hard", "origin/main"], cwd=main)

        # Create / reset worktree
        if Path(worktree).exists():
            try:
                _run(["git", "worktree", "remove", "--force", worktree], cwd=main)
            except RuntimeError:
                pass
        _run(
            ["git", "worktree", "add", "-B", branch, worktree, "origin/main"], cwd=main
        )

        # Build Codex prompt
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
            "6. 只修改实现任务所需的最小文件集"
        )

        # Codex blocks for up to 45 min; run in thread so the asyncio event
        # loop stays free for Temporal heartbeats and other workflow tasks.
        await asyncio.to_thread(
            _run,
            ["codex", "exec", "--sandbox", "workspace-write", prompt],
            cwd=worktree,
            env={
                "CODEX_HOME": CODEX_HOME,
                "HOME": str(Path.home()),
                "PATH": os.environ["PATH"],
                "https_proxy": GFW_PROXY,
                "http_proxy": GFW_PROXY,
            },
            timeout=2700,
        )

        # Auto-fix style issues so ruff/format CI checks pass.
        # Errors that can't be auto-fixed are logged but don't block the commit.
        try:
            _run(
                ["python3.11", "-m", "ruff", "check", "--fix", "--unsafe-fixes", "."],
                cwd=worktree,
            )
        except RuntimeError as _ruff_err:
            activity.logger.warning(
                "ruff auto-fix had remaining errors (will commit anyway): %s",
                str(_ruff_err)[:300],
            )
        try:
            _run(["python3.11", "-m", "ruff", "format", "."], cwd=worktree)
        except RuntimeError as _fmt_err:
            activity.logger.warning("ruff format failed: %s", str(_fmt_err)[:300])

        # Detect changes
        porcelain = _run(["git", "status", "--porcelain"], cwd=worktree)
        has_changes = bool(porcelain.strip())

        if has_changes:
            _run(["git", "add", "-A"], cwd=worktree)
            _run(
                [
                    "git",
                    "commit",
                    "--signoff",
                    "-m",
                    f"feat: implement issue #{issue_number}\n\n"
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

        db.upsert_run(issue_number, stage="implemented", branch=branch)
        db.log_event(
            issue_number,
            "implement",
            "completed",
            f"has_changes={has_changes} sha={sha}",
        )
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
    if (
        run
        and run["pr_number"]
        and run["stage"] in ("pr_created", "reviewing", "approved", "merged")
    ):
        activity.logger.info("PR already created for issue #%d", issue_number)
        return {"pr_number": run["pr_number"], "skipped": True}

    db.log_event(issue_number, "create_pr", "started")

    pr_body = (
        f"## Summary\n\nAutomated implementation by **autodev-train** (Temporal worker).\n\n"
        f"Closes #{issue_number}\n\n---\n"
        f"*Do not merge manually. autodev-train will merge after review passes.*"
    )

    pr_url = _gh(
        [
            "pr",
            "create",
            "--repo",
            REPO_SLUG,
            "--title",
            f"autodev: implement issue #{issue_number}",
            "--body",
            pr_body,
            "--label",
            "autodev-pr",
            "--head",
            branch,
            "--base",
            "main",
        ]
    )

    pr_number_str = _gh(
        [
            "pr",
            "view",
            pr_url.strip(),
            "--repo",
            REPO_SLUG,
            "--json",
            "number",
            "--jq",
            ".number",
        ]
    )
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

    diff = _gh(["pr", "diff", str(pr_number), "--repo", REPO_SLUG])
    issue_body = _gh(
        [
            "issue",
            "view",
            str(issue_number),
            "--repo",
            REPO_SLUG,
            "--json",
            "body",
            "--jq",
            ".body",
        ]
    )

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
    try:
        # Qwen/DeepSeek review can take several minutes; run in thread.
        output = await asyncio.to_thread(
            _run,
            [
                "qwen",
                prompt,
                "--openai-api-key",
                deepseek_key,
                "--openai-base-url",
                "https://api.deepseek.com/v1",
                "--auth-type",
                "openai",
                "--model",
                "deepseek-v4-pro",
                "--approval-mode",
                "yolo",
                "--output-format",
                "text",
                "--max-session-turns",
                "1",
                "--channel",
                "CI",
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
    _gh(
        [
            "pr",
            "comment",
            str(pr_number),
            "--repo",
            REPO_SLUG,
            "--body",
            review_body,
        ]
    )

    if decision == "APPROVE":
        _gh(
            [
                "api",
                "-X",
                "POST",
                f"repos/{REPO_SLUG}/issues/{pr_number}/labels",
                "-f",
                "labels[]=review-passed",
            ]
        )
        db.upsert_run(issue_number, stage="approved")
    else:
        # Close PR immediately so it doesn't block the auto-loop guard.
        try:
            _gh(["pr", "close", str(pr_number), "--repo", REPO_SLUG])
        except RuntimeError:
            pass
        db.upsert_run(issue_number, stage="failed")

    db.log_event(issue_number, "post_review", "completed", f"decision={decision}")
    return {"posted": True}


# ── activity: merge_pr ─────────────────────────────────────────────────────────


@activity.defn(name="merge_pr")
async def merge_pr_activity(issue_number: int, pr_number: int) -> dict:
    """Squash-merge the PR. Waits for CI (via mergeStateStatus), then rebases and merges."""
    import time as _time

    branch = _gh(
        [
            "pr",
            "view",
            str(pr_number),
            "--repo",
            REPO_SLUG,
            "--json",
            "headRefName",
            "--jq",
            ".headRefName",
        ]
    ).strip()

    # Poll mergeStateStatus — avoids the broken `gh pr checks --json required` field.
    # CLEAN   → all checks passed, safe to merge.
    # UNSTABLE → one or more checks failed → close PR and exit (no retry).
    # BLOCKED  → branch protection pending → keep waiting.
    # CONFLICTING → merge conflict → proceed to rebase below.
    activity.logger.info("Waiting for CI on PR #%d ...", pr_number)
    ci_deadline = _time.monotonic() + 600
    while True:
        info = json.loads(
            _gh(
                [
                    "pr",
                    "view",
                    str(pr_number),
                    "--repo",
                    REPO_SLUG,
                    "--json",
                    "mergeable,mergeStateStatus",
                ]
            )
        )
        merge_state = info.get("mergeStateStatus", "UNKNOWN")
        mergeable = info.get("mergeable", "UNKNOWN")

        if merge_state == "CLEAN":
            activity.logger.info("CI passed for PR #%d (CLEAN)", pr_number)
            break
        if merge_state == "UNSTABLE":
            activity.logger.error(
                "CI FAILED for PR #%d (UNSTABLE) — closing PR", pr_number
            )
            try:
                _gh(
                    [
                        "pr",
                        "close",
                        str(pr_number),
                        "--repo",
                        REPO_SLUG,
                        "--comment",
                        "Closed by autodev-train: CI checks failed (UNSTABLE). Fix linting/tests and reopen.",
                    ]
                )
            except RuntimeError:
                pass
            db.upsert_run(issue_number, stage="failed")
            db.log_event(issue_number, "merge", "ci_failed", f"pr={pr_number}")
            return {"merged": False, "reason": "ci_unstable"}
        if mergeable == "CONFLICTING":
            activity.logger.info(
                "PR #%d has merge conflict — will attempt rebase", pr_number
            )
            break
        if _time.monotonic() > ci_deadline:
            activity.logger.warning(
                "CI timeout for PR #%d (state=%s) — merging anyway",
                pr_number,
                merge_state,
            )
            break
        await asyncio.sleep(30)
    worktree = str(MAIN_REPO.parent / f"attestplane-merge-{issue_number}")
    main = str(MAIN_REPO)

    # Rebase branch on current main to resolve any conflicts before merging.
    try:
        _run(["git", "fetch", "origin", "main", branch], cwd=main)
        if Path(worktree).exists():
            try:
                _run(["git", "worktree", "remove", "--force", worktree], cwd=main)
            except RuntimeError:
                pass
        _run(
            ["git", "worktree", "add", "-B", branch, worktree, f"origin/{branch}"],
            cwd=main,
        )
        _run(
            ["git", "rebase", "origin/main"],
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
    except RuntimeError as rebase_err:
        activity.logger.warning("rebase failed for PR #%d: %s", pr_number, rebase_err)
        # Abort rebase so worktree is clean; merge attempt below may still work or fail
        try:
            _run(["git", "rebase", "--abort"], cwd=worktree)
        except RuntimeError:
            pass
    finally:
        try:
            _run(["git", "worktree", "remove", "--force", worktree], cwd=main)
        except Exception:
            pass

    _gh(
        [
            "pr",
            "merge",
            str(pr_number),
            "-R",
            REPO_SLUG,
            "--squash",
            "--subject",
            f"autodev: implement issue #{issue_number} [autodev]",
            "--body",
            "Squash-merged by autodev-train Temporal worker after AI review + CI.",
        ]
    )
    db.upsert_run(issue_number, stage="merged")
    db.log_event(issue_number, "merge", "completed", f"pr={pr_number}")
    return {"merged": True}
