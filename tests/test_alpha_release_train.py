from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "release" / "alpha_release_train.py"


spec = importlib.util.spec_from_file_location("alpha_release_train", MODULE_PATH)
assert spec is not None
alpha_release_train = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["alpha_release_train"] = alpha_release_train
spec.loader.exec_module(alpha_release_train)


def write_queue(tmp_path: Path, candidates: list[dict[str, object]]) -> Path:
    path = tmp_path / "queue.json"
    path.write_text(json.dumps({"schema": "attestplane_alpha_release_train_queue.v1", "candidates": candidates}))
    return path


def candidate(release: str = "v0.0.6-alpha") -> dict[str, object]:
    return {
        "release": release,
        "python_version": "0.0.6a0",
        "npm_version": "0.0.6-alpha",
    }


def test_empty_queue_is_noop_success(tmp_path: Path) -> None:
    path = write_queue(tmp_path, [])
    assert alpha_release_train.load_queue(path) == []


def test_queue_requires_alpha_release_shape(tmp_path: Path) -> None:
    path = write_queue(tmp_path, [candidate("v0.0.6")])
    with pytest.raises(ValueError, match="alpha release names"):
        alpha_release_train.load_queue(path)


def test_queue_rejects_duplicate_release_entries(tmp_path: Path) -> None:
    path = write_queue(tmp_path, [candidate(), candidate()])
    with pytest.raises(ValueError, match="duplicate alpha release"):
        alpha_release_train.load_queue(path)


def test_queue_rejects_non_alpha_npm_version(tmp_path: Path) -> None:
    item = candidate()
    item["npm_version"] = "0.0.6"
    path = write_queue(tmp_path, [item])
    with pytest.raises(ValueError, match="npm alpha versions"):
        alpha_release_train.load_queue(path)
