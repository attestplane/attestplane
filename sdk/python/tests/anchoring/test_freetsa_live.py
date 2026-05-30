# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Claim-safe FreeTSA live-path coverage.

The live path is exercised without hitting the network by monkeypatching the
stdlib transport constructor. This keeps the test deterministic while still
proving the provider can route through the live code path when explicitly
enabled.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

pytest.importorskip("cryptography")
pytest.importorskip("asn1crypto")

from attestplane import EventDraft
from attestplane.anchoring import (
    Anchorer,
    AnchorVerificationError,
    TimestampRequest,
    verify_chain_with_anchors,
)
from attestplane.anchoring.http import FreeTSAProvider, RecordedHttpTransport
from attestplane.anchoring.rfc3161 import parse_timestamp_response
from attestplane.anchoring.testing import TestTSAAuthority
from attestplane.hashchain import chain_extend, genesis_head

NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def test_freetsa_live_mode_uses_stdlib_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    authority = TestTSAAuthority(now=NOW)
    digest = hashlib.sha256(b"chain-head").digest()
    response_der = authority.sign_timestamp_response(digest, gen_time=NOW)
    fake_transport = RecordedHttpTransport(response_der)

    monkeypatch.setattr("attestplane.anchoring.http.UrllibHttpTransport", lambda: fake_transport)

    provider = FreeTSAProvider(
        live=True,
        trust_roots_der=[authority.materials().root_cert_der],
        ocsp_responses_der=[b"ocsp"],
    )
    anchor = provider.request_timestamp(TimestampRequest(digest=digest), now=NOW)

    assert anchor.tsa_provider_id == "freetsa.org"
    assert anchor.tsa_token == response_der
    parsed = parse_timestamp_response(anchor.tsa_token)
    assert parsed.message_imprint == digest

    chain = []
    head = genesis_head()
    draft = EventDraft(event_type="eval_event", actor="agent://test", payload={"score": 1})
    event = chain_extend(head, draft, now=NOW, event_id="00000000-0000-7000-8000-000000000001")
    chain.append(event)
    assert event.seq == 0

    result = verify_chain_with_anchors(
        chain,
        [anchor],
        trust_roots_der=[authority.materials().root_cert_der],
        verification_time=NOW,
        verify_ocsp=False,
    )
    assert result.ok is True
    assert result.anchor_results[0].valid is True
    assert result.anchor_results[0].cert_status == "VALID"


def test_freetsa_live_mode_rejects_transport_override() -> None:
    with pytest.raises(ValueError, match="live mode does not accept"):
        FreeTSAProvider(live=True, transport=RecordedHttpTransport(b"ignored"))


def test_freetsa_recorded_mode_requires_transport() -> None:
    with pytest.raises(ValueError, match="recorded-fixture mode requires a transport"):
        FreeTSAProvider()


def test_freetsa_live_mode_promotes_transport_outage_to_quarantine(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailingTransport(RecordedHttpTransport):
        def submit(self, url: str, request_der: bytes, *, timeout_seconds: float = 30.0) -> bytes:  # type: ignore[override]
            from attestplane.anchoring import TSAUnavailableError

            raise TSAUnavailableError("simulated FreeTSA outage")

    monkeypatch.setattr("attestplane.anchoring.http.UrllibHttpTransport", lambda: _FailingTransport(b"ignored"))

    authority = TestTSAAuthority(now=NOW)
    provider = FreeTSAProvider(
        live=True,
        trust_roots_der=[authority.materials().root_cert_der],
        ocsp_responses_der=[b"ocsp"],
    )

    with pytest.raises(AnchorVerificationError, match="quarantining bundle"):
        provider.request_timestamp(TimestampRequest(digest=hashlib.sha256(b"chain-head").digest()), now=NOW)


def test_freetsa_live_mode_outage_quarantines_in_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailingTransport(RecordedHttpTransport):
        def submit(self, url: str, request_der: bytes, *, timeout_seconds: float = 30.0) -> bytes:  # type: ignore[override]
            from attestplane.anchoring import TSAUnavailableError

            raise TSAUnavailableError("simulated FreeTSA outage")

    monkeypatch.setattr("attestplane.anchoring.http.UrllibHttpTransport", lambda: _FailingTransport(b"ignored"))

    authority = TestTSAAuthority(now=NOW)
    provider = FreeTSAProvider(
        live=True,
        trust_roots_der=[authority.materials().root_cert_der],
        ocsp_responses_der=[b"ocsp"],
    )
    anchorer = Anchorer(provider, now=lambda: NOW)
    anchorer.enqueue(hashlib.sha256(b"chain-head").digest(), seq=0)

    result = anchorer.step_once()

    assert result is not None
    assert result.record is None
    assert result.pending.status == "failed_permanent"
