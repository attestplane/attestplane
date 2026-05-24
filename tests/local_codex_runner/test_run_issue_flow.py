from pathlib import Path

from scripts.local_codex_runner.config import RunnerConfig
from scripts.local_codex_runner.models import RunnerResult, RunnerStatus
from scripts.local_codex_runner.run_issue import append_residual_risk, parse_pr_number, run_issue


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


def test_append_residual_risk_preserves_legacy_string_value() -> None:
    result = RunnerResult(
        issue_number=127,
        branch=None,
        pr_url=None,
        status=RunnerStatus.LOCAL_FAILED,
        plan_path=None,
        evidence_dir="evidence",
    )
    result.residual_risks = "legacy scalar risk"  # type: ignore[assignment]

    append_residual_risk(result, "new exception")

    assert result.residual_risks == ["legacy scalar risk", "new exception"]


def test_parse_pr_number_from_github_url() -> None:
    assert parse_pr_number("https://github.com/attestplane/attestplane/pull/202") == 202
    assert parse_pr_number("https://github.com/attestplane/attestplane/pull/202/") == 202
    assert parse_pr_number(None) is None
    assert parse_pr_number("not-a-pr-url") is None
