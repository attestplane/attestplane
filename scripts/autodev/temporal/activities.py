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


def _purge_whitespace_only_changes(worktree: str) -> None:
    """Reset files whose only changes are whitespace/formatting (no semantic diff)."""
    changed = _run(["git", "diff", "--name-only"], cwd=worktree).splitlines()
    reset: list[str] = []
    for fname in changed:
        if not fname.strip():
            continue
        # --ignore-all-space: if the diff is empty, the change is whitespace-only
        semantic_diff = _run(
            ["git", "diff", "--ignore-all-space", "--", fname], cwd=worktree
        )
        if not semantic_diff.strip():
            reset.append(fname)
    if reset:
        _run(["git", "checkout", "--"] + reset, cwd=worktree)


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
            "6. 只修改实现任务所需的最小文件集\n"
            "7. 严禁对整个仓库运行 ruff format .、black .、isort . 等批量格式化命令\n"
            "   只在新建或修改的具体文件上运行格式化\n"
            "8. 最小化 diff：不要重构与任务无关的代码，不要重命名无关变量或调整无关缩进"
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

        # Purge files whose only changes are whitespace/formatting so the PR diff
        # stays focused on real implementation changes. Codex sometimes runs
        # ruff format on the whole repo, creating a noisy 30+ file diff.
        _purge_whitespace_only_changes(worktree)

        # Auto-fix style issues on only the remaining changed files.
        changed_py = [
            f
            for f in _run(["git", "diff", "--name-only"], cwd=worktree).splitlines()
            if f.endswith(".py")
        ]
        for _py_file in changed_py:
            try:
                _run(
                    [
                        "python3.11",
                        "-m",
                        "ruff",
                        "check",
                        "--fix",
                        "--unsafe-fixes",
                        _py_file,
                    ],
                    cwd=worktree,
                )
                _run(["python3.11", "-m", "ruff", "format", _py_file], cwd=worktree)
            except RuntimeError as _ruff_err:
                activity.logger.warning(
                    "ruff on %s had errors: %s", _py_file, str(_ruff_err)[:200]
                )

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

    try:
        diff = _gh(["pr", "diff", str(pr_number), "--repo", REPO_SLUG])
    except RuntimeError as _e:
        if "too_large" in str(_e) or "diff exceeded" in str(_e):
            # Diff too big for GH API — fall back to per-file patches (first page = 30 files)
            import json as _json

            files_raw = _gh(
                ["api", f"repos/{REPO_SLUG}/pulls/{pr_number}/files?per_page=30"]
            )
            files = _json.loads(files_raw)
            parts = [
                f"[DIFF TRUNCATED — PR has >{len(files)} files; showing first 30]\n"
            ]
            for file in files:
                fname = file.get("filename", "?")
                patch = file.get("patch") or "(binary or too large)"
                parts.append(f"--- {fname}\n{patch[:2000]}\n")
            diff = "\n".join(parts)[:50000]
        else:
            raise
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
        # Kick auto-loop so it can advance even if no [autodev] merge commit was produced
        try:
            _gh(
                [
                    "workflow",
                    "run",
                    "auto-loop.yml",
                    "--repo",
                    REPO_SLUG,
                    "--ref",
                    "main",
                ]
            )
        except RuntimeError:
            pass

    db.log_event(issue_number, "post_review", "completed", f"decision={decision}")
    return {"posted": True}


# ── activity: fix_ci ──────────────────────────────────────────────────────────


