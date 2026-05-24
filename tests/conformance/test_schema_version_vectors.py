# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.verifier import verify_proof_bundle
from attestplane.verify_reason_codes import (
    VERIFY_REASON_SCHEMA_VERSION_MISSING,
    VERIFY_REASON_SCHEMA_UNKNOWN,
    VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION_DIR = ROOT / "tests" / "conformance" / "schema_version"

EXPECTED_CASES = {
    "additive_minor_ok": {
        "ok": True,
        "primary_reason": None,
        "extra_fields": (),
    },
    "additive_with_unknown_field_ok": {
        "ok": True,
        "primary_reason": None,
        "extra_fields": ("future_bundle_field",),
    },
    "missing": {
        "ok": False,
        "primary_reason": VERIFY_REASON_SCHEMA_VERSION_MISSING,
        "extra_fields": (),
    },
    "major_version_ahead": {
        "ok": False,
        "primary_reason": VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
        "extra_fields": (),
    },
    "unknown_required_field": {
        "ok": False,
        "primary_reason": VERIFY_REASON_SCHEMA_UNKNOWN,
        "extra_fields": (),
        "chain_metadata_fields": ("critical_future_field",),
    },
}


def _bundle(case: str) -> dict:
    return json.loads((SCHEMA_VERSION_DIR / case / "bundle.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", sorted(EXPECTED_CASES))
def test_schema_version_vector_set_is_complete(case: str) -> None:
    assert (SCHEMA_VERSION_DIR / case / "bundle.json").exists()


@pytest.mark.parametrize("case", sorted(EXPECTED_CASES))
def test_schema_version_vectors_pin_expected_outcome(case: str) -> None:
    bundle = _bundle(case)
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    expected = EXPECTED_CASES[case]

    assert result.ok is expected["ok"]
    assert result.primary_reason == expected["primary_reason"]
    assert result.secondary_reasons == ()
    for field in expected["extra_fields"]:
        assert field in bundle
    for field in expected.get("chain_metadata_fields", ()):
        assert field in bundle["chain_metadata"]


def test_schema_version_major_version_ahead_keeps_chain_mismatch_ahead_of_version_failure() -> None:
    bundle = _bundle("major_version_ahead")
    bundle["events"][0]["event_hash_hex"] = "f" * 64

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is False
    assert result.primary_reason != VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED
    assert result.primary_reason is not None
    assert VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED in result.secondary_reasons
