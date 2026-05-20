from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts/release/stable_auto_train.py"

spec = importlib.util.spec_from_file_location("stable_auto_train", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
stable_auto_train = importlib.util.module_from_spec(spec)
sys.modules["stable_auto_train"] = stable_auto_train
spec.loader.exec_module(stable_auto_train)


def test_target_queue_loads_strictly_increasing_stable_targets(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    queue.write_text(
        json.dumps(
            {
                "schema": "attestplane_autodev_train_targets.v2",
                "targets": [
                    {"version": "0.8.6", "status": "queued", "channel": "latest", "min_soak_hours": 0},
                    {"version": "0.9.0", "status": "queued", "channel": "latest", "min_soak_hours": 0},
                ],
            }
        ),
        encoding="utf-8",
    )

    targets = stable_auto_train.load_target_queue(queue)

    assert [target.version.tag for target in targets] == ["v0.8.6", "v0.9.0"]
    assert all(target.channel == "latest" for target in targets)


def test_target_queue_rejects_rc_channel(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    queue.write_text(
        json.dumps(
            {
                "schema": "attestplane_autodev_train_targets.v2",
                "targets": [
                    {"version": "0.8.6", "status": "queued", "channel": "rc", "min_soak_hours": 0},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="unsupported"):
        stable_auto_train.load_target_queue(queue)


def test_target_queue_rejects_non_increasing_versions(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    queue.write_text(
        json.dumps(
            {
                "schema": "attestplane_autodev_train_targets.v2",
                "targets": [
                    {"version": "0.8.7", "status": "queued", "channel": "latest", "min_soak_hours": 0},
                    {"version": "0.8.6", "status": "queued", "channel": "latest", "min_soak_hours": 0},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="strictly increasing"):
        stable_auto_train.load_target_queue(queue)


def test_next_stable_after_advances_patch_until_ten() -> None:
    current = stable_auto_train.StableVersion.parse("0.8.9")

    assert stable_auto_train.next_stable_after(current).tag == "v0.8.10"


def test_next_stable_after_rolls_patch_ten_to_next_minor_zero() -> None:
    current = stable_auto_train.StableVersion.parse("0.8.10")

    assert stable_auto_train.next_stable_after(current).tag == "v0.9.0"


def test_next_stable_after_continues_after_minor_boundary() -> None:
    current = stable_auto_train.StableVersion.parse("0.9.0")

    assert stable_auto_train.next_stable_after(current).tag == "v0.9.1"


def test_next_stable_after_rolls_zero_nine_ten_to_one_zero_zero() -> None:
    current = stable_auto_train.StableVersion.parse("0.9.10")

    assert stable_auto_train.next_stable_after(current).tag == "v1.0.0"


def test_next_stable_after_rolls_post_one_patch_ten_to_next_minor_zero() -> None:
    current = stable_auto_train.StableVersion.parse("1.0.10")

    assert stable_auto_train.next_stable_after(current).tag == "v1.1.0"
