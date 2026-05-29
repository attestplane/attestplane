# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Recorded FreeTSA end-to-end coverage.

These tests exercise the live RFC-3161 request/response path with a
recorded DER response so unit tests never touch the network.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

pytest.importorskip("cryptography")
pytest.importorskip("asn1crypto")

from attestplane.anchoring import (
    Anchorer,
    TimestampRequest,
    TSAUnavailableError,
    verify_chain_with_anchors,
)
from attestplane.anchoring.http import (
    FreeTSAProvider,
    HttpTransport,
    RecordedHttpTransport,
)
from attestplane.anchoring.testing import TestTSAAuthority
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.types import EventDraft

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _build_chain() -> list:
    head = genesis_head()
    draft = EventDraft(event_type="eval_event", actor="agent://test", payload={"i": 1})
    ev = chain_extend(
        head,
        draft,
        now=_NOW,
        event_id="00000000-0000-7000-8000-000000000001",
    )
    return [ev]


class _UnavailableTransport(HttpTransport):
    def submit(
        self,
        url: str,
        request_der: bytes,
        *,
        timeout_seconds: float = 30.0,
    ) -> bytes:
        raise TSAUnavailableError("simulated TSA outage")


def test_recorded_freetsa_response_verifies_end_to_end() -> None:
    chain = _build_chain()
    authority = TestTSAAuthority(now=_NOW)
    digest = chain[0].event_hash
    der = authority.sign_timestamp_response(digest, gen_time=_NOW)
    materials = authority.materials()
    provider = FreeTSAProvider(
        transport=RecordedHttpTransport(der),
        trust_roots_der=[materials.root_cert_der],
        ocsp_responses_der=[b"ATTESTPLANE-TEST-OCSP-V1|status=good"],
    )

    assert provider.quarantine_on_unavailable is True
    anchor = provider.request_timestamp(
        TimestampRequest(digest=digest),
        anchored_seq=0,
        now=_NOW,
    )

    result = verify_chain_with_anchors(
        chain,
        [anchor],
        trust_roots_der=[materials.root_cert_der],
        verification_time=_NOW,
        verify_ocsp=False,
    )

    assert result.ok is True
    assert result.anchor_results[0].valid is True
    assert result.anchor_results[0].cert_status == "VALID"


def test_recorded_freetsa_unavailable_quarantines_claim_safe_worker() -> None:
    chain = _build_chain()
    authority = TestTSAAuthority(now=_NOW)
    materials = authority.materials()
    provider = FreeTSAProvider(
        transport=_UnavailableTransport(),
        trust_roots_der=[materials.root_cert_der],
        ocsp_responses_der=[b"ATTESTPLANE-TEST-OCSP-V1|status=good"],
    )
    anchorer = Anchorer(provider, now=lambda: _NOW)
    digest = chain[0].event_hash

    anchorer.enqueue(digest, seq=0)
    result = anchorer.step_once()

    assert result is not None
    assert result.record is None
    assert result.pending.status == "quarantined"
    assert "simulated TSA outage" in (result.pending.last_error or "")
    assert anchorer.stats().quarantined == 1
    assert anchorer.pending_count() == 0
