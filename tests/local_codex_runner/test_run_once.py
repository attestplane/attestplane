import subprocess
from pathlib import Path

from scripts.local_codex_runner.run_once import cleanup_stale_state, product_delta_idle_summary, run_once


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


def test_run_once_prioritizes_open_issues_by_title(monkeypatch, tmp_path: Path) -> None:
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

        def list_issues(self, repo: str, label: str | None, limit: int):
            if label is None:
                return [
                    IssueTask(1, "[P1][sdk] SDK", "", "", ["priority:P1"]),
                    IssueTask(2, "[P0][release] Release", "", "", ["priority-P0"]),
                ]
            return []

    processed: list[int] = []

    def fake_run_issue(config, issue_number):
        processed.append(issue_number)
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
    assert result["needs_human_recovery"] == {"enabled": False, "results": []}


def test_run_once_reports_needs_human_recovery_is_disabled(monkeypatch, tmp_path: Path) -> None:
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

        def list_issues(self, repo: str, label: str | None, limit: int):
            return []

    monkeypatch.setattr("scripts.local_codex_runner.run_once.GitHubCLI", FakeGH)

    result = run_once(type("Args", (), {"config": config_path, "include_label": [], "exclude_label": []})())

    assert result["needs_human_recovery"] == {"enabled": False, "results": []}


def test_run_once_cleans_transient_evidence_without_needs_human_recovery(monkeypatch, tmp_path: Path) -> None:
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
        "auto_recover_needs_human: false\n"
        "max_issues_per_run: 0\n",
        encoding="utf-8",
    )

    from scripts.local_codex_runner.models import IssueTask

    class FakeGH:
        def __init__(self, dry_run=True):
            self.issues = [IssueTask(14, "Issue 14", "", "", ["codex-needs-human"])]

        def list_issues(self, repo: str, label: str | None, limit: int):
            return []

    monkeypatch.setattr("scripts.local_codex_runner.run_once.GitHubCLI", FakeGH)

    result = run_once(type("Args", (), {"config": config_path, "include_label": [], "exclude_label": []})())

    assert result["needs_human_recovery"] == {"enabled": False, "results": []}
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

        def list_issues(self, repo: str, label: str | None, limit: int):
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

        def list_issues(self, repo: str, label: str | None, limit: int):
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


def test_product_delta_idle_summary_is_disabled(tmp_path: Path) -> None:
    log = tmp_path / "stable.log"
    log.write_text(
        "autodev-train stable: no product implementation delta since v1.7.6; skipping v1.7.7\n"
        '{"event": "product_delta_skipped", "version": "v1.7.7"}\n'
        '{"event": "product_delta_skipped", "version": "v1.7.8"}\n',
        encoding="utf-8",
    )
    config_path = tmp_path / "runner.yml"
    config_path.write_text(
        'repo: "o/r"\n'
        f'workdir: "{tmp_path}"\n'
        "dry_run: true\n"
        "product_delta_idle_dispatch: false\n"
        f'product_delta_idle_log_glob: "{log}"\n'
        "product_delta_idle_threshold: 2\n",
        encoding="utf-8",
    )

    from scripts.local_codex_runner.config import load_config

    summary = product_delta_idle_summary(load_config(config_path))

    assert summary == {"active": False, "reason": "disabled"}


