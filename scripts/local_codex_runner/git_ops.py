#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Git operations for the local Codex runner."""

from __future__ import annotations

import fnmatch
import re
import subprocess
from pathlib import Path

from scripts.local_codex_runner.github_cli import RunnerCommandError, redact, truncate


FORBIDDEN_PATTERNS = (
    ".env",
    "**/.env",
    "*.pem",
    "*.key",
    "secrets.*",
    "**/secrets.*",
    "credentials.*",
    "**/credentials.*",
    ".pypirc",
    "**/.pypirc",
    "**/.npmrc",
    "**/id_rsa",
    "**/id_ed25519",
    "**/*github*token*",
    "**/*release*credential*",
)


class GitOps:
    def __init__(self, workdir: Path) -> None:
        self.workdir = workdir
        self.commands_run: list[str] = []

    def run(self, args: list[str]) -> str:
        command = ["git", *args]
        self.commands_run.append(" ".join(command))
        completed = subprocess.run(command, cwd=self.workdir, capture_output=True, text=True, check=False)
        completed.stdout = redact(completed.stdout)
        completed.stderr = redact(completed.stderr)
        if completed.returncode != 0:
            raise RunnerCommandError(command, completed.returncode, completed.stderr)
        return completed.stdout

    def ensure_clean_worktree(self) -> None:
        if self.run(["status", "--porcelain"]).strip():
            raise GitSafetyError("Worktree is not clean; pass --allow-dirty only for supervised local recovery.")

    def checkout_base_and_pull(self, base_branch: str) -> None:
        self.run(["checkout", base_branch])
        self.run(["pull", "--ff-only", "origin", base_branch])

    def create_branch(self, issue_number: int, title: str) -> str:
        branch = f"codex/issue-{issue_number}-{slugify(title)}"
        self.run(["checkout", "-B", branch])
        return branch

    def current_branch(self) -> str:
        return self.run(["branch", "--show-current"]).strip()

    def has_changes(self) -> bool:
        return bool(self.run(["status", "--porcelain"]).strip())

    def diff_summary(self) -> str:
        return self.run(["diff", "--stat"]) + "\n" + self.run(["diff", "--name-status"])

    def changed_files(self) -> list[str]:
        output = self.run(["diff", "--name-only", "HEAD"])
        return [line.strip() for line in output.splitlines() if line.strip()]

    def diff(self) -> str:
        return self.run(["diff", "HEAD"])

    def ensure_no_forbidden_files_changed(self, files: list[str] | None = None) -> None:
        changed = files if files is not None else self.changed_files()
        forbidden = [path for path in changed if is_forbidden_path(path)]
        if forbidden:
            raise GitSafetyError(f"Forbidden sensitive file change blocked: {', '.join(forbidden)}")

    def commit_all(self, issue_number: int, message: str) -> None:
        branch = self.current_branch()
        if branch in {"main", "master"}:
            raise GitSafetyError("Refusing to commit directly on main/master")
        if not self.has_changes():
            raise GitSafetyError("Refusing to commit an empty diff")
        if f"#{issue_number}" not in message and f"issue {issue_number}" not in message.lower():
            raise GitSafetyError("Commit message must include the issue number")
        self.ensure_no_forbidden_files_changed()
        self.run(["add", "-A"])
        self.run(["commit", "-s", "-m", message])

    def push_branch(self, branch: str) -> None:
        if branch in {"main", "master"}:
            raise GitSafetyError("Refusing to push main/master from runner")
        self.run(["push", "-u", "origin", branch])

    def abort_or_stash_on_failure(self) -> str:
        if not self.has_changes():
            return "no changes to stash"
        return truncate(self.run(["stash", "push", "-u", "-m", "local-codex-runner-failure"]))


class GitSafetyError(RuntimeError):
    """Raised when a git operation would violate runner safety rules."""


def slugify(title: str, *, max_length: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return (slug[:max_length].strip("-") or "task")


def is_forbidden_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in FORBIDDEN_PATTERNS)
