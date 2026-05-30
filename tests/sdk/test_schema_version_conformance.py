# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""SDK-facing schema_version conformance coverage.

This keeps the forward-compatible additive-optional acceptance case wired
through the SDK test path, and it documents the paired breaking rejection rule
that remains fail-closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from attestplane.verifier import verify_proof_bundle
from attestplane.verify_reason_codes import VERIFY_REASON_SCHEMA_UNKNOWN

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION_DIR = ROOT / "tests" / "conformance" / "schema_version"
SCHEMA_VERSION_VECTORS = json.loads(
    (SCHEMA_VERSION_DIR / "vectors.json").read_text(encoding="utf-8")
)


def _bundle(case: str) -> dict:
    return json.loads((SCHEMA_VERSION_DIR / case / "bundle.json").read_text(encoding="utf-8"))


def test_schema_version_vectors_document_forward_compat_rule() -> None:
    comment = SCHEMA_VERSION_VECTORS.get("comment")

    assert isinstance(comment, str)
    assert "additive-optional" in comment
    assert "breaking rejected" in comment
    assert "#173" in comment
    assert "#210" in comment


def test_schema_version_additive_optional_field_is_accepted_as_valid() -> None:
    bundle = _bundle("additive_with_unknown_field_ok")

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is True
    assert result.primary_reason is None
    assert result.secondary_reasons == ()
    assert bundle["chain_metadata"]["future_metadata_field"] == "kept"


def test_schema_version_unknown_required_field_is_rejected() -> None:
    bundle = _bundle("unknown_required_field")

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is False
    assert result.primary_reason == VERIFY_REASON_SCHEMA_UNKNOWN
    assert "critical_future_field" in (result.metadata_reason or "")
