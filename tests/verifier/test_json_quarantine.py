# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Quarantine-state coverage for ``verify --json`` and SDK verifier results."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verifier import verify_proof_bundle_file

ROOT = Path(__file__).resolve().parents[2]
UNANCHORED_FIXTURE = ROOT / "fixtures" / "positive" / "minimal.json"
ANCHORED_FIXTURE = ROOT / "fixtures" / "anchored.bundle"
QUARANTINED_FIXTURE = ROOT / "fixtures" / "quarantined.bundle"


def _run_json(path: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, object]]:
    rc = main(["verify", "--json", str(path)])
    payload = json.loads(capsys.readouterr().out)
    return rc, payload


@pytest.mark.parametrize(
    ("fixture", "expected_status", "expected_exit"),
    [
        (UNANCHORED_FIXTURE, "unanchored", 0),
        (ANCHORED_FIXTURE, "anchored", 0),
        (QUARANTINED_FIXTURE, "quarantined", 3),
    ],
)
def test_verify_json_surface_exposes_anchoring_state(
    fixture: Path,
    expected_status: str,
    expected_exit: int,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload = _run_json(fixture, capsys)
    assert rc == expected_exit
    assert payload["result"] == "pass"
    assert payload["exit_code"] == expected_exit
    assert payload["anchoring"] == {
        "status": expected_status,
        "quarantined": expected_status == "quarantined",
    }

    sdk_result = verify_proof_bundle_file(fixture)
    assert sdk_result.anchoring.status == expected_status
    assert sdk_result.anchoring.quarantined is (expected_status == "quarantined")
    assert sdk_result.ok is True


def test_verify_json_quarantined_bundle_branches_on_exit_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload = _run_json(QUARANTINED_FIXTURE, capsys)

    assert rc == 3
    assert payload["result"] == "pass"
    assert payload["reason_code"] is None
    assert payload["reasons"] == []
    assert payload["anchoring"] == {
        "status": "quarantined",
        "quarantined": True,
    }

