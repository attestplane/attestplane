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

TRANSIENT_EVIDENCE_PATTERNS = (
    "docs/validation/local_codex_runner/issue-*/*.prompt.md",
    "docs/validation/local_codex_runner/issue-*/codex_*.log",
    "docs/validation/local_codex_runner/issue-*/code.md",
    "docs/validation/local_codex_runner/issue-*/failure.txt",
    "docs/validation/local_codex_runner/issue-*/gate_report.json",
    "docs/validation/local_codex_runner/issue-*/gate_report.md",
    "docs/validation/local_codex_runner/issue-*/plan.md",
    "docs/validation/local_codex_runner/issue-*/pr_body.md",
    "docs/validation/local_codex_runner/issue-*/review.md",
    "docs/validation/local_codex_runner/issue-*/runner_result.json",
    "docs/validation/local_codex_runner/issue-*/runner_result.md",
    "docs/validation/local_codex_runner/issue-*/test.md",
)


class GitOps:
    def __init__(self, workdir: Path) -> None:
        self.workdir = workdir
        self.commands_run: list[str] = []

    def run(self, args: list[str]) -> str:
        command = ["git", *args]
        self.commands_run.append(" ".join(command))
        completed = subprocess.run(  # noqa: S603 - Git command argv is assembled by the runner.
            command,
            cwd=self.workdir,
            capture_output=True,
            text=True,
            check=False,
        )
        completed.stdout = redact(completed.stdout)
        completed.stderr = redact(completed.stderr)
        if completed.returncode != 0:
            raise RunnerCommandError(command, completed.returncode, completed.stderr)
        return completed.stdout

    def ensure_clean_worktree(self) -> None:
        if self.run(["status", "--porcelain"]).strip():
            raise GitSafetyError("Worktree is not clean; pass --allow-dirty only for supervised local recovery.")

    def checkout_base_and_pull(self, base_ref: str) -> None:
        if base_ref.startswith("origin/"):
            remote_branch = base_ref.split("/", 1)[1]
            self.run(["fetch", "origin", remote_branch])
            self.run(["checkout", "--detach", base_ref])
            return
        self.run(["checkout", base_ref])
        self.run(["pull", "--ff-only", "origin", base_ref])

    def checkout_remote_branch(self, branch: str) -> None:
        if branch in {"main", "master"} or not branch.startswith("codex/"):
            raise GitSafetyError(f"Refusing to check out non-runner branch {branch!r}")
        self.run(["fetch", "origin", branch])
        if self.current_branch() == branch and self.has_unpushed_commits(branch):
            return
        self.run(["checkout", "-B", branch, f"origin/{branch}"])

    def has_unpushed_commits(self, branch: str) -> bool:
        if branch in {"main", "master"} or not branch.startswith("codex/"):
            raise GitSafetyError(f"Refusing to inspect non-runner branch {branch!r}")
        count = self.run(["rev-list", "--count", f"origin/{branch}..HEAD"]).strip()
        return int(count or "0") > 0

    def create_branch(self, issue_number: int, title: str) -> str:
        branch = f"codex/issue-{issue_number}-{slugify(title)}"
        self.run(["checkout", "-B", branch])
        return branch

    def current_branch(self) -> str:
        return self.run(["branch", "--show-current"]).strip()

    def ensure_current_branch(self, branch: str) -> None:
        current = self.current_branch()
        if current == branch:
            return
        if current == "":
            self.run(["switch", "-C", branch])
            return
        raise GitSafetyError(f"Refusing to continue on branch {current!r}; expected {branch!r}")

    def has_changes(self) -> bool:
        return bool(self.run(["status", "--porcelain"]).strip())

    def status_paths(self) -> list[tuple[str, str]]:
        output = self.run(["status", "--porcelain", "--untracked-files=all"])
        paths: list[tuple[str, str]] = []
        for line in output.splitlines():
            if not line:
                continue
            status = line[:2]
            path = line[3:]
            if " -> " in path:
                path = path.rsplit(" -> ", 1)[1]
            paths.append((status, path.strip()))
        return paths

    def diff_summary(self) -> str:
        return self.run(["diff", "--stat"]) + "\n" + self.run(["diff", "--name-status"])

    def changed_files(self) -> list[str]:
        return [path for _, path in self.status_paths()]

    def diff(self) -> str:
        return self.run(["diff", "HEAD"])

    def ensure_no_forbidden_files_changed(self, files: list[str] | None = None) -> None:
        changed = files if files is not None else self.changed_files()
        forbidden = [path for path in changed if is_forbidden_path(path)]
        if forbidden:
            raise GitSafetyError(f"Forbidden sensitive file change blocked: {', '.join(forbidden)}")

    def remove_transient_evidence(self) -> list[str]:
        transient = [
            (status, path) for status, path in self.status_paths() if is_transient_evidence_path(path)
        ]
        untracked = [path for status, path in transient if status == "??"]
        tracked = [path for status, path in transient if status != "??"]
        if tracked:
            self.run(["restore", "--worktree", "--staged", "--", *tracked])
        if untracked:
            self.run(["clean", "-f", "--", *untracked])
        return tracked + untracked

    def commit_all(self, issue_number: int, message: str, *, expected_branch: str | None = None) -> None:
        if expected_branch is not None:
            self.ensure_current_branch(expected_branch)
        branch = self.current_branch()
        if branch in {"main", "master"}:
            raise GitSafetyError("Refusing to commit directly on main/master")
        if not self.has_changes():
            raise GitSafetyError("Refusing to commit an empty diff")
        if f"#{issue_number}" not in message and f"issue {issue_number}" not in message.lower():
            raise GitSafetyError("Commit message must include the issue number")
        self.remove_transient_evidence()
        if not self.has_changes():
            raise GitSafetyError("Refusing to commit only transient runner evidence")
        self.ensure_no_forbidden_files_changed()
        self.run(["add", "-A"])
        self.run(["commit", "-s", "-m", message])

    def push_branch(self, branch: str) -> None:
        self.ensure_current_branch(branch)
        if branch in {"main", "master"}:
            raise GitSafetyError("Refusing to push main/master from runner")
        self.run(["push", "-u", "origin", f"HEAD:refs/heads/{branch}"])

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


def is_transient_evidence_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in TRANSIENT_EVIDENCE_PATTERNS)
