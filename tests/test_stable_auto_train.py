from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "release" / "stable_auto_train.py"


spec = importlib.util.spec_from_file_location("stable_auto_train", MODULE_PATH)
assert spec is not None
stable_auto_train = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["stable_auto_train"] = stable_auto_train
spec.loader.exec_module(stable_auto_train)


def test_open_actionable_product_planned_tasks_excludes_blocked_and_in_progress(monkeypatch) -> None:
    payload = [
        {
            "number": 207,
            "labels": [{"name": "planned-task"}, {"name": "auto-codex-approved"}],
        },
        {
            "number": 208,
            "labels": [
                {"name": "planned-task"},
                {"name": "auto-codex-approved"},
                {"name": "codex-in-progress"},
            ],
        },
        {
            "number": 209,
            "labels": [
                {"name": "planned-task"},
                {"name": "auto-codex-approved"},
                {"name": "codex-needs-human"},
            ],
        },
        {
            "number": 210,
            "labels": [{"name": "planned-task"}],
        },
    ]
    monkeypatch.setattr(stable_auto_train, "capture", lambda *args, **kwargs: json.dumps(payload))

    assert stable_auto_train.open_actionable_product_planned_tasks() == [207]


def test_stale_product_delta_plan_recently_dispatched_uses_tag_and_cooldown(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    state.write_text(
        json.dumps({"planning_tag": "v1.7.6", "dispatched_at_epoch": 1000.0}) + "\n",
        encoding="utf-8",
    )

    assert stable_auto_train.stale_product_delta_plan_recently_dispatched(
        state_path=state,
        planning_tag="v1.7.6",
        now=1100.0,
        cooldown_seconds=300,
    )
    assert not stable_auto_train.stale_product_delta_plan_recently_dispatched(
        state_path=state,
        planning_tag="v1.7.6",
        now=1400.0,
        cooldown_seconds=300,
    )
    assert not stable_auto_train.stale_product_delta_plan_recently_dispatched(
        state_path=state,
        planning_tag="v1.7.7",
        now=1100.0,
        cooldown_seconds=300,
    )


def test_maybe_dispatch_stale_product_delta_planning_dispatches_for_previous_stable(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[list[str]] = []
    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(stable_auto_train, "open_actionable_product_planned_tasks", lambda: [])
    monkeypatch.setattr(stable_auto_train, "time", type("FakeTime", (), {"time": staticmethod(lambda: 1234.0)}))
    monkeypatch.setattr(stable_auto_train, "DEFAULT_STALE_PRODUCT_DELTA_PLAN_STATE", tmp_path / "state.json")
    monkeypatch.setattr(stable_auto_train, "DEFAULT_STALE_PRODUCT_DELTA_PLAN_LOCK", tmp_path / "state.lock")
    monkeypatch.setattr(stable_auto_train, "run", lambda argv, **kwargs: calls.append(argv))
    monkeypatch.setattr(stable_auto_train, "emit_event", lambda event, **fields: events.append((event, fields)))

    target = stable_auto_train.ReleaseTarget(
        version=stable_auto_train.StableVersion.parse("1.7.7"),
        channel="latest",
        min_soak_hours=0,
    )
    previous = stable_auto_train.StableVersion.parse("1.7.6")

    stable_auto_train.maybe_dispatch_stale_product_delta_planning(target, previous)

    assert calls == [
        [
            "gh",
            "workflow",
            "run",
            "architecture-audit.yml",
            "--ref",
            "main",
            "-f",
            "milestone_tag=v1.7.6",
        ]
    ]
    assert events[-1][0] == "stale_product_delta_planning_dispatched"
    assert json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))["planning_tag"] == "v1.7.6"


def test_maybe_dispatch_stale_product_delta_planning_skips_when_actionable_tasks_exist(monkeypatch) -> None:
    calls: list[list[str]] = []
    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(stable_auto_train, "open_actionable_product_planned_tasks", lambda: [207, 209])
    monkeypatch.setattr(stable_auto_train, "run", lambda argv, **kwargs: calls.append(argv))
    monkeypatch.setattr(stable_auto_train, "emit_event", lambda event, **fields: events.append((event, fields)))

    target = stable_auto_train.ReleaseTarget(
        version=stable_auto_train.StableVersion.parse("1.7.7"),
        channel="latest",
        min_soak_hours=0,
    )
    previous = stable_auto_train.StableVersion.parse("1.7.6")

    stable_auto_train.maybe_dispatch_stale_product_delta_planning(target, previous)

    assert calls == []
    assert events == [
        (
            "stale_product_delta_planning_skipped",
            {
                "previous_tag": "v1.7.6",
                "target_tag": "v1.7.7",
                "reason": "actionable_planned_tasks_exist",
                "planned_tasks": [207, 209],
            },
        )
    ]
