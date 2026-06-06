# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
"""Shared shell helpers, constants, and utilities for all autodev activities."""

import asyncio
import logging
import os
import re
import subprocess
from pathlib import Path

# Redact auth tokens from subprocess error output before it enters Temporal event history. (H3 fix)
_SECRET_RE = re.compile(
    r"((?:Authorization|Bearer|api[_-]?key|password|token)[\s:=]+)\S+",
    re.IGNORECASE,
)


def _redact(text: str) -> str:
    return _SECRET_RE.sub(r"\1[REDACTED]", text)

_log = logging.getLogger("autodev.activities")

# ── environment ────────────────────────────────────────────────────────────────
REPO_URL = "https://github.com/attestplane/attestplane.git"
REPO_SLUG = "attestplane/attestplane"
MAIN_REPO = Path(os.environ.get("AUTODEV_MAIN_REPO", Path.home() / "projects/attestplane"))
QWEN_MODEL = os.environ.get("QWEN_MODEL", "deepseek-v4-flash")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
BOT_NAME = "autodev-bot"
BOT_EMAIL = "258170091+merchloubna70-dot@users.noreply.github.com"
GFW_PROXY = "http://127.0.0.1:7897"

# Word-boundary regex to avoid false positives like "contest-load" matching "test". (L4/M5 fix)
_CRITICAL_FAIL_RE = re.compile(r"\b(pytest|mypy|ruff|typecheck|tests?|type-check)\b")


def _is_critical_check(name: str) -> bool:
    """Return True if a failed CI check name indicates a blocking test/lint failure."""
    n = name.lower()
    # Skip deployment/publish checks that happen to contain "test" in their name.
    if any(skip in n for skip in ("deploy", "build-and-", "push-to-", "publish-", "docker")):
        return False
    return bool(_CRITICAL_FAIL_RE.search(n))


def _build_subprocess_env(**overrides: str) -> dict[str, str]:
    """Build a minimal env for restricted subprocesses (qwen/codex) that need git but not API keys.

    Passes through GIT_* and SSH/SSL essentials so git operations inside the subprocess work
    correctly on any host, without leaking DEEPSEEK_API_KEY, GH_TOKEN, or other worker secrets.
    Callers layer their own OPENAI_API_KEY and proxy settings on top via **overrides. (H1 fix)
    """
    _passthrough = {
        k: v for k, v in os.environ.items()
        if k.startswith("GIT_") or k in (
            "SSH_AUTH_SOCK", "SSL_CERT_FILE", "SSL_CERT_DIR",
            "XDG_CONFIG_HOME", "USER", "USERNAME",
        )
    }
    env: dict[str, str] = {
        "HOME": str(Path.home()),
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        **_passthrough,
    }
    env.update(overrides)
    return env


def _run(
    cmd: list[str],
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 60,
) -> str:
    # When env is provided, use it AS-IS — caller is responsible for including
    # the vars they need.  When env is None, use a scrubbed env that passes git/SSH
    # essentials without leaking DEEPSEEK_API_KEY, GH_TOKEN, or other worker secrets
    # to subprocesses that don't need them (e.g. plain git fetch/push). (H3 fix)
    final_env = env if env is not None else _build_subprocess_env()
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=final_env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        cmd_name = cmd[0] if cmd else "?"
        raise RuntimeError(f"cmd={cmd_name!r} timed out after {timeout}s")
    if result.returncode != 0:
        # Only log the command NAME, never the full arg list — args may contain
        # multi-KB prompts or API keys that would pollute Temporal event history
        # and hit the 2 MB event payload limit. (H3 fix)
        cmd_display = cmd[0] if cmd else "?"
        raise RuntimeError(
            f"cmd={cmd_display!r} exit={result.returncode}\n"
            f"stdout: {_redact(result.stdout.strip())[-800:]}\n"
            f"stderr: {_redact(result.stderr.strip())[-800:]}"
        )
    return result.stdout.strip()


async def _arun(
    cmd: list[str],
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 60,
) -> str:
    """Async wrapper around _run: offloads subprocess to a thread so the event loop
    is never blocked by git fetch/push/commit or other shell commands. (CRITICAL-1 fix)"""
    return await asyncio.to_thread(_run, cmd, cwd=cwd, env=env, timeout=timeout)


async def _arun_git_fetch(*args: str, cwd: str | None = None, timeout: int = 60) -> str:
    """git fetch with 3-attempt exponential retry for .git/index.lock contention.

    Multiple concurrent implement/fix_ci activities may race on the shared MAIN_REPO
    git index when a previous lock file was not cleaned up. (M5 fix)
    """
    cmd = ["git", "fetch", *args]
    for _i in range(3):
        try:
            return await _arun(cmd, cwd=cwd, timeout=timeout)
        except RuntimeError as _e:
            if "index.lock" in str(_e).lower() and _i < 2:
                await asyncio.sleep(5 * (_i + 1))
                continue
            raise
    raise RuntimeError("unreachable")


def _gh(args: list[str], **kwargs) -> str:
    token = os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", ""))
    # gh CLI needs the full process environment (git, PATH, SSH, etc.).
    return _run(["gh", *args], env={"GH_TOKEN": token, **os.environ}, **kwargs)


async def _agh(args: list[str], **kwargs) -> str:
    """Async version of _gh — offloads to thread pool. (CRITICAL-1 fix)"""
    token = os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", ""))
    return await _arun(["gh", *args], env={"GH_TOKEN": token, **os.environ}, **kwargs)


def _purge_whitespace_only_changes(worktree: str) -> None:
    """Reset files whose only changes are whitespace/formatting or file-mode (no semantic diff)."""
    if not Path(worktree).exists():
        return  # qwen may have removed the worktree dir; skip silently
    # Use HEAD (not bare diff) to cover both staged and unstaged changes.
    # qwen in --approval-mode yolo may self-git-add files; `git diff` without HEAD
    # only shows unstaged changes and would miss staged whitespace noise. (H6 fix)
    all_changed = set(_run(["git", "diff", "HEAD", "--name-only"], cwd=worktree).splitlines())
    semantic_changed = set(
        _run(["git", "diff", "HEAD", "--ignore-all-space", "--name-only"], cwd=worktree).splitlines()
    )
    whitespace_only = all_changed - semantic_changed

    # Also detect mode-only changes (e.g. qwen chmod +x a script): git numstat reports
    # 0 insertions and 0 deletions for such files, yet they appear in the diff. (H3 fix)
    try:
        numstat = _run(["git", "diff", "HEAD", "--numstat"], cwd=worktree)
        zero_content = {
            parts[2]
            for line in numstat.splitlines()
            if len(parts := line.split("\t", 2)) == 3 and parts[0] == "0" and parts[1] == "0"
            and " => " not in parts[2]  # skip "old => new" renames (H4 fix)
            and "{" not in parts[2]  # skip git brace-expand renames "foo/{a => b}.py" (H1 fix)
        }
        whitespace_only = whitespace_only | (zero_content & all_changed)
    except RuntimeError:
        pass

    to_reset = [f for f in whitespace_only if f.strip()]
    if to_reset:
        # Chunk to avoid ARG_MAX when hundreds of files need resetting. (M8 fix)
        _chunk = 50
        for _i in range(0, len(to_reset), _chunk):
            _run(["git", "checkout", "HEAD", "--"] + to_reset[_i:_i + _chunk], cwd=worktree)
