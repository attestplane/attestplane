#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

import subprocess

from scripts.local_codex_runner.github_cli import GitHubCLI
from scripts.local_codex_runner.models import IssueTask, candidate_fetch_limit, processable_issues


def issue(number: int, labels: list[str]) -> IssueTask:
    return IssueTask(
        number=number,
        title=f"issue {number}",
        body="",
        url=f"https://example.test/{number}",
        labels=labels,
    )


def test_candidate_fetch_limit_fetches_past_single_cycle_limit() -> None:
    assert candidate_fetch_limit(1) == 20
    assert candidate_fetch_limit(3) == 30
    assert candidate_fetch_limit(1000) == 100


def test_processable_issues_skips_ineligible_queue_head_without_starving_ready_issue() -> None:
    queue = processable_issues(
        [
            issue(141, ["auto-codex-approved", "codex-pr-opened"]),
            issue(140, ["auto-codex-approved", "codex-needs-human"]),
            issue(118, ["auto-codex-approved", "planned-task"]),
            issue(117, ["auto-codex-approved", "planned-task"]),
        ],
        approved_label="auto-codex-approved",
        pr_opened_label="codex-pr-opened",
        needs_human_label="codex-needs-human",
        max_issues_per_run=1,
    )

    assert [task.number for task in queue] == [118]


def test_pr_checks_treats_missing_checks_as_empty(monkeypatch) -> None:
    def fake_run(command, *, capture_output, text, check):  # noqa: ANN001
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="no checks reported on the branch\n")

    monkeypatch.setattr(subprocess, "run", fake_run)

    gh = GitHubCLI(dry_run=False)

    assert gh.pr_checks("attestplane/attestplane", "151") == []
