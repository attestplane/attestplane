# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
"""review_pr_activity and post_review_activity for autodev-train pipeline."""

import json
import os
import re
from pathlib import Path

from temporalio import activity

from .. import db
from ..llm_router import router
from ._base import (
    BOT_EMAIL,
    BOT_NAME,
    GFW_PROXY,
    REPO_SLUG,
    _arun,
    _agh,
)


# Hoisted to module scope so it's compiled once, not per invocation. (L5 fix)
_DECISION_RE = re.compile(r"\b(APPROVE|REQUEST_CHANGES)\b")


# ── activity: review_pr ────────────────────────────────────────────────────────

@activity.defn(name="review_pr")
async def review_pr_activity(issue_number: int, pr_number: int) -> dict:
    """Run Qwen Code + DeepSeek review. Idempotent."""
    run = db.get_run(issue_number)
    if run and run["review_decision"] and run["stage"] in ("approved", "merged"):
        return {"decision": run["review_decision"], "output": "", "skipped": True}

    db.log_event(issue_number, "review", "started", f"pr={pr_number}")

    try:
        diff = await _agh(["pr", "diff", str(pr_number), "--repo", REPO_SLUG])
        diff = diff[:30000]  # cap to keep total argv under ARG_MAX with large PRs (H7 fix)
    except RuntimeError as _e:
        # Match GitHub error messages for oversized diffs regardless of exact phrasing. (L3 fix)
        _e_str = str(_e).lower()
        if "too large" in _e_str or "too big" in _e_str or "exceeded" in _e_str:
            files_raw = await _agh(["api", f"repos/{REPO_SLUG}/pulls/{pr_number}/files?per_page=100"])
            files = json.loads(files_raw)
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

    issue_body = await _agh(["issue", "view", str(issue_number), "--repo", REPO_SLUG, "--json", "body", "--jq", ".body"])
    issue_body = issue_body[:4000]  # guard ARG_MAX and limit prompt injection surface (H7 fix)

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

    # Use router for review provider (MEDIUM-3 fix: consistent with implement/fix_ci)
    _review_providers = router.providers_for("review")
    if not _review_providers:
        raise RuntimeError("No review providers configured — DEEPSEEK_API_KEY required")

    _review_p = _review_providers[0]
    # On retry, use AUTODEV_REVIEW_MODEL_RETRY env var if set, else fall back to
    # the provider's default model. Avoids hardcoding "deepseek-v4-pro" which is
    # wrong for non-DeepSeek providers (e.g. modelscope). (H-model fix)
    _is_retry = activity.info().attempt > 1
    _review_model = (
        os.environ.get("AUTODEV_REVIEW_MODEL_RETRY", _review_p.model)
        if _is_retry
        else os.environ.get("DEEPSEEK_REVIEW_MODEL", _review_p.model)
    )
    activity.logger.info("review_pr_activity attempt=%d model=%s", activity.info().attempt, _review_model)
    _review_env: dict[str, str] = {
        "HOME": str(Path.home()),
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),  # L1 fix: KeyError if PATH stripped
        "OPENAI_API_KEY": _review_p.api_key,
        "https_proxy": GFW_PROXY,
        "http_proxy": GFW_PROXY,
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
    }
    if "CODEX_HOME" in os.environ:
        _review_env["CODEX_HOME"] = os.environ["CODEX_HOME"]
    # Cap prompt at 60 KB to prevent E2BIG on exec when prompt contains CJK content
    # (UTF-8 encodes CJK as 3 bytes; 20K CJK chars ≈ 60KB). (H5 fix)
    _prompt_bytes = prompt.encode("utf-8", errors="replace")
    if len(_prompt_bytes) > 60000:
        # Walk back from the cut point to a valid UTF-8 lead byte to avoid splitting
        # multi-byte CJK characters and producing replacement-char salad. (L3 fix)
        _cut = 60000
        while _cut > 0 and (_prompt_bytes[_cut] & 0xC0) == 0x80:
            _cut -= 1
        prompt = _prompt_bytes[:_cut].decode("utf-8", errors="replace")
    output = await _arun(
        [
            "qwen", prompt,
            "--auth-type", "openai",
            "--openai-base-url", _review_p.base_url,
            "--model", _review_model,
            "-y",
            "--output-format", "text",
            "--max-session-turns", "5",
            "--channel", "CI",
            "--bare",
        ],
        env=_review_env,
        timeout=600,
    )

    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    decision = "REQUEST_CHANGES"
    # Prefer an exact-match line first (LLM output that is exactly the decision word).
    # Regex fallback checks only the FIRST non-empty line — a match buried in the review
    # body (e.g. "I APPROVE of the approach") must not override a leading REQUEST_CHANGES. (L4 fix)
    for _ln in lines:
        if _ln in ("APPROVE", "REQUEST_CHANGES"):
            decision = _ln
            break
    else:
        if lines:
            _m = _DECISION_RE.search(lines[0])
            if _m:
                decision = _m.group(1)

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
    """Post GitHub review comment. APPROVE labels PR; REQUEST_CHANGES closes it."""
    body_lines = review_output.splitlines()
    # Cap at 30000 chars to stay well under GitHub's 65535-char comment limit. (M3 fix)
    detail = "\n".join(body_lines[1:]).strip()[:30000] if len(body_lines) > 1 else ""
    # Use pr_number-scoped marker so duplicate detection works across workflow retries. (H10 fix)
    marker = f"<!-- autodev-review-pr-{pr_number} -->"
    review_body = (
        f"### autodev-review: {decision}\n\n{detail}\n\n---\n"
        f"*Reviewed by autodev-train – Temporal worker – Qwen Code + DeepSeek v4.0 Pro*\n"
        f"{marker}"
    )

    already_posted = False
    try:
        existing = await _agh([
            "pr", "view", str(pr_number), "--repo", REPO_SLUG,
            "--json", "comments", "--jq", "[.comments[].body] | join(\"\\n\")",
        ])
        already_posted = marker in existing
    except RuntimeError:
        pass
    if not already_posted:
        await _agh([
            "pr", "comment", str(pr_number),
            "--repo", REPO_SLUG,
            "--body", review_body,
        ])

    if decision == "APPROVE":
        # Only post label if not already present to avoid duplicate API calls. (LOW-5 fix)
        try:
            existing_labels_raw = await _agh([
                "pr", "view", str(pr_number), "--repo", REPO_SLUG,
                "--json", "labels", "--jq", "[.labels[].name]",
            ])
            existing_labels = json.loads(existing_labels_raw)
        except RuntimeError:
            existing_labels = []
        if "review-passed" not in existing_labels:
            await _agh([
                "api", "-X", "POST",
                f"repos/{REPO_SLUG}/issues/{pr_number}/labels",
                "-f", "labels[]=review-passed",
            ])
        # Clear any stale error from prior stages. (MEDIUM-7 / HIGH-5 fix)
        db.upsert_run(issue_number, stage="approved", error=None)
    else:
        try:
            await _agh(["pr", "close", str(pr_number), "--repo", REPO_SLUG])
        except RuntimeError:
            pass
        try:
            await _agh(["issue", "close", str(issue_number), "--repo", REPO_SLUG,
                        "--comment",
                        f"Closed: autodev-train PR #{pr_number} received REQUEST_CHANGES and was not merged. "
                        "Re-open this issue to retry implementation."])
            await _agh(["issue", "edit", str(issue_number), "--repo", REPO_SLUG,
                        "--add-label", "autodev-failed"])
        except RuntimeError as _e:
            activity.logger.warning("Failed to close issue #%d: %s", issue_number, str(_e)[:200])
        # Write meaningful error so DB doesn't retain stale error from a prior stage. (HIGH-5 fix)
        db.upsert_run(issue_number, stage="failed",
                      error="REQUEST_CHANGES — autodev reviewer rejected implementation")
        # Gate on stage_events idempotency marker — _retry_5 would dispatch auto-loop.yml
        # on every retry attempt, multiplying the implement load. (H6 fix)
        # Write the marker BEFORE dispatching (H7 fix): if dispatch fails, no spurious retry;
        # if dispatch succeeds but a crash prevents DB write, we accept one missed trigger.
        try:
            if not db.has_event(issue_number, "post_review", "auto_loop_dispatched"):
                db.log_event(issue_number, "post_review", "auto_loop_dispatched", f"pr={pr_number}")
                await _agh(["workflow", "run", "auto-loop.yml", "--repo", REPO_SLUG, "--ref", "main"])
        except RuntimeError as _e:
            activity.logger.error("Failed to trigger auto-loop.yml workflow: %s", str(_e)[:200])
            db.log_event(issue_number, "post_review", "auto_loop_dispatch_failed", str(_e)[:200])  # L5 fix

    db.log_event(issue_number, "post_review", "completed", f"decision={decision}")
    return {"posted": True}
