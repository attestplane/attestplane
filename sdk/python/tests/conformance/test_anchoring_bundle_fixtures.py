# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Conformance coverage for claim-safe proof-bundle anchor state fixtures."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import jsonschema
from attestplane.verifier import verify_proof_bundle

from .anchor_bundle_fixtures import (
    ANCHOR_BUNDLE_FIXTURES,
    ANCHOR_BUNDLE_FIXTURES_JSON,
)

_SCHEMA_PATH = Path(__file__).resolve().parents[4] / "schemas" / "v1" / "proof_bundle.schema.json"
_EXPECTED_ANCHOR_BUNDLE_FIXTURES_SHA256 = "6fe905cc26ac79a8db6c0d7608268ad1c088861e2d78420ebca83c1209a2c57e"


def _schema() -> dict[str, object]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def test_anchoring_bundle_fixtures_are_byte_stable() -> None:
    assert sha256(ANCHOR_BUNDLE_FIXTURES_JSON.encode("utf-8")).hexdigest() == _EXPECTED_ANCHOR_BUNDLE_FIXTURES_SHA256


def test_anchoring_bundle_fixtures_validate_against_schema() -> None:
    schema = _schema()
    assert schema["properties"]["anchor_status"]["enum"] == ["unanchored", "pending", "anchored", "quarantined"]
    for entry in ANCHOR_BUNDLE_FIXTURES["entries"]:
        bundle = entry["bundle"]
        jsonschema.validate(bundle, schema)


def test_anchoring_bundle_fixtures_remain_verifiable() -> None:
    for entry in ANCHOR_BUNDLE_FIXTURES["entries"]:
        bundle = entry["bundle"]
        result = verify_proof_bundle(bundle)
        assert result.ok is True
        assert bundle["anchor_status"] in {"anchored", "quarantined"}
        assert bundle["verification_report"]["verification_method"] == "canonical-bytes-walk+anchor"
