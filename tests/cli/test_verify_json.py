# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verify_reason_codes import (
    VERIFY_REASON_CANONICAL_MISMATCH,
    VERIFY_REASON_CODE_DESCRIPTIONS,
)

ROOT = Path(__file__).resolve().parents[2]
PASS_FIXTURE = ROOT / "fixtures" / "positive" / "minimal.json"
FAIL_FIXTURE = ROOT / "fixtures" / "reject" / "canonicalization-edge.json"
SCHEMA_VERSION_ADDITIVE_FIXTURE = (
    ROOT
    / "tests"
    / "conformance"
    / "schema_version"
    / "additive_with_unknown_field_ok"
    / "bundle.json"
)


def _run_verify(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, object]]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, json.loads(captured.out)


def test_verify_json_pass_fixture_emits_fixed_schema(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload = _run_verify(["verify", "--json", str(PASS_FIXTURE)], capsys)

    assert rc == 0
    assert payload["schema_version"] == 1
    assert payload["result"] == "pass"
    assert payload["exit_code"] == 0
    assert payload["reason_code"] is None
    assert payload["taxonomy_version"] == 1
    assert payload["reasons"] == []
    assert payload["bundle"] == {
        "schema_version": 1,
        "digest": payload["bundle"]["digest"],
    }
    assert re.fullmatch(r"[0-9a-f]{64}", str(payload["bundle"]["digest"]))


def test_verify_json_fail_fixture_reports_canonicalization_reason(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload = _run_verify(["verify", "--json", str(FAIL_FIXTURE)], capsys)

    assert rc == 1
    assert payload["schema_version"] == 1
    assert payload["result"] == "fail"
    assert payload["exit_code"] == 1
    assert payload["reason_code"] == VERIFY_REASON_CANONICAL_MISMATCH
    assert payload["taxonomy_version"] == 1
    assert payload["bundle"]["schema_version"] == 1
    assert re.fullmatch(r"[0-9a-f]{64}", str(payload["bundle"]["digest"]))
    assert payload["reasons"]
    reason = payload["reasons"][0]
    assert reason["code"] == VERIFY_REASON_CANONICAL_MISMATCH
    assert reason["path"].startswith("/events/")
    assert "canonicalization" in reason["message"]


def test_verify_json_and_explain_keep_json_parseable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload = _run_verify(["verify", "--json", "--explain", str(FAIL_FIXTURE)], capsys)

    assert rc == 1
    assert payload["result"] == "fail"
    assert payload["reason_code"] == VERIFY_REASON_CANONICAL_MISMATCH
    assert payload["taxonomy_version"] == 1
    explanation = payload["explanation"]
    assert isinstance(explanation, list)
    assert explanation
    first = explanation[0]
    assert first["primary_reason"] == VERIFY_REASON_CANONICAL_MISMATCH
    assert first["pointer"].startswith("/events/")
    assert "Unicode-NFC" in first["message"]
    reason = payload["reasons"][0]
    assert reason["code"] == VERIFY_REASON_CANONICAL_MISMATCH
    assert "Unicode-NFC" in reason["message"]
    assert reason["explanation"] == VERIFY_REASON_CODE_DESCRIPTIONS[reason["code"]]


def test_verify_json_explain_success_emits_compact_summary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload = _run_verify(["verify", "--json", "--explain", str(PASS_FIXTURE)], capsys)

    assert rc == 0
    assert payload["result"] == "pass"
    assert payload["reason_code"] is None
    explanation = payload["explanation"]
    assert isinstance(explanation, list)
    assert len(explanation) == 1
    summary = explanation[0]
    assert summary["primary_reason"] is None
    assert summary["pointer"] == "/"
    assert "signer_subject=" in summary["message"]
    assert "schema_version=1" in summary["message"]
    assert "anchor=absent" in summary["message"]


def test_verify_json_additive_optional_schema_fixture_emits_clean_pass(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload = _run_verify(["verify", "--json", str(SCHEMA_VERSION_ADDITIVE_FIXTURE)], capsys)

    assert rc == 0
    assert payload == {
        "schema_version": 1,
        "result": "pass",
        "exit_code": 0,
        "reason_code": None,
        "taxonomy_version": 1,
        "reasons": [],
        "bundle": {
            "schema_version": 1,
            "digest": payload["bundle"]["digest"],
        },
    }