def test_run_once_product_delta_idle_processes_product_issue_not_support_issue(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log = tmp_path / "stable.log"
    log.write_text(
        '{"event": "product_delta_skipped", "version": "v1.7.7"}\n'
        '{"event": "product_delta_skipped", "version": "v1.7.8"}\n',
        encoding="utf-8",
    )
    config_path = tmp_path / "runner.yml"
    config_path.write_text(
        'repo: "o/r"\n'
        f'workdir: "{tmp_path}"\n'
        "dry_run: true\n"
        "cleanup_stale_state: false\n"
        "auto_advance_before_consume: false\n"
        "product_delta_idle_dispatch: false\n"
        f'product_delta_idle_log_glob: "{log}"\n'
        "max_issues_per_run: 2\n",
        encoding="utf-8",
    )

    from scripts.local_codex_runner.models import IssueTask, RunnerResult, RunnerStatus

    class FakeGH:
        def __init__(self, dry_run=True):
            pass

        def list_issues(self, repo: str, label: str | None, limit: int):
            if label is None:
                return [
                    IssueTask(31, "[P1][runner] Support-only runner task", "", "", ["priority:P1"]),
                    IssueTask(32, "[P1][sdk][verifier] Product implementation task", "Implement SDK verifier behavior.", "", ["priority:P1"]),
                ]
            return []

    processed: list[int] = []

    def fake_run_issue(config, issue_number):
        processed.append(issue_number)
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

    assert processed == [31, 32]
    assert result["product_delta_idle"] == {"active": False, "reason": "disabled"}


def test_run_once_product_delta_idle_creates_recovery_product_task_when_none_exist(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log = tmp_path / "stable.log"
    log.write_text(
        '{"event": "product_delta_skipped", "version": "v1.8.1"}\n'
        '{"event": "product_delta_skipped", "version": "v1.8.1"}\n',
        encoding="utf-8",
    )
    config_path = tmp_path / "runner.yml"
    config_path.write_text(
        'repo: "o/r"\n'
        f'workdir: "{tmp_path}"\n'
        "dry_run: true\n"
        "cleanup_stale_state: false\n"
        "auto_advance_before_consume: false\n"
        "product_delta_idle_dispatch: false\n"
        "product_delta_idle_create_task: false\n"
        f'product_delta_idle_log_glob: "{log}"\n'
        "max_issues_per_run: 1\n",
        encoding="utf-8",
    )

    from scripts.local_codex_runner.models import IssueTask, RunnerResult, RunnerStatus

    class FakeGH:
        def __init__(self, dry_run=True):
            self.issues = [
                IssueTask(
                    30,
                    "[P2][sdk] Existing product task for another lane",
                    "Implement SDK verifier behavior.",
                    "",
                    ["priority:P2"],
                ),
                IssueTask(
                    31,
                    "[P1][runner] Support-only runner task",
                    "Support-only local runner task.",
                    "",
                    ["priority:P1"],
                )
            ]

        def list_issues(self, repo: str, label: str | None, limit: int):
            if label is None:
                return self.issues
            return []

    processed: list[int] = []

    def fake_run_issue(config, issue_number):
        processed.append(issue_number)
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

    assert result["product_delta_recovery"] == {"enabled": False, "reason": "disabled"}
    assert processed == [31]


def test_run_once_product_delta_idle_keeps_lane_product_task_when_it_is_open(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log = tmp_path / "stable.log"
    log.write_text(
        '{"event": "product_delta_skipped", "version": "v1.8.1"}\n'
        '{"event": "product_delta_skipped", "version": "v1.8.1"}\n',
        encoding="utf-8",
    )
    config_path = tmp_path / "runner.yml"
    config_path.write_text(
        'repo: "o/r"\n'
        f'workdir: "{tmp_path}"\n'
        "dry_run: true\n"
        "cleanup_stale_state: false\n"
        "auto_advance_before_consume: false\n"
        "product_delta_idle_dispatch: false\n"
        "product_delta_idle_create_task: false\n"
        f'product_delta_idle_log_glob: "{log}"\n'
        "max_issues_per_run: 1\n",
        encoding="utf-8",
    )

    from scripts.local_codex_runner.models import IssueTask, RunnerResult, RunnerStatus

    processed: list[int] = []

    class FakeGH:
        def __init__(self, dry_run=True):
            self.issues = [
                IssueTask(
                    32,
                    "[P1][sdk][verifier] Product implementation task",
                    "Implement SDK verifier behavior.",
                    "",
                    ["priority:P1"],
                )
            ]

        def list_issues(self, repo: str, label: str | None, limit: int):
            if label is None:
                return self.issues
            return []

    def fake_run_issue(config, issue_number):
        processed.append(issue_number)
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

    assert result["product_delta_recovery"] == {"enabled": False, "reason": "disabled"}
    assert processed == [32]


def test_run_once_product_delta_idle_keeps_approved_lane_product_task_without_duplicate(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log = tmp_path / "stable.log"
    log.write_text(
        '{"event": "product_delta_skipped", "version": "v1.8.1"}\n'
        '{"event": "product_delta_skipped", "version": "v1.8.1"}\n',
        encoding="utf-8",
    )
    config_path = tmp_path / "runner.yml"
    config_path.write_text(
        'repo: "o/r"\n'
        f'workdir: "{tmp_path}"\n'
        "dry_run: true\n"
        "cleanup_stale_state: false\n"
        "auto_advance_before_consume: false\n"
        "product_delta_idle_dispatch: false\n"
        "product_delta_idle_create_task: false\n"
        f'product_delta_idle_log_glob: "{log}"\n'
        "max_issues_per_run: 1\n",
        encoding="utf-8",
    )

    from scripts.local_codex_runner.models import IssueTask, RunnerResult, RunnerStatus

    processed: list[int] = []

    class FakeGH:
        def __init__(self, dry_run=True):
            self.issues = [
                IssueTask(
                    32,
                    "[P1][sdk][verifier] Product implementation task",
                    "Implement SDK verifier behavior.",
                    "",
                    ["priority:P1"],
                )
            ]

        def list_issues(self, repo: str, label: str | None, limit: int):
            if label is None:
                return self.issues
            return []

        def add_labels(self, repo: str, issue_number: int, labels: list[str]) -> None:
            raise AssertionError("product delta recovery is disabled")

        def create_issue(self, repo: str, title: str, body: str, labels: list[str]) -> str:
            raise AssertionError("product delta recovery is disabled")

    def fake_run_issue(config, issue_number):
        processed.append(issue_number)
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

    assert result["product_delta_recovery"] == {"enabled": False, "reason": "disabled"}
    assert processed == [32]


def test_run_once_product_delta_idle_consumes_approved_product_task_outside_candidate_window(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log = tmp_path / "stable.log"
    log.write_text(
        '{"event": "product_delta_skipped", "version": "v1.8.1"}\n'
        '{"event": "product_delta_skipped", "version": "v1.8.1"}\n',
        encoding="utf-8",
    )
    config_path = tmp_path / "runner.yml"
    config_path.write_text(
        'repo: "o/r"\n'
        f'workdir: "{tmp_path}"\n'
        "dry_run: true\n"
        "cleanup_stale_state: false\n"
        "auto_advance_before_consume: false\n"
        "product_delta_idle_dispatch: false\n"
        "product_delta_idle_create_task: false\n"
        f'product_delta_idle_log_glob: "{log}"\n'
        "max_issues_per_run: 1\n",
        encoding="utf-8",
    )

    from scripts.local_codex_runner.models import IssueTask, RunnerResult, RunnerStatus

    processed: list[int] = []

    class FakeGH:
        def __init__(self, dry_run=True):
            self.product_issue = IssueTask(
                67,
                "[P1][sdk][verifier] Old approved product implementation task",
                "Implement SDK verifier behavior.",
                "",
                ["priority:P1"],
            )

        def list_issues(self, repo: str, label: str | None, limit: int):
            if label is None:
                return [self.product_issue]
            return []

    def fake_run_issue(config, issue_number):
        processed.append(issue_number)
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

    assert result["product_delta_recovery"] == {"enabled": False, "reason": "disabled"}
    assert processed == [67]
