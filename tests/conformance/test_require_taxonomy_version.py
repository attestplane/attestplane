# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Conformance vectors for ``verify --require-taxonomy-version``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verify_errors import VERIFY_TAXONOMY_VERSION_PINNING_FAILED
from attestplane.verify_reason_codes import VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED

ROOT = Path(__file__).resolve().parents[2]
VALID_BUNDLE = ROOT / "fixtures" / "valid_bundle.att"

VECTOR_CASES = [
    {
        "case_id": "require-taxonomy-version-match-v1",
        "required_taxonomy_version": 1,
        "expected_exit_code": 0,
        "expected_reason_code": None,
        "expected_stderr_code": None,
    },
    {
        "case_id": "require-taxonomy-version-mismatch-v999",
        "required_taxonomy_version": 999,
        "expected_exit_code": 4,
        "expected_reason_code": VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
        "expected_stderr_code": VERIFY_TAXONOMY_VERSION_PINNING_FAILED,
    },
]


def _load_bundle() -> dict[str, object]:
    return json.loads(VALID_BUNDLE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", VECTOR_CASES, ids=lambda case: str(case["case_id"]))
def test_require_taxonomy_version_vectors(
    case: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = _load_bundle()
    assert bundle["chain_metadata"]["evidence_taxonomy_version"] == 1

    rc = main(
        [
            "verify",
            "--require-taxonomy-version",
            str(case["required_taxonomy_version"]),
            str(VALID_BUNDLE),
        ]
    )
    captured = capsys.readouterr()

    assert rc == case["expected_exit_code"]
    assert captured.err == ""
    assert captured.out.startswith("OK" if rc == 0 else "FAIL")

    rc = main(
        [
            "verify",
            "--require-taxonomy-version",
            str(case["required_taxonomy_version"]),
            "--json",
            str(VALID_BUNDLE),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == case["expected_exit_code"]
    assert payload["schema_version"] == 1
    assert payload["result"] == ("pass" if rc == 0 else "fail")
    assert payload["exit_code"] == case["expected_exit_code"]
    assert payload["taxonomy_version"] == 1
    if case["expected_reason_code"] is None:
        assert payload["reason_code"] is None
        assert payload["reasons"] == []
        assert captured.err == ""
    else:
        assert payload["reason_code"] == case["expected_reason_code"]
        assert payload["reasons"][0]["code"] == case["expected_reason_code"]
        assert captured.err == f"{case['expected_stderr_code']}\n"
