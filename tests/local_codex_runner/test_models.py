from scripts.local_codex_runner.models import IssueTask, State, should_process_issue


def test_only_approved_issue_enters_queue() -> None:
    approved = IssueTask(1, "Fix", "", "", ["auto-codex-approved"])
    unapproved = IssueTask(2, "Fix", "", "", ["auto-codex-candidate"])

    assert should_process_issue(approved, approved_label="auto-codex-approved", pr_opened_label="codex-pr-opened", needs_human_label="codex-needs-human")
    assert not should_process_issue(unapproved, approved_label="auto-codex-approved", pr_opened_label="codex-pr-opened", needs_human_label="codex-needs-human")


def test_pr_opened_issue_is_not_reprocessed() -> None:
    issue = IssueTask(1, "Fix", "", "", ["auto-codex-approved", "codex-pr-opened"])

    assert not should_process_issue(issue, approved_label="auto-codex-approved", pr_opened_label="codex-pr-opened", needs_human_label="codex-needs-human")


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

