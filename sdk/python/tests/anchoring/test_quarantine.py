# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the claim-safe quarantine path."""

from __future__ import annotations

from datetime import UTC, datetime

from attestplane.anchoring import Anchorer, MockTSAProvider, TSAUnavailableError
from attestplane.verifier import verify_proof_bundle
from tests.conformance.anchor_bundle_fixtures import ANCHOR_BUNDLE_FIXTURES

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def test_claim_safe_unavailable_routes_to_quarantine() -> None:
    provider = MockTSAProvider(fail_with=TSAUnavailableError("simulated outage"))
    anchorer = Anchorer(provider, now=lambda: _NOW, claim_safe=True)

    anchorer.enqueue(b"\x0a" * 32, seq=0)
    result = anchorer.step_once()

    assert result is not None
    assert result.record is None
    assert result.pending.status == "quarantined"
    assert anchorer.stats().failed_permanent == 1
    assert anchorer.stats().retries_after_unavailable == 0
    assert anchorer.pending_count() == 0


def test_quarantined_fixture_remains_verifiable() -> None:
    bundle = ANCHOR_BUNDLE_FIXTURES["entries"][1]["bundle"]
    result = verify_proof_bundle(bundle)

    assert result.ok is True
    assert bundle["anchor_status"] == "quarantined"
    assert bundle["verification_report"]["verification_method"] == "canonical-bytes-walk+anchor"
