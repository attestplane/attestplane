# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Conformance coverage for anchored, quarantined, and unanchored verify JSON states."""

from __future__ import annotations

import json
from pathlib import Path

from attestplane.cli.main import main

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = {
    "unanchored": ROOT / "fixtures" / "positive" / "minimal.json",
    "anchored": ROOT / "fixtures" / "anchored.bundle",
    "quarantined": ROOT / "fixtures" / "quarantined.bundle",
}

CASES = [
    ("unanchored", 0, {"anchored", "quarantined"}),
    ("anchored", 0, {"unanchored", "quarantined"}),
    ("quarantined", 3, {"unanchored", "anchored"}),
]


def _load_payload(fixture: Path, capsys) -> tuple[int, dict[str, object]]:
    rc = main(["verify", "--json", str(fixture)])
    payload = json.loads(capsys.readouterr().out)
    return rc, payload


def test_quarantine_status_vectors_cover_all_states(capsys) -> None:
    for status, expected_exit, forbidden in CASES:
        rc, payload = _load_payload(FIXTURES[status], capsys)
        assert rc == expected_exit
        assert payload["result"] == "pass"
        assert payload["exit_code"] == expected_exit
        anchoring = payload["anchoring"]
        assert anchoring["status"] == status
        assert anchoring["quarantined"] is (status == "quarantined")
        assert anchoring["status"] not in forbidden


def test_quarantine_vector_is_distinct_from_hard_failures(capsys) -> None:
    rc, payload = _load_payload(FIXTURES["quarantined"], capsys)
    assert rc == 3
    assert payload["result"] == "pass"
    assert payload["reason_code"] is None
    assert payload["reasons"] == []
