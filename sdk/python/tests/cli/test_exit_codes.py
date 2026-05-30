# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Deterministic exit-code contract tests for ``attestplane verify``.

The stable table is:

- pass -> 0
- fail -> 1
- quarantine -> 2
- taxonomy mismatch -> 2
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
TAXONOMY_MISMATCH_FIXTURE = ROOT / "tests" / "conformance" / "schema_version" / "major_version_ahead" / "bundle.json"


def _run_verify(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, object], str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, json.loads(captured.out), captured.err


@pytest.mark.parametrize(
    ("label", "fixture_path", "expected_exit_code", "expected_reason_code"),
    [
        ("pass", PASS_FIXTURE, 0, None),
        ("fail", FAIL_FIXTURE, 1, VERIFY_REASON_CANONICAL_MISMATCH),
        ("quarantine", QUARANTINE_FIXTURE, 2, VERIFY_REASON_SCHEMA_UNKNOWN),
        (
            "taxonomy_mismatch",
            TAXONOMY_MISMATCH_FIXTURE,
            2,
            VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
        ),
    ],
)
def test_verify_exit_code_table(
    label: str,
    fixture_path: Path,
    expected_exit_code: int,
    expected_reason_code: str | None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, stderr = _run_verify(["verify", "--json", str(fixture_path)], capsys)

    assert rc == expected_exit_code, label
    assert payload["exit_code"] == expected_exit_code
    assert payload["reason_code"] == expected_reason_code
    assert payload["result"] == ("pass" if expected_exit_code == 0 else "fail")
    assert stderr == ""


def test_verify_exit_code_usage_error_for_malformed_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = tmp_path / "bad.json"
    bundle.write_text("{", encoding="utf-8")

    rc, payload, stderr = _run_verify(["verify", "--json", str(bundle)], capsys)

    assert rc == 3
    assert payload["exit_code"] == 3
    assert payload["reason_code"] == VERIFY_REASON_SCHEMA_INVALID
    assert payload["result"] == "fail"
    assert stderr == f"{VERIFY_SCHEMA_ERROR}\n"
