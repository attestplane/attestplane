# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.verifier import verify_proof_bundle
from attestplane.verify_errors import VERIFY_METADATA_CLOSURE_FAILED
from attestplane.verify_reason_codes import (
    VERIFY_REASON_SCHEMA_UNKNOWN,
    VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION_DIR = ROOT / "tests" / "conformance" / "schema_version"
SCHEMA_VERSION_VECTORS = json.loads(
    (SCHEMA_VERSION_DIR / "vectors.json").read_text(encoding="utf-8")
)["cases"]
SCHEMA_VERSION_CASE_IDS = {str(vector["case_id"]) for vector in SCHEMA_VERSION_VECTORS}


def _bundle(case: str) -> dict:
    return json.loads(
        (SCHEMA_VERSION_DIR / case / "bundle.json").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("case", sorted(SCHEMA_VERSION_CASE_IDS))
def test_schema_version_vector_set_is_complete(case: str) -> None:
    assert (SCHEMA_VERSION_DIR / case / "bundle.json").exists()


@pytest.mark.parametrize(
    "vector", SCHEMA_VERSION_VECTORS, ids=lambda vector: vector["case_id"]
)
def test_schema_version_vectors_pin_expected_outcome(vector: dict[str, object]) -> None:
    case = str(vector["case_id"])
    bundle = _bundle(case)
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    expected_reason = vector["expected_reason_code"]

    assert result.ok is vector["ok"]
    assert result.primary_reason == expected_reason
    assert result.secondary_reasons == tuple(vector["expected_secondary_reasons"])
    for field in vector.get("extra_fields", ()):
        assert field in bundle
    for field in vector.get("chain_metadata_fields", ()):
        assert field in bundle["chain_metadata"]


def test_schema_version_additive_optional_and_required_fields_are_paired() -> None:
    additive_bundle = _bundle("additive_with_unknown_field_ok")
    required_bundle = _bundle("unknown_required_field")

    additive_result = verify_proof_bundle(
        additive_bundle, require_signed_attestation=True
    )
    required_result = verify_proof_bundle(
        required_bundle, require_signed_attestation=True
    )

    assert additive_result.ok is True
    assert additive_result.primary_reason is None
    assert additive_result.secondary_reasons == ()
    assert additive_bundle["chain_metadata"]["future_metadata_field"] == "kept"
    assert required_result.ok is False
    assert required_result.error_code == VERIFY_METADATA_CLOSURE_FAILED
    assert required_result.primary_reason == VERIFY_REASON_SCHEMA_UNKNOWN
    assert "critical_future_field" in (required_result.metadata_reason or "")


def test_schema_version_major_version_ahead_keeps_chain_mismatch_ahead_of_version_failure() -> (
    None
):
    bundle = _bundle("major_version_ahead")
    bundle["events"][0]["event_hash_hex"] = "f" * 64

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is False
    assert result.primary_reason != VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED
    assert result.primary_reason is not None
    assert VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED in result.secondary_reasons
