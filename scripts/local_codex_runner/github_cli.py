#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Small GitHub CLI wrapper with dry-run and redaction support."""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Any

from scripts.local_codex_runner.models import IssueTask


SECRET_PATTERNS = (
    re.compile(r"(ghp_|github_pat_|GITHUB_TOKEN=)[A-Za-z0-9_:\-]+"),
    re.compile(r"(sk-[A-Za-z0-9]{12,})"),
    re.compile(r"(?i)(token|password|secret|cookie)=\S+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
)

READ_RETRY_ATTEMPTS = 3
READ_RETRY_BACKOFF_SECONDS = (1.0, 2.0)
TRANSIENT_GH_STDERR_PATTERNS = (
    "post \"https://api.github.com/graphql\": eof",
    "post \"https://api.github.com/graphql\": unexpected eof",
    "connection reset by peer",
    "i/o timeout",
    "tls handshake timeout",
    "net/http: request canceled",
    "temporary failure in name resolution",
    "502 bad gateway",
    "503 service unavailable",
    "504 gateway timeout",
)


class RunnerCommandError(RuntimeError):
    """Raised when an external runner command fails."""

    def __init__(self, command: list[str], returncode: int, stderr: str) -> None:
        self.command = command
        self.returncode = returncode
        self.stderr = truncate(redact(stderr))
        super().__init__(f"command failed ({returncode}): {' '.join(command)}\n{self.stderr}")


@dataclass(frozen=True)
class CheckStatus:
    name: str
    state: str
    bucket: str
    link: str | None = None


def redact(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def truncate(text: str, limit: int = 20_000) -> str:
    return text if len(text) <= limit else text[:limit] + "\n[truncated]\n"


class GitHubCLI:
    def __init__(self, *, dry_run: bool = True) -> None:
        self.dry_run = dry_run
        self.commands_run: list[str] = []

    def _run(self, command: list[str], *, write: bool = False) -> subprocess.CompletedProcess[str]:
        if self.dry_run and write:
            self.commands_run.append(" ".join(command))
            return subprocess.CompletedProcess(command, 0, stdout="[dry-run]\n", stderr="")
        attempts = 1 if write else READ_RETRY_ATTEMPTS
        last_completed: subprocess.CompletedProcess[str] | None = None
        for attempt in range(attempts):
            self.commands_run.append(" ".join(command))
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            completed.stdout = redact(completed.stdout)
            completed.stderr = redact(completed.stderr)
            if completed.returncode == 0:
                return completed
            last_completed = completed
            if attempt + 1 >= attempts or not is_transient_read_error(command, completed.stderr):
                break
            time.sleep(READ_RETRY_BACKOFF_SECONDS[min(attempt, len(READ_RETRY_BACKOFF_SECONDS) - 1)])
        assert last_completed is not None
        raise RunnerCommandError(command, last_completed.returncode, last_completed.stderr)

    def current_auth_status(self) -> str:
        try:
            return self._run(["gh", "auth", "status"]).stdout
        except RunnerCommandError as exc:
            raise RunnerCommandError(
                exc.command,
                exc.returncode,
                exc.stderr + "\nRun `gh auth login` locally; do not store tokens in runner config.",
            ) from exc

    def list_issues(self, repo: str, label: str, limit: int, *, state: str = "open") -> list[IssueTask]:
        completed = self._run(
            [
                "gh",
                "issue",
                "list",
                "--repo",
                repo,
                "--state",
                state,
                "--label",
                label,
                "--json",
                "number,title,url,labels,body",
                "--limit",
                str(limit),
            ]
        )
        return [IssueTask.from_gh_json(item) for item in json.loads(completed.stdout or "[]")]

    def list_pull_requests(self, repo: str, base: str, limit: int) -> list[dict[str, Any]]:
        completed = self._run(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                repo,
                "--state",
                "open",
                "--base",
                base,
                "--json",
                "number,title,url,author,baseRefName,headRefName,isDraft,mergeStateStatus,reviewDecision,labels",
                "--limit",
                str(limit),
            ]
        )
        loaded = json.loads(completed.stdout or "[]")
        if not isinstance(loaded, list):
            return []
        return [dict(item) for item in loaded]

    def view_pull_request(self, repo: str, pr_number: int) -> dict[str, Any]:
        completed = self._run(
            [
                "gh",
                "pr",
                "view",
                str(pr_number),
                "--repo",
                repo,
                "--json",
                "number,title,url,author,baseRefName,headRefName,isDraft,mergeStateStatus,reviewDecision,labels",
            ]
        )
        loaded = json.loads(completed.stdout or "{}")
        return dict(loaded) if isinstance(loaded, dict) else {}

    def view_issue(self, repo: str, issue_number: int) -> IssueTask:
        completed = self._run(["gh", "issue", "view", str(issue_number), "--repo", repo, "--json", "number,title,url,labels,body"])
        return IssueTask.from_gh_json(json.loads(completed.stdout))

    def view_issue_state(self, repo: str, issue_number: int) -> str:
        completed = self._run(["gh", "issue", "view", str(issue_number), "--repo", repo, "--json", "state"])
        data = json.loads(completed.stdout or "{}")
        return str(data.get("state", "UNKNOWN"))

    def add_labels(self, repo: str, issue_number: int, labels: list[str]) -> None:
        if labels:
            command = ["gh", "issue", "edit", str(issue_number), "--repo", repo, "--add-label", ",".join(labels)]
            try:
                self._run(command, write=True)
            except RunnerCommandError as exc:
                if "not found" not in exc.stderr.lower():
                    raise
                self.ensure_labels(repo, labels)
                self._run(command, write=True)

    def ensure_labels(self, repo: str, labels: list[str]) -> None:
        for label in labels:
            command = [
                "gh",
                "label",
                "create",
                label,
                "--repo",
                repo,
                "--color",
                label_color(label),
                "--description",
                label_description(label),
            ]
            try:
                self._run(command, write=True)
            except RunnerCommandError as exc:
                if "already exists" not in exc.stderr.lower():
                    raise

    def remove_labels(self, repo: str, issue_number: int, labels: list[str]) -> None:
        if labels:
            self._run(["gh", "issue", "edit", str(issue_number), "--repo", repo, "--remove-label", ",".join(labels)], write=True)

    def comment_issue(self, repo: str, issue_number: int, body: str) -> None:
        self._run(["gh", "issue", "comment", str(issue_number), "--repo", repo, "--body", redact(body)], write=True)

    def create_pr(self, repo: str, title: str, body: str, base: str, head: str) -> str:
        completed = self._run(
            ["gh", "pr", "create", "--repo", repo, "--title", title, "--body", redact(body), "--base", base, "--head", head],
            write=True,
        )
        return completed.stdout.strip()

    def merge_pr(self, repo: str, pr_number: int) -> None:
        self._run(["gh", "pr", "merge", str(pr_number), "--repo", repo, "--squash"], write=True)

    def pr_checks(self, repo: str, pr_number_or_branch: str) -> list[CheckStatus]:
        command = ["gh", "pr", "checks", pr_number_or_branch, "--repo", repo, "--json", "name,state,bucket,link"]
        try:
            completed = self._run(command)
        except RunnerCommandError as exc:
            if "no checks reported" not in exc.stderr.lower():
                raise
            return []
        return [check_from_json(item) for item in json.loads(completed.stdout or "[]")]

    def run_view_failed_logs(self, repo: str, pr_number_or_branch: str) -> str:
        failed = [check for check in self.pr_checks(repo, pr_number_or_branch) if check.bucket in {"fail", "cancel"}]
        if not failed:
            return "No failed check links found."
        return "\n".join(["Failed GitHub check links:", *[f"- {check.name}: {check.link or 'no link'}" for check in failed]])


def check_from_json(data: dict[str, Any]) -> CheckStatus:
    return CheckStatus(name=str(data.get("name", "")), state=str(data.get("state", "")), bucket=str(data.get("bucket", "")), link=data.get("link"))


def is_transient_read_error(command: list[str], stderr: str) -> bool:
    if not command or command[0] != "gh":
        return False
    normalized = stderr.lower()
    return any(pattern in normalized for pattern in TRANSIENT_GH_STDERR_PATTERNS)


def label_color(label: str) -> str:
    if label.startswith("codex-"):
        return "5319e7"
    if label.startswith("status:"):
        return "fbca04"
    if label.startswith("priority"):
        return "d73a4a"
    return "bfd4f2"


def label_description(label: str) -> str:
    if label == "codex-recovered":
        return "Recovered by the local Codex runner after a safe retry or stale-state cleanup."
    if label == "codex-ci-green":
        return "Local Codex runner observed green CI for the linked pull request."
    if label.startswith("codex-"):
        return "Managed by the local Codex runner."
    return "Created automatically by the local Codex runner when applying workflow state."
