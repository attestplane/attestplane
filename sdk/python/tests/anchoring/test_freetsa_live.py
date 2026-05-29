# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the FreeTSA anchoring path.

The default mode in CI is recorded-fixture replay so unit coverage never
depends on live network access. A live smoke path is available behind an
explicit opt-in environment flag for local/manual verification.
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime

import pytest

pytest.importorskip("cryptography")
pytest.importorskip("asn1crypto")

from attestplane.anchoring import (
    Anchorer,
    FreeTSAProvider,
    MockTSAProvider,
    TimestampRequest,
    TSAUnavailableError,
)
from attestplane.anchoring.http import RecordedHttpTransport
from attestplane.anchoring.testing import TestTSAAuthority

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_LIVE_FREETSA_ENV = "ATTESTPLANE_LIVE_FREETSA"


def _make_recorded_response(digest: bytes) -> tuple[bytes, bytes, bytes]:
    authority = TestTSAAuthority(now=_NOW)
    response = authority.sign_timestamp_response(digest, gen_time=_NOW)
    materials = authority.materials()
    ocsp = b"ATTESTPLANE-TEST-OCSP-V1|status=good"
    return response, materials.root_cert_der, ocsp


def test_freetsa_provider_replays_recorded_response_by_default() -> None:
    digest = hashlib.sha256(b"freetsa-recorded").digest()
    response, root, ocsp = _make_recorded_response(digest)

    provider = FreeTSAProvider(
        transport=RecordedHttpTransport(response),
        trust_roots_der=[root],
        ocsp_responses_der=[ocsp],
    )
    anchor = provider.request_timestamp(TimestampRequest(digest=digest), anchored_seq=0, now=_NOW)

    assert anchor.anchored_event_hash == digest
    assert anchor.tsa_provider_id == "freetsa.org"


@pytest.mark.skipif(os.getenv(_LIVE_FREETSA_ENV) != "1", reason="live FreeTSA smoke test disabled")
def test_freetsa_live_endpoint_smoke() -> None:
    digest = hashlib.sha256(b"freetsa-live").digest()
    provider = FreeTSAProvider()

    anchor = provider.request_timestamp(TimestampRequest(digest=digest), anchored_seq=0)

    assert anchor.anchored_event_hash == digest
    assert anchor.tsa_provider_id == "freetsa.org"
    assert len(anchor.tsa_token) > 0


def test_claim_safe_tsa_unavailable_routes_to_quarantine_with_free_tsa_provider() -> None:
    digest = hashlib.sha256(b"freetsa-quarantine").digest()
    provider = MockTSAProvider(fail_with=TSAUnavailableError("simulated outage"))
    anchorer = Anchorer(provider, now=lambda: _NOW, claim_safe=True)

    anchorer.enqueue(digest, seq=0)
    result = anchorer.step_once()

    assert result is not None
    assert result.record is None
    assert result.pending.status == "quarantined"
    assert anchorer.stats().failed_permanent == 1
