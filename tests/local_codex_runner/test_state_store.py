import json
from pathlib import Path

from scripts.local_codex_runner.models import State
from scripts.local_codex_runner.state_store import load_state, save_state


def test_state_json_round_trip_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = State(processed_issue_ids=[2, 1], active_issue_ids=[3], branch_mappings={"3": "b"}, retry_counts={"x": 1})

    save_state(path, state)
    loaded = load_state(path)

    assert loaded.to_dict() == json.loads(path.read_text(encoding="utf-8"))

