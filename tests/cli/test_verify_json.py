# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.cli.verify_json import VERIFY_JSON_ERROR_CANON_MISMATCH
from attestplane.verify_reason_codes import VERIFY_REASON_CANONICAL_MISMATCH

ROOT = Path(__file__).resolve().parents[2]
PASS_FIXTURE = ROOT / "fixtures" / "positive" / "minimal.json"
FAIL_FIXTURE = ROOT / "fixtures" / "reject" / "canonicalization-edge.json"


def _run_verify(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, dict[str, object], str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, json.loads(captured.out), captured.out


def test_verify_json_pass_fixture_emits_fixed_schema(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, stdout = _run_verify(["verify", "--json", str(PASS_FIXTURE)], capsys)

    assert rc == 0
    assert stdout.count("\n") == 1
    assert payload["schema_version"] == 1
    assert payload["result"] == "pass"
    assert payload["failed_gates"] == []
    assert payload["bundle_id"] == "p3-cli-proofbundle"
    assert "vector_id" not in payload


def test_verify_json_fail_fixture_reports_canonicalization_reason(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, stdout = _run_verify(["verify", "--json", str(FAIL_FIXTURE)], capsys)

    assert rc == 1
    assert stdout.count("\n") == 1
    assert payload["schema_version"] == 1
    assert payload["result"] == "fail"
    assert payload["bundle_id"] == "p3-cli-proofbundle"
    assert payload["failed_gates"] == [
        {"gate": "canonicalization", "error_code": VERIFY_JSON_ERROR_CANON_MISMATCH}
    ]


def test_verify_json_and_explain_keep_json_parseable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, stdout = _run_verify(["verify", "--json", "--explain", str(FAIL_FIXTURE)], capsys)

    assert rc == 1
    assert stdout.count("\n") == 1
    assert payload["result"] == "fail"
    explanation = payload["explanation"]
    assert isinstance(explanation, list)
    assert explanation
    first = explanation[0]
    assert first["primary_reason"] == VERIFY_REASON_CANONICAL_MISMATCH
    assert first["pointer"].startswith("/events/")
    assert "Unicode-NFC" in first["message"]
    assert payload["failed_gates"] == [
        {"gate": "canonicalization", "error_code": VERIFY_JSON_ERROR_CANON_MISMATCH}
    ]


def test_verify_json_explain_success_emits_compact_summary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, stdout = _run_verify(["verify", "--json", "--explain", str(PASS_FIXTURE)], capsys)

    assert rc == 0
    assert stdout.count("\n") == 1
    assert payload["result"] == "pass"
    explanation = payload["explanation"]
    assert isinstance(explanation, list)
    assert len(explanation) == 1
    summary = explanation[0]
    assert summary["primary_reason"] is None
    assert summary["pointer"] == "/"
    assert "signer_subject=" in summary["message"]
    assert "schema_version=1" in summary["message"]
    assert "anchor=absent" in summary["message"]
    assert payload["failed_gates"] == []
