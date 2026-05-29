import json
from pathlib import Path

from scripts.local_codex_runner.models import State
from scripts.local_codex_runner.state_store import load_state, save_state


def test_state_json_round_trip_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = State(
        processed_issue_ids=[2, 1],
        active_issue_ids=[3],
        branch_mappings={"3": "b"},
        retry_counts={"x": 1},
    )

    save_state(path, state)
    loaded = load_state(path)

    assert loaded.to_dict() == json.loads(path.read_text(encoding="utf-8"))


def test_state_prunes_closed_issue_without_forgetting_processed_history() -> None:
    state = State(
        active_issue_ids=[118, 125],
        branch_mappings={"118": "codex/issue-118", "125": "codex/issue-125"},
        processed_issue_ids=[118],
    )

    assert state.prune_issue(118)

    assert state.active_issue_ids == [125]
    assert state.branch_mappings == {"125": "codex/issue-125"}
    assert state.processed_issue_ids == [118]
