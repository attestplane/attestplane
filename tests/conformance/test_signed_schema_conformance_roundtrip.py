# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Positive signed-schema conformance selector for Issue #139."""

from __future__ import annotations

import json
from pathlib import Path

from attestplane.verifier import verify_proof_bundle
from attestplane.verify_errors import VERIFY_OK
from tests.verifier.test_signed_schema_roundtrip import rebuild_signed_schema_fixture

ROOT = Path(__file__).resolve().parents[2]
SIGNED_SCHEMA_FIXTURE = ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"


def test_signed_schema_positive_fixture_roundtrip_passes_strict_conformance() -> None:
    bundle = json.loads(SIGNED_SCHEMA_FIXTURE.read_text(encoding="utf-8"))
    rebuilt = rebuild_signed_schema_fixture(bundle)

    result = verify_proof_bundle(
        rebuilt,
        require_non_empty=True,
        require_signed_attestation=True,
    )

    assert result.ok is True
    assert result.error_code == VERIFY_OK
    assert result.signed_attestation_schema_ok is True
