# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk" / "python" / "src"))

from attestplane.verifier import verify_proof_bundle  # noqa: E402

VECTOR_DIR = ROOT / "tests" / "conformance" / "vectors" / "negative"
EXPECTED_CASE_IDS = {
    "empty-bundle",
    "attestations-array-empty",
    "attestation-missing-signature",
    "attestation-missing-subject-digest",
}


def _vectors() -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(VECTOR_DIR.glob("*.json"))
    ]


def test_negative_minimum_schema_vector_set_is_complete() -> None:
    assert {vector["case_id"] for vector in _vectors()} == EXPECTED_CASE_IDS


@pytest.mark.parametrize("vector", _vectors(), ids=lambda vector: vector["case_id"])
def test_negative_minimum_schema_vectors_pin_error_code(vector: dict) -> None:
    result = verify_proof_bundle(vector["bundle"], **vector["verify_options"])

    assert result.ok is vector["expected_ok"]
    assert result.error_code == vector["expected_error_code"]
