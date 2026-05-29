# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Versioned contract tests for ``attestplane verify --json``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.cli.verify_json import (
    VERIFY_EXIT_CODE_INVALID,
    VERIFY_EXIT_CODE_QUARANTINED,
    VERIFY_EXIT_CODE_USAGE_OR_IO_ERROR,
    VERIFY_EXIT_CODE_VALID,
)

ROOT = Path(__file__).resolve().parents[2]
VALID_FIXTURE = (
    ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"
)
INVALID_FIXTURE = ROOT / "tests" / "fixtures" / "unknown_schema_version.json"
GOLDEN_FIXTURE = ROOT / "tests" / "fixtures" / "verify_json_golden.json"

VERIFY_JSON_EXIT_CODES = {
    "valid": VERIFY_EXIT_CODE_VALID,
    "invalid": VERIFY_EXIT_CODE_INVALID,
    "quarantined": VERIFY_EXIT_CODE_QUARANTINED,
    "usage_or_error": VERIFY_EXIT_CODE_USAGE_OR_IO_ERROR,
}


def _run_verify(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def test_verify_json_contract_fixture_is_byte_stable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, stdout, stderr = _run_verify(["verify", "--json", str(VALID_FIXTURE)], capsys)

    assert rc == VERIFY_JSON_EXIT_CODES["valid"]
    assert stderr == ""
    assert stdout == GOLDEN_FIXTURE.read_text(encoding="utf-8")

    payload = json.loads(stdout)
    assert payload["schema_version"] == 1
    assert payload["result"] == "pass"
    assert payload["exit_code"] == VERIFY_JSON_EXIT_CODES["valid"]
    assert payload["reason_code"] is None
    assert payload["taxonomy_version"] == 1
    assert payload["reasons"] == []
    assert payload["bundle"]["schema_version"] == 1


def test_verify_json_exit_code_contract_invalid_bundle(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, stdout, stderr = _run_verify(["verify", "--json", str(INVALID_FIXTURE)], capsys)

    payload = json.loads(stdout)

    assert rc == VERIFY_JSON_EXIT_CODES["invalid"]
    assert stderr == ""
    assert payload["schema_version"] == 1
    assert payload["result"] == "fail"
    assert payload["exit_code"] == VERIFY_JSON_EXIT_CODES["invalid"]
    assert payload["reason_code"] == "att.verify.schema_version_unsupported"
    assert payload["taxonomy_version"] == 1
    assert payload["reasons"][0]["code"] == "att.verify.schema_version_unsupported"


def test_verify_json_exit_code_contract_usage_or_io_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing_fixture = tmp_path / "missing.json"
    rc, stdout, stderr = _run_verify(["verify", "--json", str(missing_fixture)], capsys)

    payload = json.loads(stdout)

    assert rc == VERIFY_JSON_EXIT_CODES["usage_or_error"]
    assert stderr == "VERIFY_IO_ERROR\n"
    assert payload["schema_version"] == 1
    assert payload["result"] == "fail"
    assert payload["exit_code"] == VERIFY_JSON_EXIT_CODES["usage_or_error"]
    assert payload["reason_code"] == "att.verify.schema_invalid"
    assert payload["taxonomy_version"] == 1
    assert payload["reasons"][0]["code"] == "att.verify.schema_invalid"


def test_verify_json_exit_code_contract_values_are_distinct() -> None:
    values = set(VERIFY_JSON_EXIT_CODES.values())

    assert values == {0, 1, 2, 3}
    assert VERIFY_JSON_EXIT_CODES["quarantined"] == 3
    assert VERIFY_JSON_EXIT_CODES["quarantined"] not in {
        VERIFY_JSON_EXIT_CODES["valid"],
        VERIFY_JSON_EXIT_CODES["invalid"],
        VERIFY_JSON_EXIT_CODES["usage_or_error"],
    }
