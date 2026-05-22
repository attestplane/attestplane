#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

import subprocess

from scripts.local_codex_runner.gate_runner import GateRunner
from scripts.local_codex_runner.git_ops import GitOps, is_transient_evidence_path
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


def test_git_ops_recovers_detached_head_before_issue_commit(monkeypatch, tmp_path) -> None:
    branch = "codex/issue-154-example"
    current_branch = {"name": ""}
    commands: list[list[str]] = []

    def fake_run(command, *, cwd, capture_output, text, check):  # noqa: ANN001
        assert cwd == tmp_path
        assert capture_output is True
        assert text is True
        assert check is False
        args = command[1:]
        commands.append(args)
        if args == ["branch", "--show-current"]:
            return subprocess.CompletedProcess(command, 0, stdout=current_branch["name"] + "\n", stderr="")
        if args == ["switch", "-C", branch]:
            current_branch["name"] = branch
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if args == ["status", "--porcelain"]:
            return subprocess.CompletedProcess(command, 0, stdout=" M tests/example.py\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    git = GitOps(tmp_path)
    git.commit_all(154, "Fix #154: example", expected_branch=branch)
    git.push_branch(branch)

    assert ["switch", "-C", branch] in commands
    assert ["push", "-u", "origin", f"HEAD:refs/heads/{branch}"] in commands


def test_pr_body_is_transient_runner_evidence() -> None:
    assert is_transient_evidence_path("docs/validation/local_codex_runner/issue-154/pr_body.md")


def test_status_paths_expands_untracked_evidence_directories(monkeypatch, tmp_path) -> None:
    commands: list[list[str]] = []

    def fake_run(command, *, cwd, capture_output, text, check):  # noqa: ANN001
        assert cwd == tmp_path
        args = command[1:]
        commands.append(args)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="?? docs/validation/local_codex_runner/issue-118/01_plan.prompt.md\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    paths = GitOps(tmp_path).status_paths()

    assert commands == [["status", "--porcelain", "--untracked-files=all"]]
    assert paths == [("??", "docs/validation/local_codex_runner/issue-118/01_plan.prompt.md")]


def test_gate_runner_rewrites_default_python_to_project_venv(tmp_path) -> None:
    bin_dir = tmp_path / "sdk/python/.venv/bin"
    bin_dir.mkdir(parents=True)
    python = bin_dir / "python"
    pytest = bin_dir / "pytest"
    python.write_text("", encoding="utf-8")
    pytest.write_text("", encoding="utf-8")

    runner = GateRunner(tmp_path, tmp_path / "missing.yml")

    assert runner.rewrite_for_project_python("python -m compileall scripts").startswith(str(python))
    assert runner.rewrite_for_project_python("pytest -q").startswith(str(pytest))
    assert runner.rewrite_for_project_python("env PYTHONPATH=sdk/python/src pytest tests/observability -q").split()[
        2
    ] == str(pytest)
