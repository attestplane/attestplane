import subprocess

import pytest

from scripts.local_codex_runner.github_cli import GitHubCLI, RunnerCommandError, redact


def test_issue_list_json_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command, capture_output, text, check):
        assert command[:3] == ["gh", "issue", "list"]
        assert "open" in command
        return subprocess.CompletedProcess(command, 0, '[{"number":7,"title":"Fix","url":"u","body":"b","labels":[{"name":"auto-codex-approved"}]}]', "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    issues = GitHubCLI(dry_run=False).list_issues("o/r", "auto-codex-approved", 10)

    assert issues[0].number == 7
    assert issues[0].labels == ["auto-codex-approved"]


def test_issue_list_can_include_closed_siblings(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command, capture_output, text, check):
        assert command[command.index("--state") + 1] == "all"
        return subprocess.CompletedProcess(command, 0, "[]", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert GitHubCLI(dry_run=False).list_issues("o/r", "planned-task", 100, state="all") == []


def test_label_add_dry_run_does_not_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(subprocess, "run", fake_run)

    GitHubCLI(dry_run=True).add_labels("o/r", 1, ["codex-in-progress"])

    assert called is False


def test_label_add_creates_missing_runner_labels_and_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []

    def fake_run(command, capture_output, text, check):
        commands.append(command)
        if command[:3] == ["gh", "issue", "edit"] and len(commands) == 1:
            return subprocess.CompletedProcess(
                command,
                1,
                "",
                "failed to update issue: 'codex-recovered' not found",
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    GitHubCLI(dry_run=False).add_labels("o/r", 108, ["codex-recovered", "codex-ci-green"])

    assert commands[0][:3] == ["gh", "issue", "edit"]
    assert commands[1][:3] == ["gh", "label", "create"]
    assert commands[2][:3] == ["gh", "label", "create"]
    assert commands[3][:3] == ["gh", "issue", "edit"]


def test_pr_checks_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command, capture_output, text, check):
        return subprocess.CompletedProcess(command, 0, '[{"name":"ci","state":"SUCCESS","bucket":"pass","link":"https://example"}]', "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    checks = GitHubCLI(dry_run=False).pr_checks("o/r", "branch")

    assert checks[0].bucket == "pass"


def test_pr_list_json_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command, capture_output, text, check):
        assert command[:3] == ["gh", "pr", "list"]
        return subprocess.CompletedProcess(command, 0, '[{"number":126,"title":"Fix","labels":[{"name":"auto-merge-ready"}]}]', "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    prs = GitHubCLI(dry_run=False).list_pull_requests("o/r", "main", 10)

    assert prs[0]["number"] == 126


def test_merge_pr_dry_run_does_not_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(subprocess, "run", fake_run)

    GitHubCLI(dry_run=True).merge_pr("o/r", 126)

    assert called is False


def test_secret_redaction() -> None:
    assert "ghp_x" not in redact("ghp_x")
    assert "[REDACTED]" in redact("token=x")


def test_command_failure_redacts_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command, capture_output, text, check):
        return subprocess.CompletedProcess(command, 1, "", "token=x")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RunnerCommandError) as excinfo:
        GitHubCLI(dry_run=False).current_auth_status()

    assert "github_pat" not in str(excinfo.value)
