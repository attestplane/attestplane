# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Claim-safe quarantine replay fixtures for anchoring proof bundles."""

from __future__ import annotations

import json
from pathlib import Path

from attestplane.proof_bundle import build_auditor_export
from attestplane.verifier import verify_proof_bundle

FIXTURES = Path(__file__).with_name("fixtures")


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_anchored_bundle_fixture_replays_cleanly() -> None:
    bundle = _load("freetsa_anchored_bundle.json")

    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    export = build_auditor_export(bundle)

    assert result.ok is True
    assert result.metadata_ok is True
    assert bundle["verification_report"]["anchor_status"] == "anchored"
    assert export["chain_summary"]["anchor_status"] == "anchored"


def test_quarantined_bundle_fixture_fails_closed() -> None:
    bundle = _load("freetsa_quarantined_bundle.json")

    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    export = build_auditor_export(bundle)

    assert result.ok is False
    assert result.metadata_ok is False
    assert "anchor_status=quarantined" in (result.metadata_reason or "")
    assert export["chain_summary"]["anchor_status"] == "quarantined"
