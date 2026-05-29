# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""SDK-facing schema_version conformance smoke tests.

This keeps the additive-optional acceptance vector wired into the SDK test
surface so ``pytest tests/sdk -k schema_version -q`` exercises the same
fixture contract as the conformance suite.
"""

from __future__ import annotations

import json
from pathlib import Path

from attestplane.verifier import verify_proof_bundle


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION_DIR = ROOT / "tests" / "conformance" / "schema_version"
SCHEMA_VERSION_FIXTURE = (
    SCHEMA_VERSION_DIR / "additive_with_unknown_field_ok" / "bundle.json"
)
SCHEMA_VERSION_VECTORS = json.loads(
    (SCHEMA_VERSION_DIR / "vectors.json").read_text(encoding="utf-8")
)


def test_schema_version_additive_optional_fixture_passes_via_sdk() -> None:
    bundle = json.loads(SCHEMA_VERSION_FIXTURE.read_text(encoding="utf-8"))
    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is True
    assert result.primary_reason is None
    assert result.secondary_reasons == ()
    assert "forward-compatibility" in SCHEMA_VERSION_VECTORS["description"]
    assert "accepted as valid" in SCHEMA_VERSION_VECTORS["description"]
    assert bundle["chain_metadata"]["future_metadata_field"] == "kept"
