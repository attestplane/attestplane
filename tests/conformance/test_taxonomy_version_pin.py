# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Conformance coverage for the opt-in verifier taxonomy version pin."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verify_reason_codes import VERIFY_REASON_TAXONOMY_VERSION_UNSUPPORTED

ROOT = Path(__file__).resolve().parents[2]
PASS_FIXTURE = ROOT / "fixtures" / "positive" / "minimal.json"

TAXONOMY_VERSION_PIN_VECTORS = (
    {
        "case_id": "taxonomy-version-pin-v1-accepts",
        "fixture": PASS_FIXTURE,
        "pin": "v1",
        "expected_ok": True,
        "expected_rc": 0,
        "expected_reason_code": None,
    },
    {
        "case_id": "taxonomy-version-pin-v0-rejects",
        "fixture": PASS_FIXTURE,
        "pin": "v0",
        "expected_ok": False,
        "expected_rc": 1,
        "expected_reason_code": VERIFY_REASON_TAXONOMY_VERSION_UNSUPPORTED,
    },
)


def test_taxonomy_version_pin_vector_set_is_complete() -> None:
    assert {vector["case_id"] for vector in TAXONOMY_VERSION_PIN_VECTORS} == {
        "taxonomy-version-pin-v1-accepts",
        "taxonomy-version-pin-v0-rejects",
    }


@pytest.mark.parametrize(
    "vector",
    TAXONOMY_VERSION_PIN_VECTORS,
    ids=lambda vector: vector["case_id"],
)
def test_taxonomy_version_pin_vectors_pin_expected_outcome(
    vector: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(
        [
            "verify",
            "--json",
            "--require-taxonomy-version",
            str(vector["pin"]),
            str(vector["fixture"]),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == vector["expected_rc"]
    assert captured.err == ""
    assert payload["result"] == ("pass" if vector["expected_ok"] else "fail")
    assert payload["exit_code"] == vector["expected_rc"]
    assert payload["reason_code"] == vector["expected_reason_code"]
    assert payload["taxonomy_version"] == 1
    if vector["expected_reason_code"] is None:
        assert payload["reasons"] == []
    else:
        assert payload["reasons"][0]["code"] == vector["expected_reason_code"]
        assert payload["reasons"][0]["path"] == "/taxonomy_version"
        assert captured.err == ""
