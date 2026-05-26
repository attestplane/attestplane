from scripts.local_codex_runner.models import (
    IssueTask,
    State,
    processable_issues,
    should_process_issue,
    task_has_product_delta,
)


def test_open_issue_enters_queue_without_approval_gate() -> None:
    open_issue = IssueTask(1, "Fix", "", "", [])
    pr_opened = IssueTask(2, "Fix", "", "", ["codex-pr-opened"])

    assert should_process_issue(open_issue, approved_label="auto-codex-approved", pr_opened_label="codex-pr-opened", needs_human_label="codex-needs-human")
    assert should_process_issue(pr_opened, approved_label="auto-codex-approved", pr_opened_label="codex-pr-opened", needs_human_label="codex-needs-human")


def test_needs_human_issue_is_not_blocked_by_queue_rules() -> None:
    issue = IssueTask(1, "Fix", "", "", ["auto-codex-approved", "codex-needs-human"])

    assert should_process_issue(issue, approved_label="auto-codex-approved", pr_opened_label="codex-pr-opened", needs_human_label="codex-needs-human")


def test_processable_issues_prioritizes_p0_and_p1_before_newer_p2() -> None:
    issues = [
        IssueTask(175, "[P2][test] Newer task", "", "", ["priority:P2"]),
        IssueTask(172, "[P1][verifier] Product task", "", "", ["priority:P1"]),
        IssueTask(114, "[P0][release] Boundary task", "", "", ["priority-P0"]),
        IssueTask(141, "[P2][docs] Open PR", "", "", ["priority:P2", "codex-pr-opened"]),
    ]

    queue = processable_issues(
        issues,
        approved_label="auto-codex-approved",
        pr_opened_label="codex-pr-opened",
        needs_human_label="codex-needs-human",
        max_issues_per_run=3,
    )

    assert [issue.number for issue in queue] == [114, 172, 175]


def test_processable_issues_uses_title_priority_when_label_is_missing() -> None:
    issues = [
        IssueTask(10, "[P2][docs] Documentation", "", "", []),
        IssueTask(11, "[P1][test] Regression", "", "", []),
    ]

    queue = processable_issues(
        issues,
        approved_label="auto-codex-approved",
        pr_opened_label="codex-pr-opened",
        needs_human_label="codex-needs-human",
        max_issues_per_run=2,
    )

    assert [issue.number for issue in queue] == [11, 10]


def test_product_delta_idle_filter_skips_support_only_tasks() -> None:
    product = IssueTask(
        21,
        "[P1][sdk][verifier] Implement proof-bundle behavior",
        "Touch Python SDK verifier and conformance fixtures.",
        "",
        ["priority:P1"],
    )
    support = IssueTask(
        22,
        "[P1][runner] Improve release train watcher",
        "Runner/docs/support-only task for release cadence.",
        "",
        ["priority:P1"],
    )

    assert task_has_product_delta(product)
    assert not task_has_product_delta(support)

    queue = processable_issues(
        [support, product],
        approved_label="auto-codex-approved",
        pr_opened_label="codex-pr-opened",
        needs_human_label="codex-needs-human",
        max_issues_per_run=2,
        require_product_delta=True,
    )

    assert [issue.number for issue in queue] == [22, 21]


def test_product_delta_idle_filter_skips_explicit_docs_release_tasks_even_with_api_text() -> None:
    docs_release = IssueTask(
        67,
        "[P1][docs][release] Publish API reference as versioned stable documentation",
        "Publish public API reference docs for stable releases.",
        "",
        ["priority:P1", "type:docs", "area:docs", "area:release-integrity"],
    )
    recovery_product = IssueTask(
        68,
        "[P1][sdk][verifier] Add product implementation delta for stalled stable train",
        "Implement SDK verifier behavior. Do not satisfy this task with docs-only or release-only changes.",
        "",
        ["priority:P1", "area:verifier"],
    )

    assert not task_has_product_delta(docs_release)
    assert task_has_product_delta(recovery_product)

    queue = processable_issues(
        [docs_release, recovery_product],
        approved_label="auto-codex-approved",
        pr_opened_label="codex-pr-opened",
        needs_human_label="codex-needs-human",
        max_issues_per_run=2,
        require_product_delta=True,
    )

    assert [issue.number for issue in queue] == [67, 68]


def test_state_round_trip_is_deterministic() -> None:
    state = State.from_dict(
        {
            "processed_issue_ids": [3, 1],
            "active_issue_ids": [2],
            "branch_mappings": {"2": "codex/issue-2-fix"},
            "retry_counts": {"issue:2": 2},
            "last_result": {"status": "SUCCESS"},
        }
    )

    assert state.to_dict() == State.from_dict(state.to_dict()).to_dict()
