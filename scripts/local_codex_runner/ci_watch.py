#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""GitHub CI watch helpers for local Codex PRs."""

from __future__ import annotations

import time
from dataclasses import dataclass

from scripts.local_codex_runner.github_cli import CheckStatus, GitHubCLI


@dataclass(frozen=True)
class CIWatchResult:
    status: str
    summary: str
    checks: list[CheckStatus]


def summarize_checks(checks: list[CheckStatus]) -> str:
    if not checks:
        return "No checks returned by gh pr checks."
    return "\n".join(
        f"- {check.name}: {check.bucket or check.state} {check.link or ''}".rstrip()
        for check in checks
    )


def classify_checks(checks: list[CheckStatus]) -> str:
    buckets = {check.bucket for check in checks}
    if buckets and buckets <= {"pass", "skipping"}:
        return "PASS"
    if buckets.intersection({"fail", "cancel"}):
        return "FAIL"
    return "PENDING"


def wait_for_ci(
    gh: GitHubCLI,
    *,
    repo: str,
    pr_number_or_branch: str,
    timeout_seconds: int,
    poll_seconds: int,
) -> CIWatchResult:
    deadline = time.monotonic() + timeout_seconds
    checks: list[CheckStatus] = []
    last_failure_summary: str | None = None
    while time.monotonic() <= deadline:
        checks = gh.pr_checks(repo, pr_number_or_branch)
        status = classify_checks(checks)
        summary = summarize_checks(checks)
        if status == "PASS":
            return CIWatchResult(status=status, summary=summary, checks=checks)
        if status == "FAIL":
            if (
                last_failure_summary == summary
                or poll_seconds <= 0
                or time.monotonic() + poll_seconds > deadline
            ):
                return CIWatchResult(status=status, summary=summary, checks=checks)
            last_failure_summary = summary
            time.sleep(poll_seconds)
            continue
        last_failure_summary = None
        time.sleep(poll_seconds)
    return CIWatchResult(
        status="TIMEOUT", summary=summarize_checks(checks), checks=checks
    )
