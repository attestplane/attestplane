# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main

ROOT = Path(__file__).resolve().parents[2]
ANCHORED_FIXTURE = ROOT / "fixtures" / "anchored.bundle"
UNANCHORED_FIXTURE = ROOT / "fixtures" / "positive" / "minimal.json"
QUARANTINED_FIXTURE = ROOT / "fixtures" / "quarantined.bundle"


def _verify_json(bundle: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, object], str]:
    rc = main(["verify", "--json", str(bundle)])
    captured = capsys.readouterr()
    return rc, json.loads(captured.out), captured.err


@pytest.mark.parametrize(
    ("case_id", "fixture", "expected_status", "expected_quarantined"),
    [
        ("anchored-positive", ANCHORED_FIXTURE, "anchored", False),
        ("anchored-negative", UNANCHORED_FIXTURE, "unanchored", False),
    ],
)
def test_verify_json_anchored_status_vectors(
    case_id: str,
    fixture: Path,
    expected_status: str,
    expected_quarantined: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, stderr = _verify_json(fixture, capsys)

    assert stderr == ""
    assert payload["anchoring"] == {"quarantined": expected_quarantined, "status": expected_status}
    assert payload["result"] == "pass"
    assert payload["exit_code"] == 0
    assert rc == 0, case_id


@pytest.mark.parametrize(
    ("case_id", "fixture", "expected_status", "expected_quarantined", "expected_exit"),
    [
        ("unanchored-positive", UNANCHORED_FIXTURE, "unanchored", False, 0),
        ("unanchored-negative", ANCHORED_FIXTURE, "anchored", False, 0),
    ],
)
def test_verify_json_unanchored_status_vectors(
    case_id: str,
    fixture: Path,
    expected_status: str,
    expected_quarantined: bool,
    expected_exit: int,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, stderr = _verify_json(fixture, capsys)

    assert stderr == ""
    assert payload["anchoring"] == {"quarantined": expected_quarantined, "status": expected_status}
    assert payload["exit_code"] == expected_exit
    assert rc == expected_exit, case_id


@pytest.mark.parametrize(
    ("case_id", "fixture", "expected_status", "expected_quarantined", "expected_exit"),
    [
        ("quarantine-positive", QUARANTINED_FIXTURE, "quarantined", True, 2),
        ("quarantine-negative", UNANCHORED_FIXTURE, "unanchored", False, 0),
    ],
)
def test_verify_json_quarantine_status_vectors(
    case_id: str,
    fixture: Path,
    expected_status: str,
    expected_quarantined: bool,
    expected_exit: int,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, stderr = _verify_json(fixture, capsys)

    assert payload["anchoring"] == {"quarantined": expected_quarantined, "status": expected_status}
    assert payload["exit_code"] == expected_exit
    assert rc == expected_exit, case_id
    if expected_exit == 2:
        assert stderr == ""
