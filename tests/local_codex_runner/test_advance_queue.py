from scripts.local_codex_runner.advance_queue import (
    PullRequestState,
    advance_queue,
    decide_dependency_unlock,
    decide_pr_action,
    dependencies_for_issue,
    matches_label_filters,
    parse_dependencies,
)
from scripts.local_codex_runner.config import RunnerConfig
from scripts.local_codex_runner.github_cli import CheckStatus
from scripts.local_codex_runner.models import IssueTask


def test_parse_dependencies_accepts_common_headers() -> None:
    body = """
    Depends on: #121, #127
    unrelated #999
    Dependencies: #122
    """

    assert parse_dependencies(body) == [121, 122, 127]


def test_dependencies_for_issue_maps_plan_local_ordinals() -> None:
    siblings = [
        IssueTask(121, "issue 1", "Source planning issue: #120", "u", ["planned-task"]),
        IssueTask(
            122,
            "issue 2",
            "Source planning issue: #120\nAcceptance: match Issue 1",
            "u",
            ["planned-task"],
        ),
        IssueTask(123, "issue 3", "Source planning issue: #120", "u", ["planned-task"]),
        IssueTask(
            125,
            "docs",
            "Source planning issue: #120\nLand after Issues 1-3 are merged.",
            "u",
            ["planned-task"],
        ),
    ]

    assert dependencies_for_issue(siblings[1], siblings) == [121]
    assert dependencies_for_issue(siblings[3], siblings) == [121, 122, 123]


def test_dependencies_for_issue_maps_extends_hint() -> None:
    issue = IssueTask(
        124,
        "test",
        "Source planning issue: #120\nExtend #115 rather than duplicate.",
        "u",
        ["planned-task"],
    )

    assert dependencies_for_issue(issue, [issue]) == [115]


def test_pr_gate_requires_explicit_ready_label() -> None:
    config = RunnerConfig(repo="o/r", workdir="/tmp/r")
    pr = PullRequestState(
        number=126,
        title="Fix #121",
        url="https://example/pr/126",
        base_branch="main",
        author="codex-bot",
        labels=["codex-ci-green"],
        is_draft=False,
        merge_state_status="CLEAN",
        review_decision="APPROVED",
        checks=[CheckStatus("ci", "SUCCESS", "pass")],
    )

    decision = decide_pr_action(pr, config)

    assert decision.action == "comment"
    assert "label:auto-merge-ready" in decision.waiting_on


def test_pr_gate_rejects_unclean_merge_state() -> None:
    config = RunnerConfig(
        repo="o/r",
        workdir="/tmp/r",
        allow_auto_merge=True,
        allowed_pr_authors=["codex-bot"],
    )
    pr = PullRequestState(
        number=126,
        title="Fix #121",
        url="https://example/pr/126",
        base_branch="main",
        author="codex-bot",
        labels=["auto-merge-ready"],
        is_draft=False,
        merge_state_status="DIRTY",
        review_decision="APPROVED",
        checks=[CheckStatus("ci", "SUCCESS", "pass")],
    )

    decision = decide_pr_action(pr, config)

    assert decision.action == "comment"
    assert "merge-state:DIRTY" in decision.waiting_on


def test_pr_gate_rejects_non_allowlisted_author() -> None:
    config = RunnerConfig(
        repo="o/r",
        workdir="/tmp/r",
        allow_auto_merge=True,
        allowed_pr_authors=["codex-bot"],
    )
    pr = PullRequestState(
        number=126,
        title="Fix #121",
        url="https://example/pr/126",
        base_branch="main",
        author="someone-else",
        labels=["auto-merge-ready"],
        is_draft=False,
        merge_state_status="CLEAN",
        review_decision="APPROVED",
        checks=[CheckStatus("ci", "SUCCESS", "pass")],
    )

    decision = decide_pr_action(pr, config)

    assert decision.action == "comment"
    assert "author:someone-else" in decision.waiting_on


def test_pr_gate_merges_only_when_config_allows() -> None:
    config = RunnerConfig(
        repo="o/r",
        workdir="/tmp/r",
        allow_auto_merge=True,
        allowed_pr_authors=["codex-bot"],
    )
    pr = PullRequestState(
        number=126,
        title="Fix #121",
        url="https://example/pr/126",
        base_branch="main",
        author="codex-bot",
        labels=["auto-merge-ready"],
        is_draft=False,
        merge_state_status="CLEAN",
        review_decision="APPROVED",
        checks=[CheckStatus("ci", "SUCCESS", "pass")],
    )

    decision = decide_pr_action(pr, config)

    assert decision.action == "merge"


