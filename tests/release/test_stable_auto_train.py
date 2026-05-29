from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


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


@pytest.mark.parametrize(
    ("release_label", "expected"),
    [
        ("release:minor", "v1.3.0"),
        ("release:major", "v2.0.0"),
        ("release:patch", "v1.2.10"),
        ("release:none", "v1.2.10"),
    ],
)
def test_next_stable_after_respects_release_label(
    release_label: str, expected: str
) -> None:
    current = stable_auto_train.StableVersion.parse("1.2.9")

    assert (
        stable_auto_train.next_stable_after(current, release_label=release_label).tag
        == expected
    )


def test_release_label_from_merged_pr_reads_gh_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []

    def fake_capture(argv: list[str], *, timeout: int | None = None) -> str:
        del timeout
        commands.append(argv)
        if argv[:3] == ["gh", "pr", "list"]:
            return "42\n"
        if argv[:3] == ["gh", "pr", "view"]:
            return json.dumps({"labels": [{"name": "release:minor"}]})
        raise AssertionError(argv)

    monkeypatch.setattr(stable_auto_train, "capture", fake_capture)

    assert stable_auto_train.release_label_from_merged_pr("deadbeef") == "release:minor"
    assert commands == [
        [
            "gh",
            "pr",
            "list",
            "--search",
            "deadbeef",
            "--state",
            "merged",
            "--limit",
            "1",
            "--json",
            "number",
            "--jq",
            ".[0].number",
        ],
        ["gh", "pr", "view", "42", "--json", "labels"],
    ]
