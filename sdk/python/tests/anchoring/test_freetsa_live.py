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

from attestplane.anchoring import Anchorer, AnchorVerificationError, TimestampRequest
from attestplane.anchoring.http import FreeTSAProvider, RecordedHttpTransport
from attestplane.anchoring.rfc3161 import parse_timestamp_response
from attestplane.anchoring.testing import TestTSAAuthority

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


def test_freetsa_live_untrusted_chain_routes_to_quarantine(monkeypatch: pytest.MonkeyPatch) -> None:
    authority = TestTSAAuthority(now=NOW)
    digest = hashlib.sha256(b"chain-head-quarantine").digest()
    response_der = authority.sign_timestamp_response(digest, gen_time=NOW)
    wrong_root = TestTSAAuthority(now=NOW, common_name="Wrong Root CA").materials().root_cert_der

    monkeypatch.setattr("attestplane.anchoring.http.UrllibHttpTransport", lambda: RecordedHttpTransport(response_der))

    provider = FreeTSAProvider(
        live=True,
        trust_roots_der=[wrong_root],
        ocsp_responses_der=[b"ocsp"],
    )
    with pytest.raises(AnchorVerificationError, match=r"trust root|signature does not verify"):
        provider.request_timestamp(TimestampRequest(digest=digest), now=NOW)

    anchorer = Anchorer(provider, now=lambda: NOW)
    anchorer.enqueue(digest, seq=0)
    result = anchorer.step_once()

    assert result is not None
    assert result.record is None
    assert result.pending.status == "failed_permanent"
    assert "AnchorVerificationError" in (result.pending.last_error or "")


def test_freetsa_live_mode_rejects_transport_override() -> None:
    with pytest.raises(ValueError, match="live mode does not accept"):
        FreeTSAProvider(live=True, transport=RecordedHttpTransport(b"ignored"))


def test_freetsa_recorded_mode_requires_transport() -> None:
    with pytest.raises(ValueError, match="recorded-fixture mode requires a transport"):
        FreeTSAProvider()
