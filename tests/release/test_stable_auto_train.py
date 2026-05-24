from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "release" / "stable_auto_train.py"


spec = importlib.util.spec_from_file_location("stable_auto_train", MODULE_PATH)
assert spec is not None
stable_auto_train = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["stable_auto_train"] = stable_auto_train
spec.loader.exec_module(stable_auto_train)


def test_best_effort_fetch_tags_updates_origin_main(monkeypatch) -> None:
    commands: list[list[str]] = []

    def fake_remote_probe(argv: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(stable_auto_train, "run_git_remote_probe", fake_remote_probe)

    stable_auto_train.best_effort_fetch_tags()

    assert commands == [
        [
            "git",
            *stable_auto_train.GIT_HTTP_CONFIG_ARGS,
            "fetch",
            "origin",
            "refs/heads/main:refs/remotes/origin/main",
            "--tags",
        ]
    ]