def test_pr_label_filters_require_includes_and_apply_excludes() -> None:
    raw_pr = {"labels": [{"name": "codex-ci-green"}, {"name": "ready"}]}

    assert matches_label_filters(raw_pr, ["codex-ci-green"], [])
    assert not matches_label_filters(raw_pr, ["auto-merge-ready"], [])
    assert not matches_label_filters(raw_pr, ["codex-ci-green"], ["ready"])


def test_dependency_unlock_waits_until_all_dependencies_closed() -> None:
    config = RunnerConfig(repo="o/r", workdir="/tmp/r", allow_dependency_unlock=True)
    issue = IssueTask(
        number=122,
        title="task",
        body="Depends on: #121, #127",
        url="https://example/issues/122",
        labels=["planned-task"],
    )

    decision = decide_dependency_unlock(issue, {121: "CLOSED", 127: "OPEN"}, config)

    assert decision.action == "comment"
    assert decision.waiting_on == ["issue:127:OPEN"]


def test_dependency_unlock_treats_reverted_dependency_as_blocked() -> None:
    config = RunnerConfig(repo="o/r", workdir="/tmp/r", allow_dependency_unlock=True)
    issue = IssueTask(
        number=122,
        title="task",
        body="Depends on: #121",
        url="https://example/issues/122",
        labels=["planned-task"],
    )

    decision = decide_dependency_unlock(issue, {121: "REVERTED"}, config)

    assert decision.action == "comment"
    assert decision.waiting_on == ["issue:121:REVERTED"]


def test_dependency_unlock_adds_approval_when_dependencies_closed() -> None:
    config = RunnerConfig(repo="o/r", workdir="/tmp/r", allow_dependency_unlock=True)
    issue = IssueTask(
        number=122,
        title="task",
        body="Depends on: #121, #127",
        url="https://example/issues/122",
        labels=["planned-task"],
    )

    decision = decide_dependency_unlock(issue, {121: "CLOSED", 127: "CLOSED"}, config)

    assert decision.action == "unlock"


def test_dependency_unlock_approves_tasks_without_dependencies() -> None:
    config = RunnerConfig(repo="o/r", workdir="/tmp/r", allow_dependency_unlock=True)
    issue = IssueTask(
        number=139,
        title="task",
        body="No dependency line.",
        url="https://example/issues/139",
        labels=["planned-task"],
    )

    decision = decide_dependency_unlock(issue, {}, config)

    assert decision.action == "unlock"
    assert decision.reason == "no_dependencies"


def test_advance_queue_unlocks_only_product_tasks_during_product_delta_idle(
    monkeypatch, tmp_path
) -> None:
    product = IssueTask(
        201,
        "[P1][sdk][verifier] Add product behavior",
        "Implement verifier-facing SDK behavior.",
        "u",
        ["planned-task", "priority:P1"],
    )
    support = IssueTask(
        202,
        "[P1][runner] Tune local runner",
        "Support-only release train runner task.",
        "u",
        ["planned-task", "priority:P1"],
    )

    class FakeGH:
        def __init__(self, dry_run=True):
            self.commands_run = []
            self.added: list[tuple[int, list[str]]] = []

        def list_issues(
            self, repo: str, label: str, limit: int, *, state: str = "open"
        ):
            return [support, product]

        def list_pull_requests(self, repo: str, base: str, limit: int):
            return []

        def view_issue_state(self, repo: str, issue_number: int) -> str:
            return "CLOSED"

        def add_labels(self, repo: str, issue_number: int, labels: list[str]) -> None:
            self.added.append((issue_number, labels))

        def remove_labels(
            self, repo: str, issue_number: int, labels: list[str]
        ) -> None:
            pass

    fake = FakeGH()
    monkeypatch.setattr(
        "scripts.local_codex_runner.advance_queue.GitHubCLI", lambda dry_run=True: fake
    )
    config_path = tmp_path / "runner.yml"
    config_path.write_text(
        'repo: "o/r"\n'
        f'workdir: "{tmp_path}"\n'
        "dry_run: false\n"
        "allow_dependency_unlock: true\n",
        encoding="utf-8",
    )
    args = type(
        "Args",
        (),
        {
            "config": config_path,
            "repo": "o/r",
            "workdir": "/tmp/r",
            "dry_run": False,
            "max_local_fix_rounds": None,
            "max_ci_fix_rounds": None,
            "create_pr": None,
            "watch_ci": None,
            "allow_dirty": None,
            "mode": "deps",
            "pr_limit": 0,
            "issue_limit": 10,
            "include_label": [],
            "exclude_label": [],
            "comment": False,
            "product_delta_idle": True,
        },
    )()

    summary = advance_queue(args)

    assert fake.added == [(201, ["auto-codex-approved"])]
    assert summary["product_delta_idle"] is True
    assert [decision["target_number"] for decision in summary["decisions"]] == [201]
