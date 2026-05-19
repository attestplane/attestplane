from pathlib import Path

from scripts.local_codex_runner.config import RunnerConfig
from scripts.local_codex_runner.run_issue import run_issue


def test_run_issue_dry_run_generates_evidence(monkeypatch, tmp_path: Path) -> None:
    class FakeGH:
        def __init__(self, dry_run):
            self.commands_run = []

        def current_auth_status(self):
            return "ok"

        def view_issue(self, repo, issue_number):
            from scripts.local_codex_runner.models import IssueTask

            return IssueTask(issue_number, "Fix test gap", "body", "url", ["auto-codex-approved", "test-gap"])

    monkeypatch.setattr("scripts.local_codex_runner.run_issue.GitHubCLI", FakeGH)
    config = RunnerConfig(repo="o/r", workdir=str(tmp_path), dry_run=True, state_path="state.json")

    result = run_issue(config, 4)

    assert result.status.value == "DRY_RUN"
    assert (tmp_path / "docs/validation/local_codex_runner/issue-4/runner_result.json").exists()
    assert (tmp_path / "docs/validation/local_codex_runner/issue-4/dry_run_actions.md").exists()

