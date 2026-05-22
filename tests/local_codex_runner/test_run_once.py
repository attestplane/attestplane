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

    result = run_once(type("Args", (), {"config": config_path, "include_label": [], "exclude_label": []})())

    assert processed == [2]
    assert result["lane"] == {
        "include_labels": ["priority-P0"],
        "exclude_labels": [],
        "name": "p0",
        "slot": 1,
    }
