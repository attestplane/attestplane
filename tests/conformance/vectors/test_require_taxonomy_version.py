# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Conformance coverage for ``verify --require-taxonomy-version``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verify_reason_codes import (
    VERIFY_REASON_TAXONOMY_VERSION,
    VERIFY_REASON_TAXONOMY_VERSION_MISMATCH,
)

ROOT = Path(__file__).resolve().parents[3]
VALID_FIXTURE = ROOT / "fixtures" / "positive" / "minimal.json"

CASES = [
    {
        "case_id": "require-taxonomy-version-match-v1",
        "required_version": 1,
        "expected_exit_code": 0,
        "expected_reason_code": None,
    },
    {
        "case_id": "require-taxonomy-version-mismatch-v2",
        "required_version": 2,
        "expected_exit_code": 1,
        "expected_reason_code": VERIFY_REASON_TAXONOMY_VERSION_MISMATCH,
    },
]


def _run_verify(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object], str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, json.loads(captured.out), captured.err


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["case_id"])
def test_require_taxonomy_version_vectors_pin_reason_and_exit_code(
    case: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, stderr = _run_verify(
        [
            "verify",
            "--json",
            "--require-taxonomy-version",
            str(case["required_version"]),
            str(VALID_FIXTURE),
        ],
        capsys,
    )

    assert rc == case["expected_exit_code"]
    assert payload["schema_version"] == 1
    assert payload["taxonomy_version"] == VERIFY_REASON_TAXONOMY_VERSION
    assert payload["exit_code"] == case["expected_exit_code"]
    assert payload["reason_code"] == case["expected_reason_code"]
    if case["expected_exit_code"] == 0:
        assert payload["result"] == "pass"
        assert payload["reasons"] == []
        assert stderr == ""
    else:
        assert payload["result"] == "fail"
        assert payload["reasons"]
        assert payload["reasons"][0]["code"] == VERIFY_REASON_TAXONOMY_VERSION_MISMATCH
        assert stderr == ""


def test_require_taxonomy_version_mismatch_fails_closed_in_human_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(
        [
            "verify",
            "--require-taxonomy-version",
            "2",
            str(VALID_FIXTURE),
        ]
    )
    captured = capsys.readouterr()

    assert rc == 1
    assert "taxonomy version requirement failed" in captured.out
    assert "required taxonomy_version=2" in captured.out
    assert captured.err == ""
