# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.verifier import (
    BundleSchemaError,
    classify_bundle_schema_error,
    verify_proof_bundle,
)
from attestplane.verify_reason_codes import VERIFY_REASON_SCHEMA_UNKNOWN

ROOT = Path(__file__).resolve().parents[2]
VECTORS_DIR = ROOT / "conformance" / "vectors"
MANIFEST_PATH = VECTORS_DIR / "vectors.json"
POSITIVE_BUNDLE_PATH = VECTORS_DIR / "additive_optional_pass.json"
NEGATIVE_BUNDLE_PATH = VECTORS_DIR / "critical_required_fail.json"
README_PATH = VECTORS_DIR / "README.md"


def _load_bundle(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_manifest_cases() -> list[dict]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["cases"]


def test_forward_compatible_additive_manifest_is_complete() -> None:
    cases = _load_manifest_cases()
    case_ids = {case["case_id"] for case in cases}
    assert case_ids == {"additive_optional_pass", "critical_required_fail"}


@pytest.mark.parametrize("case", _load_manifest_cases(), ids=lambda c: c["case_id"])
def test_forward_compatible_additive_vector_matches_manifest(case: dict) -> None:
    vector_path = ROOT / case["path"]
    assert vector_path.exists(), f"vector file missing: {vector_path}"


def test_forward_compatible_additive_optional_passes() -> None:
    bundle = _load_bundle(POSITIVE_BUNDLE_PATH)
    assert "future_field" in bundle
    assert bundle["future_field"] == "kept"

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is True
    assert result.primary_reason is None
    assert result.error_code == "VERIFY_OK"


def test_forward_compatible_additive_required_fails() -> None:
    bundle = _load_bundle(NEGATIVE_BUNDLE_PATH)
    assert "critical_future_field" in bundle

    with pytest.raises(BundleSchemaError) as exc_info:
        verify_proof_bundle(bundle, require_signed_attestation=True)

    assert classify_bundle_schema_error(exc_info.value) == VERIFY_REASON_SCHEMA_UNKNOWN
    assert "critical_future_field" in str(exc_info.value)


def test_forward_compatible_additive_optional_and_required_are_paired() -> None:
    positive_bundle = _load_bundle(POSITIVE_BUNDLE_PATH)
    negative_bundle = _load_bundle(NEGATIVE_BUNDLE_PATH)

    # Positive: unknown additive field passes.
    positive_result = verify_proof_bundle(
        positive_bundle, require_signed_attestation=True
    )
    assert positive_result.ok is True
    assert positive_result.primary_reason is None
    assert "future_field" in positive_bundle

    # Negative: unknown critical field fails closed.
    with pytest.raises(BundleSchemaError) as exc_info:
        verify_proof_bundle(negative_bundle, require_signed_attestation=True)
    assert classify_bundle_schema_error(exc_info.value) == VERIFY_REASON_SCHEMA_UNKNOWN
    assert "critical_future_field" in negative_bundle


def test_forward_compatible_additive_fixture_doc_pins_rule() -> None:
    text = README_PATH.read_text(encoding="utf-8")

    assert "additive-optional" in text
    assert "forward-compatibility" in text
    assert "att.verify.schema_unknown" in text
    assert "#185" in text
    assert "#292" in text
