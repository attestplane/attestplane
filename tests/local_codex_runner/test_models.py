from scripts.local_codex_runner.models import IssueTask, State, processable_issues, should_process_issue


def test_only_approved_issue_enters_queue() -> None:
    approved = IssueTask(1, "Fix", "", "", ["auto-codex-approved"])
    unapproved = IssueTask(2, "Fix", "", "", ["auto-codex-candidate"])

    assert should_process_issue(approved, approved_label="auto-codex-approved", pr_opened_label="codex-pr-opened", needs_human_label="codex-needs-human")
    assert not should_process_issue(unapproved, approved_label="auto-codex-approved", pr_opened_label="codex-pr-opened", needs_human_label="codex-needs-human")


def test_pr_opened_issue_is_not_reprocessed() -> None:
    issue = IssueTask(1, "Fix", "", "", ["auto-codex-approved", "codex-pr-opened"])

    assert not should_process_issue(issue, approved_label="auto-codex-approved", pr_opened_label="codex-pr-opened", needs_human_label="codex-needs-human")


def test_processable_issues_prioritizes_p0_and_p1_before_newer_p2() -> None:
    issues = [
        IssueTask(175, "[P2][test] Newer task", "", "", ["auto-codex-approved", "priority:P2"]),
        IssueTask(172, "[P1][verifier] Product task", "", "", ["auto-codex-approved", "priority:P1"]),
        IssueTask(114, "[P0][release] Boundary task", "", "", ["auto-codex-approved", "priority-P0"]),
        IssueTask(141, "[P2][docs] Open PR", "", "", ["auto-codex-approved", "priority:P2", "codex-pr-opened"]),
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
        IssueTask(10, "[P2][docs] Documentation", "", "", ["auto-codex-approved"]),
        IssueTask(11, "[P1][test] Regression", "", "", ["auto-codex-approved"]),
    ]

    queue = processable_issues(
        issues,
        approved_label="auto-codex-approved",
        pr_opened_label="codex-pr-opened",
        needs_human_label="codex-needs-human",
        max_issues_per_run=2,
    )

    assert [issue.number for issue in queue] == [11, 10]


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