@activity.defn(name="fix_ci")
async def fix_ci_activity(issue_number: int, pr_number: int) -> dict:
    """Wait for CI on a freshly-created PR; if it fails, run Codex to fix the errors.

    Returns {"ci_passed": bool, "fixed": bool}.
    Called once between create_pr and review_pr. merge_pr_activity re-checks CI
    independently before the final squash-merge, so a False/"not fixed" here only
    means we skip the fast-path — the PR stays open for review.
    """
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

    # ── wait for CI to complete (up to 5 minutes) ──────────────────────────────
    ci_wait_deadline = _time.monotonic() + 300
    while True:
        pr_info = json.loads(
            _gh(
                [
                    "pr",
                    "view",
                    str(pr_number),
                    "--repo",
                    REPO_SLUG,
                    "--json",
                    "mergeStateStatus,statusCheckRollup",
                ]
            )
        )
        merge_state = pr_info.get("mergeStateStatus", "UNKNOWN")
        checks = pr_info.get("statusCheckRollup", [])
        pending = [c for c in checks if c.get("status") not in ("COMPLETED",)]

        if merge_state == "CLEAN":
            activity.logger.info(
                "CI passed for PR #%d (CLEAN) — no fix needed", pr_number
            )
            return {"ci_passed": True, "fixed": False}

        if not pending:
            # All checks completed but not CLEAN → CI failed
            activity.logger.info(
                "CI failed for PR #%d (state=%s) — will attempt Codex fix",
                pr_number,
                merge_state,
            )
            break

        if _time.monotonic() > ci_wait_deadline:
            activity.logger.warning(
                "Timed out waiting for CI on PR #%d — attempting fix anyway", pr_number
            )
            break

        await asyncio.sleep(30)

    # ── extract CI error logs ──────────────────────────────────────────────────
    failed_checks = [c for c in checks if c.get("conclusion") == "FAILURE"]
    error_summary = ""
    for check in failed_checks[:5]:
        check_name = check.get("name", "unknown")
        run_id = str(check.get("databaseId", ""))
        if run_id:
            try:
                log = _gh(
                    ["run", "view", run_id, "--log-failed", "--repo", REPO_SLUG],
                    timeout=90,
                )
                # Keep only diagnostic lines to stay within Codex context
                kept = [
                    ln
                    for ln in log.splitlines()
                    if any(
                        kw in ln
                        for kw in [
                            "error",
                            "FAILED",
                            "Error:",
                            "E402",
                            "assert",
                            "Found",
                            "✗",
                            "ruff",
                            "mypy",
                            "biome",
                            "markdownlint",
                            "lychee",
                            "TypeError",
                        ]
                    )
                ]
                error_summary += f"\n### {check_name}\n" + "\n".join(kept[:40]) + "\n"
            except RuntimeError:
                error_summary += f"\n### {check_name}\n(log unavailable)\n"

    if not error_summary.strip():
        activity.logger.warning(
            "No extractable CI errors for PR #%d — skipping Codex fix", pr_number
        )
        return {"ci_passed": False, "fixed": False}

    # ── run Codex on a fresh worktree of the branch ───────────────────────────
    main = str(MAIN_REPO)
    worktree = str(MAIN_REPO.parent / f"attestplane-cifix-{issue_number}")
    try:
        _run(["git", "fetch", "origin", branch], cwd=main)
        if Path(worktree).exists():
            try:
                _run(["git", "worktree", "remove", "--force", worktree], cwd=main)
            except RuntimeError:
                pass
        _run(
            ["git", "worktree", "add", "-B", branch, worktree, f"origin/{branch}"],
            cwd=main,
        )

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

        await asyncio.to_thread(
            _run,
            ["codex", "exec", "--sandbox", "workspace-write", fix_prompt],
            cwd=worktree,
            env={
                "CODEX_HOME": CODEX_HOME,
                "HOME": str(Path.home()),
                "PATH": os.environ["PATH"],
                "https_proxy": GFW_PROXY,
                "http_proxy": GFW_PROXY,
            },
            timeout=1800,
        )

        # Post-Codex ruff cleanup
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
                [
                    "git",
                    "commit",
                    "--signoff",
                    "-m",
                    f"fix(ci): auto-fix CI errors for issue #{issue_number}",
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
            activity.logger.info("CI fix committed and pushed for PR #%d", pr_number)
            db.log_event(
                issue_number, "fix_ci", "completed", f"pr={pr_number} fixed=True"
            )
            return {"ci_passed": False, "fixed": True}
        else:
            activity.logger.warning(
                "Codex produced no changes for CI fix on PR #%d", pr_number
            )
            db.log_event(
                issue_number, "fix_ci", "completed", f"pr={pr_number} fixed=False"
            )
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
    # CLEAN      → all checks passed, safe to merge.
    # UNSTABLE   → non-required checks failed → close PR and exit (no retry).
    # BLOCKED    → required check failed OR pending → wait; if all done and any FAILURE, close.
    # CONFLICTING → merge conflict → proceed to rebase below.
    activity.logger.info("Waiting for CI on PR #%d ...", pr_number)
    ci_deadline = _time.monotonic() + 600
    while True:
        pr_info = json.loads(
            _gh(
                [
                    "pr",
                    "view",
                    str(pr_number),
                    "--repo",
                    REPO_SLUG,
                    "--json",
                    "mergeable,mergeStateStatus,statusCheckRollup",
                ]
            )
        )
        merge_state = pr_info.get("mergeStateStatus", "UNKNOWN")
        mergeable = pr_info.get("mergeable", "UNKNOWN")
        checks = pr_info.get("statusCheckRollup", [])

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
            db.log_event(
                issue_number, "merge", "ci_failed", f"pr={pr_number} reason=UNSTABLE"
            )
            try:
                _gh(
                    [
                        "workflow",
                        "run",
                        "auto-loop.yml",
                        "--repo",
                        REPO_SLUG,
                        "--ref",
                        "main",
                    ]
                )
            except RuntimeError:
                pass
            return {"merged": False, "reason": "ci_unstable"}
        if merge_state == "BLOCKED":
            # If all checks completed and at least one failed → CI is done and broken
            pending = [c for c in checks if c.get("status") not in ("COMPLETED",)]
            failed = [c for c in checks if c.get("conclusion") == "FAILURE"]
            if not pending and failed:
                activity.logger.error(
                    "CI FAILED for PR #%d (BLOCKED, all checks done) — closing PR",
                    pr_number,
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
                            "Closed by autodev-train: required CI checks failed (BLOCKED). Fix linting/tests and reopen.",
                        ]
                    )
                except RuntimeError:
                    pass
                db.upsert_run(issue_number, stage="failed")
                db.log_event(
                    issue_number, "merge", "ci_failed", f"pr={pr_number} reason=BLOCKED"
                )
                try:
                    _gh(
                        [
                            "workflow",
                            "run",
                            "auto-loop.yml",
                            "--repo",
                            REPO_SLUG,
                            "--ref",
                            "main",
                        ]
                    )
                except RuntimeError:
                    pass
                return {"merged": False, "reason": "ci_blocked"}
        if mergeable == "CONFLICTING":
            activity.logger.info(
                "PR #%d has merge conflict — will attempt rebase", pr_number
            )
            break
        if _time.monotonic() > ci_deadline:
            # Timeout: if BLOCKED (not just slow), close instead of blindly merging
            if merge_state == "BLOCKED":
                activity.logger.error(
                    "CI timeout for PR #%d (BLOCKED) — closing PR", pr_number
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
                            "Closed by autodev-train: CI timed out in BLOCKED state.",
                        ]
                    )
                except RuntimeError:
                    pass
                db.upsert_run(issue_number, stage="failed")
                db.log_event(
                    issue_number, "merge", "ci_timeout_blocked", f"pr={pr_number}"
                )
                try:
                    _gh(
                        [
                            "workflow",
                            "run",
                            "auto-loop.yml",
                            "--repo",
                            REPO_SLUG,
                            "--ref",
                            "main",
                        ]
                    )
                except RuntimeError:
                    pass
                return {"merged": False, "reason": "ci_timeout_blocked"}
            activity.logger.warning(
                "CI timeout for PR #%d (state=%s) — proceeding to merge",
                pr_number,
                merge_state,
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
        rebase_ok = True
    except RuntimeError as rebase_err:
        activity.logger.error(
            "rebase FAILED for PR #%d (true conflict) — closing PR: %s",
            pr_number,
            str(rebase_err)[:200],
        )
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
            _gh(
                [
                    "pr",
                    "close",
                    str(pr_number),
                    "--repo",
                    REPO_SLUG,
                    "--comment",
                    "Closed by autodev-train: rebase onto main failed due to merge conflicts.",
                ]
            )
        except RuntimeError:
            pass
        db.upsert_run(issue_number, stage="failed")
        db.log_event(issue_number, "merge", "conflict", f"pr={pr_number}")
        try:
            _gh(
                [
                    "workflow",
                    "run",
                    "auto-loop.yml",
                    "--repo",
                    REPO_SLUG,
                    "--ref",
                    "main",
                ]
            )
        except RuntimeError:
            pass
        return {"merged": False, "reason": "conflict"}

    # Rebase succeeded — use --auto so GitHub waits for fresh CI before merging
    _gh(
        [
            "pr",
            "merge",
            str(pr_number),
            "-R",
            REPO_SLUG,
            "--squash",
            "--auto",
            "--subject",
            f"autodev: implement issue #{issue_number} [autodev]",
            "--body",
            "Squash-merged by autodev-train Temporal worker after AI review + CI.",
        ]
    )
    # Poll until GitHub actually merges the PR (--auto is async)
    poll_deadline = _time.monotonic() + 600
    while True:
        state = json.loads(
            _gh(
                [
                    "pr",
                    "view",
                    str(pr_number),
                    "--repo",
                    REPO_SLUG,
                    "--json",
                    "state,mergedAt",
                ]
            )
        )
        if state.get("mergedAt"):
            break
        if state.get("state") == "CLOSED":
            activity.logger.error(
                "PR #%d was closed (not merged) after --auto", pr_number
            )
            db.upsert_run(issue_number, stage="failed")
            db.log_event(issue_number, "merge", "closed_not_merged", f"pr={pr_number}")
            return {"merged": False, "reason": "closed_not_merged"}
        if _time.monotonic() > poll_deadline:
            activity.logger.warning("--auto merge timeout for PR #%d", pr_number)
            break
        await asyncio.sleep(20)

    db.upsert_run(issue_number, stage="merged")
    db.log_event(issue_number, "merge", "completed", f"pr={pr_number}")
    return {"merged": True}
