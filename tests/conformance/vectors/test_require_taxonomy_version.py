# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Conformance vectors for ``attestplane verify --require-taxonomy-version``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verify_reason_codes import VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED

ROOT = Path(__file__).resolve().parents[3]
MATCHING_BUNDLE = ROOT / "tests" / "conformance" / "schema_version" / "additive_minor_ok" / "bundle.json"

REQUIRE_TAXONOMY_VERSION_VECTORS = [
    {
        "case_id": "require_taxonomy_version_match",
        "argv": [
            "verify",
            "--json",
            str(MATCHING_BUNDLE),
            "--require-taxonomy-version",
            "1",
        ],
        "expected_exit_code": 0,
        "expected_reason_code": None,
    },
    {
        "case_id": "require_taxonomy_version_mismatch",
        "argv": [
            "verify",
            "--explain",
            str(MATCHING_BUNDLE),
            "--require-taxonomy-version",
            "2",
        ],
        "expected_exit_code": 2,
        "expected_reason_code": VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
    },
]


def test_require_taxonomy_version_vector_set_is_complete() -> None:
    assert {vector["case_id"] for vector in REQUIRE_TAXONOMY_VERSION_VECTORS} == {
        "require_taxonomy_version_match",
        "require_taxonomy_version_mismatch",
    }


@pytest.mark.parametrize("vector", REQUIRE_TAXONOMY_VERSION_VECTORS, ids=lambda vector: vector["case_id"])
def test_require_taxonomy_version_vectors_pin_exit_code_and_reason(
    vector: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(vector["argv"])  # type: ignore[arg-type]
    captured = capsys.readouterr()

    assert rc == vector["expected_exit_code"]
    if vector["case_id"] == "require_taxonomy_version_match":
        payload = json.loads(captured.out)
        assert captured.err == ""
        assert payload["schema_version"] == 1
        assert payload["result"] == "pass"
        assert payload["exit_code"] == 0
        assert payload["reason_code"] is None
        assert payload["reasons"] == []
        return

    assert captured.out.startswith("FAIL: taxonomy version pin rejected")
    assert (
        captured.err
        == (
            "att.verify.schema_version_unsupported "
            "/chain_metadata/evidence_taxonomy_version: "
            "chain_metadata.evidence_taxonomy_version=1; this verifier requires 2\n"
        )
    )
