# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DIFF_PATH = REPO_ROOT / "scripts" / "security" / "scorecard_diff.py"
MONITOR_PATH = REPO_ROOT / "scripts" / "security" / "scorecard_monitor.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


scorecard_diff = _load_module(DIFF_PATH, "scorecard_diff")
scorecard_monitor = _load_module(MONITOR_PATH, "scorecard_monitor")


def _summary(score: float, checks: list[tuple[str, float, str]] | None = None) -> dict[str, object]:
    return {
        "schema": "attestplane.scorecard.summary.v1",
        "repo": "github.com/attestplane/attestplane",
        "score": score,
        "checks": [
            {"name": name, "score": check_score, "reason": reason}
            for name, check_score, reason in (checks or [])
        ],
    }


def test_compare_summaries_flags_meaningful_regression_from_score_drop(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    baseline_path.write_text(json.dumps(_summary(9.0, [("Branch-Protection", 10.0, "ok"), ("Signed-Releases", 8.0, "ok")])) + "\n", encoding="utf-8")
    current_path.write_text(json.dumps(_summary(7.0, [("Branch-Protection", 8.0, "changed"), ("Signed-Releases", 6.0, "changed")])) + "\n", encoding="utf-8")

    report = scorecard_diff.compare_summaries(
        scorecard_diff.load_summary(baseline_path),
        scorecard_diff.load_summary(current_path),
    )

    assert report.meaningful_regression is True
    assert report.score_drop == 2.0
    assert [item.name for item in report.regressions] == ["Branch-Protection", "Signed-Releases"]


def test_compare_summaries_ignores_small_drift(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    baseline_path.write_text(json.dumps(_summary(9.0, [("Branch-Protection", 10.0, "ok")])) + "\n", encoding="utf-8")
    current_path.write_text(json.dumps(_summary(8.5, [("Branch-Protection", 9.5, "small drift")])) + "\n", encoding="utf-8")

    report = scorecard_diff.compare_summaries(
        scorecard_diff.load_summary(baseline_path),
        scorecard_diff.load_summary(current_path),
    )

    assert report.meaningful_regression is False
    assert report.score_drop == 0.5


def test_scorecard_diff_main_returns_nonzero_on_meaningful_regression(tmp_path: Path, capsys) -> None:
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    baseline_path.write_text(json.dumps(_summary(9.0, [("Branch-Protection", 10.0, "ok")])) + "\n", encoding="utf-8")
    current_path.write_text(json.dumps(_summary(7.5, [("Branch-Protection", 8.0, "changed")])) + "\n", encoding="utf-8")

    rc = scorecard_diff.main(["--baseline", str(baseline_path), "--current", str(current_path)])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert payload["meaningful_regression"] is True
    assert payload["score_drop"] == 1.5


def test_monitor_bootstraps_missing_baseline_and_writes_latest_summary(tmp_path: Path, monkeypatch) -> None:
    current_path = tmp_path / "current.json"
    baseline_path = tmp_path / "baseline.json"
    latest_path = tmp_path / "latest.json"
    current_path.write_text(json.dumps(_summary(8.0, [("Branch-Protection", 10.0, "ok")])) + "\n", encoding="utf-8")

    result = scorecard_monitor.run_monitor(
        baseline_path=baseline_path,
        current_path=current_path,
        latest_summary_path=latest_path,
        repo=None,
        meaningful_drop=1.0,
        issue_title=scorecard_monitor.DEFAULT_ISSUE_TITLE,
        issue_labels=scorecard_monitor.DEFAULT_ISSUE_LABELS,
    )

    assert result["status"] == "baseline_initialized"
    assert baseline_path.exists()
    assert latest_path.exists()
    assert json.loads(latest_path.read_text(encoding="utf-8"))["score"] == 8.0


def test_monitor_opens_issue_on_meaningful_regression(tmp_path: Path, monkeypatch) -> None:
    current_path = tmp_path / "current.json"
    baseline_path = tmp_path / "baseline.json"
    latest_path = tmp_path / "latest.json"
    baseline_path.write_text(json.dumps(_summary(9.0, [("Branch-Protection", 10.0, "ok"), ("Signed-Releases", 8.0, "ok")])) + "\n", encoding="utf-8")
    current_path.write_text(json.dumps(_summary(7.0, [("Branch-Protection", 8.0, "changed"), ("Signed-Releases", 6.0, "changed")])) + "\n", encoding="utf-8")

    calls: list[list[str]] = []

    def fake_run(command, check, capture_output, text):
        calls.append(command)
        if command[:3] == ["gh", "label", "create"]:
            return subprocess.CompletedProcess(command, 0, "", "already exists")
        if command[:3] == ["gh", "issue", "list"]:
            return subprocess.CompletedProcess(command, 0, "[]", "")
        if command[:3] == ["gh", "issue", "create"]:
            return subprocess.CompletedProcess(command, 0, "https://example.test/issues/7\n", "")
        raise AssertionError(command)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = scorecard_monitor.run_monitor(
        baseline_path=baseline_path,
        current_path=current_path,
        latest_summary_path=latest_path,
        repo="github.com/attestplane/attestplane",
        meaningful_drop=1.0,
        issue_title=scorecard_monitor.DEFAULT_ISSUE_TITLE,
        issue_labels=scorecard_monitor.DEFAULT_ISSUE_LABELS,
    )

    assert result["status"] == "regression"
    assert result["issue"]["action"] == "created"
    assert any(command[:3] == ["gh", "issue", "create"] for command in calls)


def test_monitor_updates_existing_issue_on_repeat_regression(tmp_path: Path, monkeypatch) -> None:
    current_path = tmp_path / "current.json"
    baseline_path = tmp_path / "baseline.json"
    latest_path = tmp_path / "latest.json"
    baseline_path.write_text(json.dumps(_summary(9.0, [("Branch-Protection", 10.0, "ok")])) + "\n", encoding="utf-8")
    current_path.write_text(json.dumps(_summary(7.0, [("Branch-Protection", 8.0, "changed")])) + "\n", encoding="utf-8")

    calls: list[list[str]] = []

    def fake_run(command, check, capture_output, text):
        calls.append(command)
        if command[:3] == ["gh", "label", "create"]:
            return subprocess.CompletedProcess(command, 0, "", "already exists")
        if command[:3] == ["gh", "issue", "list"]:
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps(
                    [
                        {
                            "number": 8,
                            "title": scorecard_monitor.DEFAULT_ISSUE_TITLE,
                            "url": "https://example.test/issues/8",
                            "labels": [{"name": "scorecard-regression"}],
                            "body": "old body",
                        }
                    ]
                ),
                "",
            )
        if command[:3] == ["gh", "issue", "edit"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        raise AssertionError(command)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = scorecard_monitor.run_monitor(
        baseline_path=baseline_path,
        current_path=current_path,
        latest_summary_path=latest_path,
        repo="github.com/attestplane/attestplane",
        meaningful_drop=1.0,
        issue_title=scorecard_monitor.DEFAULT_ISSUE_TITLE,
        issue_labels=scorecard_monitor.DEFAULT_ISSUE_LABELS,
    )

    assert result["status"] == "regression"
    assert result["issue"]["action"] == "updated"
    assert any(command[:3] == ["gh", "issue", "edit"] for command in calls)
