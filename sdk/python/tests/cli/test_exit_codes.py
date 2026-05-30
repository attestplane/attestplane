# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Deterministic exit-code contract for ``attestplane verify --json``.

Contract table:

- pass -> 0
- fail -> 1
- quarantine -> 2
- taxonomy-mismatch -> 2
- usage error -> 3
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verify_errors import VERIFY_SCHEMA_ERROR
from attestplane.verify_reason_codes import (
    VERIFY_REASON_CANONICAL_MISMATCH,
    VERIFY_REASON_SCHEMA_INVALID,
    VERIFY_REASON_SCHEMA_UNKNOWN,
    VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
)

ROOT = Path(__file__).resolve().parents[4]
CONFORMANCE_FIXTURES = ROOT / "fixtures" / "conformance"
PASS_FIXTURE = CONFORMANCE_FIXTURES / "valid_bundle.json"
FAIL_FIXTURE = ROOT / "fixtures" / "reject" / "canonicalization-edge.json"
QUARANTINE_FIXTURE = CONFORMANCE_FIXTURES / "unknown_required_field.att"


def _run_verify(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, object], str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, json.loads(captured.out), captured.err


@pytest.mark.parametrize(
    ("case_id", "argv", "expected_rc", "expected_reason"),
    [
        (
            "pass",
            ["verify", "--json", str(PASS_FIXTURE)],
            0,
            None,
        ),
        (
            "fail",
            ["verify", "--json", str(FAIL_FIXTURE)],
            1,
            VERIFY_REASON_CANONICAL_MISMATCH,
        ),
        (
            "quarantine",
            ["verify", "--json", str(QUARANTINE_FIXTURE)],
            2,
            VERIFY_REASON_SCHEMA_UNKNOWN,
        ),
        (
            "taxonomy_mismatch",
            ["verify", "--json", "--require-taxonomy-version", "2", str(PASS_FIXTURE)],
            2,
            VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
        ),
    ],
)
def test_verify_json_exit_code_contract(
    case_id: str,
    argv: list[str],
    expected_rc: int,
    expected_reason: str | None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, stderr = _run_verify(argv, capsys)

    assert rc == expected_rc, case_id
    assert payload["schema_version"] == 1
    assert payload["exit_code"] == expected_rc
    assert payload["result"] == ("pass" if expected_rc == 0 else "fail")
    if expected_reason is None:
        assert payload["reason_code"] is None
        assert payload["reasons"] == []
    else:
        assert payload["reason_code"] == expected_reason
        assert payload["reasons"][0]["code"] == expected_reason
    assert stderr == ""


def test_verify_json_usage_error_contract(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")

    rc, payload, stderr = _run_verify(["verify", "--json", str(bad)], capsys)

    assert rc == 3
    assert payload["schema_version"] == 1
    assert payload["exit_code"] == 3
    assert payload["result"] == "fail"
    assert payload["reason_code"] == VERIFY_REASON_SCHEMA_INVALID
    assert payload["reasons"][0]["code"] == VERIFY_REASON_SCHEMA_INVALID
    assert stderr == f"{VERIFY_SCHEMA_ERROR}\n"
