# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.cli.verify_json import (
    VERIFY_EXIT_CODE_INVALID,
    VERIFY_EXIT_CODE_QUARANTINED,
    VERIFY_EXIT_CODE_USAGE_ERROR,
    VERIFY_EXIT_CODE_VALID,
    VerifyJsonOutcome,
)
from attestplane.verify_reason_codes import (
    VERIFY_REASON_CANONICAL_MISMATCH,
    VERIFY_REASON_CODE_DESCRIPTIONS,
    VERIFY_REASON_STRUCTURE_INVALID,
)

ROOT = Path(__file__).resolve().parents[2]
PASS_FIXTURE = ROOT / "fixtures" / "positive" / "minimal.json"
FAIL_FIXTURE = ROOT / "fixtures" / "reject" / "canonicalization-edge.json"
VERIFY_JSON_GOLDEN = ROOT / "tests" / "fixtures" / "verify_json_golden.json"


def _run_verify(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object]]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, json.loads(captured.out)


def _run_verify_raw(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


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


def test_verify_json_contract_fixture_is_byte_stable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, stdout, stderr = _run_verify_raw(
        ["verify", "--json", str(PASS_FIXTURE)], capsys
    )

    assert rc == VERIFY_EXIT_CODE_VALID
    assert stderr == ""
    assert stdout == VERIFY_JSON_GOLDEN.read_text(encoding="utf-8")


def test_verify_result_schema_pins_exit_code_contract() -> None:
    schema = json.loads(
        (ROOT / "schemas" / "cli" / "verify-result-v1.json").read_text(encoding="utf-8")
    )

    assert schema["properties"]["exit_code"]["enum"] == [
        VERIFY_EXIT_CODE_VALID,
        VERIFY_EXIT_CODE_INVALID,
        VERIFY_EXIT_CODE_USAGE_ERROR,
        VERIFY_EXIT_CODE_QUARANTINED,
    ]


def test_verify_exit_code_contract_distinguishes_invalid_quarantined_and_usage(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rc, payload = _run_verify(["verify", "--json", str(FAIL_FIXTURE)], capsys)

    assert rc == VERIFY_EXIT_CODE_INVALID
    assert payload["exit_code"] == VERIFY_EXIT_CODE_INVALID

    rc, stdout, stderr = _run_verify_raw(["verify", "--json"], capsys)

    assert rc == VERIFY_EXIT_CODE_USAGE_ERROR
    assert stdout == ""
    assert "bundle path is required" in stderr

    def fake_build_verify_json_outcome(
        *args: object, **kwargs: object
    ) -> VerifyJsonOutcome:
        return VerifyJsonOutcome(
            payload={
                "schema_version": 1,
                "result": "fail",
                "exit_code": VERIFY_EXIT_CODE_QUARANTINED,
                "reason_code": VERIFY_REASON_STRUCTURE_INVALID,
                "taxonomy_version": 1,
                "reasons": [
                    {
                        "code": VERIFY_REASON_STRUCTURE_INVALID,
                        "path": "/verification_report",
                        "message": "quarantined by upstream policy",
                    }
                ],
                "bundle": {
                    "schema_version": 1,
                    "digest": "0" * 64,
                },
            },
            exit_code=VERIFY_EXIT_CODE_QUARANTINED,
            stderr_code=None,
        )

    monkeypatch.setattr(
        "attestplane.cli.main.build_verify_json_outcome", fake_build_verify_json_outcome
    )
    rc, stdout, stderr = _run_verify_raw(
        ["verify", "--json", str(PASS_FIXTURE)], capsys
    )
    payload = json.loads(stdout)

    assert rc == VERIFY_EXIT_CODE_QUARANTINED
    assert stderr == ""
    assert payload["exit_code"] == VERIFY_EXIT_CODE_QUARANTINED


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
    rc, payload = _run_verify(
        ["verify", "--json", "--explain", str(FAIL_FIXTURE)], capsys
    )

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
    rc, payload = _run_verify(
        ["verify", "--json", "--explain", str(PASS_FIXTURE)], capsys
    )

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
    assert "taxonomy_version=1" in summary["message"]
    assert "anchor=absent" in summary["message"]
