import subprocess
from pathlib import Path

from scripts.local_codex_runner.run_once import cleanup_stale_state, run_once


def test_cleanup_stale_state_prunes_closed_active_issues(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(
        "{\n"
        '  "active_issue_ids": [118, 125, 141],\n'
        '  "branch_mappings": {"118": "codex/118", "125": "codex/125", "141": "codex/141", "note": "legacy"},\n'
        '  "last_result": null,\n'
        '  "processed_issue_ids": [],\n'
        '  "retry_counts": {}\n'
        "}\n",
        encoding="utf-8",
    )

    class FakeGH:
        def __init__(self) -> None:
            self.states = {118: "CLOSED", 125: "CLOSED", 141: "OPEN"}

        def view_issue_state(self, repo: str, issue_number: int) -> str:
            return self.states[issue_number]

    from scripts.local_codex_runner.config import RunnerConfig

    config = RunnerConfig(repo="o/r", workdir=str(tmp_path), state_path="state.json")
    summary = cleanup_stale_state(config, FakeGH())  # type: ignore[arg-type]

    assert summary["invalid_branch_keys"] == ["note"]
    assert summary["pruned_closed_issues"] == [118, 125]
    assert state_path.read_text(encoding="utf-8").count("codex/141") == 1
    assert "codex/118" not in state_path.read_text(encoding="utf-8")


def test_cleanup_stale_state_reports_github_errors_without_crashing(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(
        "{\n"
        '  "active_issue_ids": [103],\n'
        '  "branch_mappings": {"103": "codex/103"},\n'
        '  "last_result": null,\n'
        '  "processed_issue_ids": [],\n'
        '  "retry_counts": {}\n'
        "}\n",
        encoding="utf-8",
    )

    from scripts.local_codex_runner.config import RunnerConfig
    from scripts.local_codex_runner.github_cli import RunnerCommandError

    class FailingGH:
        def view_issue_state(self, repo: str, issue_number: int) -> str:
            raise RunnerCommandError(
                ["gh", "issue", "view", str(issue_number)],
                1,
                "proxyconnect tcp: dial tcp 127.0.0.1:7897: connect: connection refused",
            )

    config = RunnerConfig(repo="o/r", workdir=str(tmp_path), state_path="state.json")
    summary = cleanup_stale_state(config, FailingGH())  # type: ignore[arg-type]

    assert summary["pruned_closed_issues"] == []
    assert summary["kept"] == []
    assert summary["external_errors"][0]["issue"] == 103
    assert "proxyconnect tcp" in summary["external_errors"][0]["error"]
    assert "codex/103" in state_path.read_text(encoding="utf-8")


def test_run_once_uses_configured_lane_filters(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "runner.yml"
    config_path.write_text(
        'repo: "o/r"\n'
        f'workdir: "{tmp_path}"\n'
        "dry_run: true\n"
        "cleanup_stale_state: false\n"
        'lane_name: "p0"\n'
        "lane_slot: 1\n"
        "max_issues_per_run: 1\n"
        "lane_include_labels:\n"
        '  - "priority-P0"\n',
        encoding="utf-8",
    )

    from scripts.local_codex_runner.models import IssueTask, RunnerResult, RunnerStatus

    class FakeGH:
        def __init__(self, dry_run=True):
            pass

        def list_issues(self, repo: str, label: str, limit: int):
            return [
                IssueTask(1, "[P1][sdk] SDK", "", "", ["auto-codex-approved", "priority:P1"]),
                IssueTask(2, "[P0][release] Release", "", "", ["auto-codex-approved", "priority-P0"]),
            ]

    processed: list[int] = []

    def fake_run_issue(config, issue_number, include, exclude):
        processed.append(issue_number)
        assert include == {"priority-P0"}
        return RunnerResult(
            issue_number=issue_number,
            branch=None,
            pr_url=None,
            status=RunnerStatus.DRY_RUN,
            plan_path=None,
            evidence_dir="evidence",
        )

    monkeypatch.setattr("scripts.local_codex_runner.run_once.GitHubCLI", FakeGH)
    monkeypatch.setattr("scripts.local_codex_runner.run_once.run_issue", fake_run_issue)
    monkeypatch.setattr(
        "scripts.local_codex_runner.run_once.recover_needs_human_for_labels",
        lambda config, gh, include_labels=None, exclude_labels=None: {"enabled": False, "results": []},
    )

    result = run_once(type("Args", (), {"config": config_path, "include_label": [], "exclude_label": []})())

    assert processed == [2]
    assert result["lane"] == {
        "include_labels": ["priority-P0"],
        "exclude_labels": [],
        "name": "p0",
        "slot": 1,
    }
    assert result["needs_human_recovery"] == {"enabled": False, "results": []}


def test_run_once_reports_needs_human_recovery(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "runner.yml"
    config_path.write_text(
        'repo: "o/r"\n'
        f'workdir: "{tmp_path}"\n'
        "dry_run: true\n"
        "cleanup_stale_state: false\n"
        "max_issues_per_run: 0\n",
        encoding="utf-8",
    )

    class FakeGH:
        def __init__(self, dry_run=True):
            pass

        def list_issues(self, repo: str, label: str, limit: int):
            return []

    monkeypatch.setattr("scripts.local_codex_runner.run_once.GitHubCLI", FakeGH)
    monkeypatch.setattr(
        "scripts.local_codex_runner.run_once.recover_needs_human_for_labels",
        lambda config, gh, include_labels=None, exclude_labels=None: {
            "enabled": True,
            "results": [{"issue_number": 1, "action": "kept"}],
        },
    )

    result = run_once(type("Args", (), {"config": config_path, "include_label": [], "exclude_label": []})())

    assert result["needs_human_recovery"] == {
        "enabled": True,
        "results": [{"issue_number": 1, "action": "kept"}],
    }


def test_run_once_recovers_needs_human_before_cleaning_transient_evidence(monkeypatch, tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    evidence_dir = tmp_path / "docs/validation/local_codex_runner/issue-14"
    evidence_dir.mkdir(parents=True)
    failure_file = evidence_dir / "failure.txt"
    failure_file.write_text("Codex usage limit reached; try again later\n", encoding="utf-8")
    config_path = tmp_path / "runner.yml"
    config_path.write_text(
        'repo: "o/r"\n'
        f'workdir: "{tmp_path}"\n'
        "dry_run: false\n"
        "cleanup_stale_state: false\n"
        "auto_recover_needs_human: true\n"
        "max_issues_per_run: 0\n",
        encoding="utf-8",
    )

    from scripts.local_codex_runner.models import IssueTask

    class FakeGH:
        def __init__(self, dry_run=True):
            self.issues = [IssueTask(14, "Issue 14", "", "", ["auto-codex-approved", "codex-needs-human"])]

        def list_issues(self, repo: str, label: str, limit: int):
            return self.issues if label == "codex-needs-human" else []

        def list_pull_requests(self, repo: str, base: str, limit: int):
            return []

        def ensure_labels(self, repo: str, labels: list[str]) -> None:
            pass

        def add_labels(self, repo: str, issue_number: int, labels: list[str]) -> None:
            pass

        def remove_labels(self, repo: str, issue_number: int, labels: list[str]) -> None:
            pass

        def comment_issue(self, repo: str, issue_number: int, body: str) -> None:
            pass

    monkeypatch.setattr("scripts.local_codex_runner.run_once.GitHubCLI", FakeGH)

    result = run_once(type("Args", (), {"config": config_path, "include_label": [], "exclude_label": []})())

    assert result["needs_human_recovery"]["results"][0]["reason"] == "rate_limit"
    assert result["transient_cleanup"] == ["docs/validation/local_codex_runner/issue-14/failure.txt"]
    assert not failure_file.exists()


def test_run_once_cleans_transient_result_files_before_live_cycle(monkeypatch, tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    evidence_dir = tmp_path / "docs/validation/local_codex_runner/issue-9"
    evidence_dir.mkdir(parents=True)
    result_file = evidence_dir / "runner_result.json"
    result_file.write_text("{}\n", encoding="utf-8")
    config_path = tmp_path / "runner.yml"
    config_path.write_text(
        'repo: "o/r"\n'
        f'workdir: "{tmp_path}"\n'
        "dry_run: false\n"
        "cleanup_stale_state: false\n"
        "auto_recover_needs_human: false\n"
        "auto_advance_before_consume: false\n"
        "max_issues_per_run: 0\n",
        encoding="utf-8",
    )

    class FakeGH:
        def __init__(self, dry_run=True):
            pass

        def list_issues(self, repo: str, label: str, limit: int):
            return []

    monkeypatch.setattr("scripts.local_codex_runner.run_once.GitHubCLI", FakeGH)

    result = run_once(type("Args", (), {"config": config_path, "include_label": [], "exclude_label": []})())

    assert result["transient_cleanup"] == ["docs/validation/local_codex_runner/issue-9/runner_result.json"]
    assert not result_file.exists()


def test_run_once_reports_issue_list_external_error(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "runner.yml"
    config_path.write_text(
        'repo: "o/r"\n'
        f'workdir: "{tmp_path}"\n'
        "dry_run: true\n"
        "cleanup_stale_state: false\n"
        "auto_recover_needs_human: false\n"
        "auto_advance_before_consume: false\n"
        "max_issues_per_run: 1\n",
        encoding="utf-8",
    )

    from scripts.local_codex_runner.github_cli import RunnerCommandError

    class FailingGH:
        def __init__(self, dry_run=True):
            pass

        def list_issues(self, repo: str, label: str, limit: int):
            raise RunnerCommandError(
                ["gh", "issue", "list"],
                1,
                'Post "https://api.github.com/graphql": EOF',
            )

    monkeypatch.setattr("scripts.local_codex_runner.run_once.GitHubCLI", FailingGH)

    result = run_once(type("Args", (), {"config": config_path, "include_label": [], "exclude_label": []})())

    assert result["processed"] == 0
    assert result["results"] == []
    assert result["external_errors"][0]["stage"] == "list_issues"
    assert "api.github.com/graphql" in result["external_errors"][0]["error"]
