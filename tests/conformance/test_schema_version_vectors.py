# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from attestplane.verifier import verify_proof_bundle
from attestplane.verify_reason_codes import (
    VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION_DIR = ROOT / "tests" / "conformance" / "schema_version"
SCHEMA_VERSION_VECTORS = json.loads(
    (SCHEMA_VERSION_DIR / "vectors.json").read_text(encoding="utf-8")
)["cases"]
SCHEMA_VERSION_FIXTURE_CASE_IDS = {
    str(vector.get("fixture_case_id", vector["case_id"])) for vector in SCHEMA_VERSION_VECTORS
}


def _bundle(case: str) -> dict:
    return json.loads((SCHEMA_VERSION_DIR / case / "bundle.json").read_text(encoding="utf-8"))


def _bundle_for_vector(vector: dict[str, object]) -> dict:
    fixture_case = str(vector.get("fixture_case_id", vector["case_id"]))
    bundle = _bundle(fixture_case)
    overrides = vector.get("bundle_overrides")
    if isinstance(overrides, dict):
        _apply_overrides(bundle, overrides)
    return bundle


def _apply_overrides(target: dict[str, object], overrides: dict[str, object]) -> None:
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _apply_overrides(target[key], value)
        else:
            target[key] = copy.deepcopy(value)


@pytest.mark.parametrize("case", sorted(SCHEMA_VERSION_FIXTURE_CASE_IDS))
def test_schema_version_vector_set_is_complete(case: str) -> None:
    assert (SCHEMA_VERSION_DIR / case / "bundle.json").exists()


@pytest.mark.parametrize("vector", SCHEMA_VERSION_VECTORS, ids=lambda vector: vector["case_id"])
def test_schema_version_vectors_pin_expected_outcome(vector: dict[str, object]) -> None:
    bundle = _bundle_for_vector(vector)
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    expected_reason = vector["expected_reason_code"]

    assert result.ok is vector["ok"]
    assert result.primary_reason == expected_reason
    assert result.secondary_reasons == tuple(vector["expected_secondary_reasons"])
    for field in vector.get("extra_fields", ()):
        assert field in bundle
    for field in vector.get("chain_metadata_fields", ()):
        assert field in bundle["chain_metadata"]
    for field in vector.get("verification_report_fields", ()):
        assert field in bundle["verification_report"]


def test_schema_version_major_version_ahead_keeps_chain_mismatch_ahead_of_version_failure() -> None:
    bundle = _bundle("major_version_ahead")
    bundle["events"][0]["event_hash_hex"] = "f" * 64

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is False
    assert result.primary_reason != VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED
    assert result.primary_reason is not None
    assert VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED in result.secondary_reasons
