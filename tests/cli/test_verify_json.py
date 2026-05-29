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
    VERIFY_REASON_TAXONOMY_VERSION_MISMATCH,
)

ROOT = Path(__file__).resolve().parents[2]
PASS_FIXTURE = ROOT / "fixtures" / "positive" / "minimal.json"
FAIL_FIXTURE = ROOT / "fixtures" / "reject" / "canonicalization-edge.json"


def _run_verify(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, object]]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, json.loads(captured.out)


def _run_verify_raw(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
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


def test_verify_json_taxonomy_version_requirement_matches_no_flag_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc_base, out_base, err_base = _run_verify_raw(["verify", "--json", str(PASS_FIXTURE)], capsys)
    rc_flag, out_flag, err_flag = _run_verify_raw(
        ["verify", "--json", "--require-taxonomy-version", "1", str(PASS_FIXTURE)],
        capsys,
    )
    rc_explain_base, explain_out_base, explain_err_base = _run_verify_raw(
        ["verify", "--json", "--explain", str(PASS_FIXTURE)],
        capsys,
    )
    rc_explain_flag, explain_out_flag, explain_err_flag = _run_verify_raw(
        [
            "verify",
            "--json",
            "--explain",
            "--require-taxonomy-version",
            "1",
            str(PASS_FIXTURE),
        ],
        capsys,
    )

    assert rc_base == 0
    assert rc_flag == 0
    assert rc_explain_base == 0
    assert rc_explain_flag == 0
    assert err_base == ""
    assert err_flag == ""
    assert explain_err_base == ""
    assert explain_err_flag == ""
    assert out_flag == out_base
    assert explain_out_flag == explain_out_base


def test_verify_json_taxonomy_version_requirement_mismatch_reports_reason_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, out, err = _run_verify_raw(
        [
            "verify",
            "--json",
            "--explain",
            "--require-taxonomy-version",
            "0.0.0",
            str(PASS_FIXTURE),
        ],
        capsys,
    )
    payload = json.loads(out)

    assert rc == 1
    assert err == ""
    assert payload["result"] == "fail"
    assert payload["exit_code"] == 1
    assert payload["reason_code"] == VERIFY_REASON_TAXONOMY_VERSION_MISMATCH
    assert payload["taxonomy_version"] == 1
    assert payload["reasons"][0]["code"] == VERIFY_REASON_TAXONOMY_VERSION_MISMATCH
    assert payload["reasons"][0]["path"] == "/taxonomy_version"
    assert "0.0.0" in payload["reasons"][0]["message"]
    assert payload["reasons"][0]["explanation"] == VERIFY_REASON_CODE_DESCRIPTIONS[
        payload["reasons"][0]["code"]
    ]
    explanation = payload["explanation"][0]
    assert explanation["primary_reason"] == VERIFY_REASON_TAXONOMY_VERSION_MISMATCH
    assert explanation["pointer"] == "/taxonomy_version"
    assert "0.0.0" in explanation["message"]
