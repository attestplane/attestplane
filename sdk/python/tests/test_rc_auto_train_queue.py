from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts/release/rc_auto_train.py"

spec = importlib.util.spec_from_file_location("rc_auto_train", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
rc_auto_train = importlib.util.module_from_spec(spec)
sys.modules["rc_auto_train"] = rc_auto_train
spec.loader.exec_module(rc_auto_train)


def test_target_queue_loads_strictly_increasing_rc_only_targets(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    queue.write_text(
        json.dumps(
            {
                "schema": "attestplane_autodev_train_targets.v1",
                "targets": [
                    {"version": "0.8.6", "status": "queued", "min_rc_soak_hours": 24, "promote_to": ["rc"]},
                    {"version": "0.9.0", "status": "queued", "min_rc_soak_hours": 24, "promote_to": ["rc"]},
                ],
            }
        ),
        encoding="utf-8",
    )

    targets = rc_auto_train.load_target_queue(queue)

    assert [target.version.tag for target in targets] == ["v0.8.6", "v0.9.0"]
    assert all(target.promote_to == ("rc",) for target in targets)


def test_target_queue_rejects_automatic_latest_or_ca_promotion(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    queue.write_text(
        json.dumps(
            {
                "schema": "attestplane_autodev_train_targets.v1",
                "targets": [
                    {"version": "0.8.6", "status": "queued", "min_rc_soak_hours": 24, "promote_to": ["rc", "ca"]},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="latest/ca promotion"):
        rc_auto_train.load_target_queue(queue)


def test_next_rc_for_target_starts_from_previous_stable() -> None:
    target = rc_auto_train.StableVersion.parse("0.8.6")
    previous = rc_auto_train.StableVersion.parse("0.8.5")

    assert rc_auto_train.next_rc_for_target(target, previous).tag == "v0.8.6-rc.1"


def test_next_rc_for_target_advances_existing_target_rc() -> None:
    target = rc_auto_train.StableVersion.parse("0.8.6")
    previous = rc_auto_train.RcVersion.parse("v0.8.6-rc.1")

    assert rc_auto_train.next_rc_for_target(target, previous).tag == "v0.8.6-rc.2"


def test_next_rc_for_target_stops_at_rc10() -> None:
    target = rc_auto_train.StableVersion.parse("0.8.6")
    previous = rc_auto_train.RcVersion.parse("v0.8.6-rc.10")

    with pytest.raises(RuntimeError, match=r"has reached rc\.10"):
        rc_auto_train.next_rc_for_target(target, previous)
