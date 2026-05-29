# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for :mod:`attestplane.anchoring.http`.

Uses the in-tree :class:`TestTSAAuthority` to generate real RFC-3161
responses, then exercises the HTTP transport path with a recorded
transport so no live network is needed.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

pytest.importorskip("cryptography")
pytest.importorskip("asn1crypto")

from attestplane.anchoring import (
    AnchorVerificationError,
    TimestampRequest,
    TSAUnavailableError,
)
from attestplane.anchoring.http import (
    DigiCertProvider,
    FreeTSAProvider,
    HttpTransport,
    RecordedHttpTransport,
    Rfc3161HttpProvider,
    UrllibHttpTransport,
    make_replay_transport,
)
from attestplane.anchoring.rfc3161 import parse_timestamp_response
from attestplane.anchoring.testing import TestTSAAuthority

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _make_response(digest: bytes, *, nonce: bytes | None = None) -> tuple[bytes, bytes, bytes]:
    authority = TestTSAAuthority(now=_NOW)
    der = authority.sign_timestamp_response(
        digest,
        gen_time=_NOW,
        nonce=nonce,
    )
    materials = authority.materials()
    return der, materials.root_cert_der, b"ATTESTPLANE-TEST-OCSP-V1|status=good"


def test_recorded_transport_replays_bytes() -> None:
    digest = hashlib.sha256(b"x").digest()
    der, _root, _ocsp = _make_response(digest)
    transport = RecordedHttpTransport(der)
    out = transport.submit("https://example.invalid", b"any-request-bytes")
    assert out == der


def test_make_replay_transport_helper() -> None:
    digest = hashlib.sha256(b"x").digest()
    der, _root, _ocsp = _make_response(digest)
    t = make_replay_transport(der)
    assert isinstance(t, HttpTransport)
    assert t.submit("https://example.invalid", b"x") == der


def test_rfc3161_http_provider_round_trips() -> None:
    digest = hashlib.sha256(b"chain-head").digest()
    der, root, ocsp = _make_response(digest)
    provider = Rfc3161HttpProvider(
        "test-provider",
        url="https://example.invalid/tsr",
        transport=RecordedHttpTransport(der),
        trust_roots_der=[root],
        ocsp_responses_der=[ocsp],
    )
    anchor = provider.request_timestamp(
        TimestampRequest(digest=digest),
        anchored_seq=0,
        now=_NOW,
    )
    assert anchor.anchored_event_hash == digest
    assert anchor.tsa_provider_id == "test-provider"
    assert anchor.tsa_token == der
    assert ocsp in anchor.ocsp_responses
    # Cert chain has the leaf extracted from the response + the
    # configured trust root (verifier finds it convenient).
    assert len(anchor.tsa_cert_chain) >= 2


def test_rfc3161_http_provider_rejects_mismatched_digest() -> None:
    real_digest = hashlib.sha256(b"real").digest()
    der, root, ocsp = _make_response(real_digest)
    provider = Rfc3161HttpProvider(
        "p",
        url="https://example.invalid/tsr",
        transport=RecordedHttpTransport(der),
        trust_roots_der=[root],
        ocsp_responses_der=[ocsp],
    )
    other_digest = hashlib.sha256(b"other").digest()
    with pytest.raises(AnchorVerificationError, match="wrong messageImprint"):
        provider.request_timestamp(TimestampRequest(digest=other_digest), now=_NOW)


def test_rfc3161_http_provider_nonce_round_trip() -> None:
    digest = hashlib.sha256(b"nonced").digest()
    der, root, ocsp = _make_response(digest, nonce=b"\xab\xcd\xef\x01")
    provider = Rfc3161HttpProvider(
        "p",
        url="https://example.invalid/tsr",
        transport=RecordedHttpTransport(der),
        trust_roots_der=[root],
        ocsp_responses_der=[ocsp],
    )
    anchor = provider.request_timestamp(
        TimestampRequest(digest=digest, nonce=b"\xab\xcd\xef\x01"),
        now=_NOW,
    )
    parsed = parse_timestamp_response(anchor.tsa_token)
    assert parsed.nonce == int.from_bytes(b"\xab\xcd\xef\x01", "big")


def test_rfc3161_http_provider_rejects_nonce_mismatch() -> None:
    """If TSA returns a nonce different from the one requested, fail."""
    digest = hashlib.sha256(b"x").digest()
    # Generate a response with nonce A, then request with nonce B.
    der, root, ocsp = _make_response(digest, nonce=b"\xaa\xaa\xaa\xaa")
    provider = Rfc3161HttpProvider(
        "p",
        url="https://example.invalid/tsr",
        transport=RecordedHttpTransport(der),
        trust_roots_der=[root],
        ocsp_responses_der=[ocsp],
    )
    with pytest.raises(AnchorVerificationError, match="nonce"):
        provider.request_timestamp(
            TimestampRequest(digest=digest, nonce=b"\xbb\xbb\xbb\xbb"),
            now=_NOW,
        )


def test_rfc3161_http_provider_no_trust_roots_does_not_verify() -> None:
    """When trust_roots_der is None, the provider does not verify the
    signature — it just constructs an AnchorRecord. Verification happens
    later via verify_chain_with_anchors."""
    digest = hashlib.sha256(b"x").digest()
    der, _root, ocsp = _make_response(digest)
    provider = Rfc3161HttpProvider(
        "p",
        url="https://example.invalid/tsr",
        transport=RecordedHttpTransport(der),
        trust_roots_der=None,
        ocsp_responses_der=[ocsp],
    )
    anchor = provider.request_timestamp(
        TimestampRequest(digest=digest),
        anchored_seq=7,
        now=_NOW,
    )
    assert anchor.anchored_seq == 7


def test_rfc3161_http_provider_no_ocsp_empty_tuple() -> None:
    digest = hashlib.sha256(b"x").digest()
    der, root, _ocsp = _make_response(digest)
    provider = Rfc3161HttpProvider(
        "p",
        url="https://example.invalid/tsr",
        transport=RecordedHttpTransport(der),
        trust_roots_der=[root],
        ocsp_responses_der=None,
    )
    anchor = provider.request_timestamp(TimestampRequest(digest=digest), now=_NOW)
    assert anchor.ocsp_responses == ()


def test_rfc3161_http_provider_rejects_empty_provider_id() -> None:
    with pytest.raises(ValueError, match="provider_id"):
        Rfc3161HttpProvider(
            "",
            url="https://x.invalid",
            transport=RecordedHttpTransport(b"any"),
        )


def test_rfc3161_http_provider_rejects_empty_url() -> None:
    with pytest.raises(ValueError, match="url"):
        Rfc3161HttpProvider(
            "p",
            url="",
            transport=RecordedHttpTransport(b"any"),
        )


# --- Pre-configured providers ---


def test_freetsa_provider_defaults() -> None:
    digest = hashlib.sha256(b"x").digest()
    der, root, ocsp = _make_response(digest)
    provider = FreeTSAProvider(
        transport=RecordedHttpTransport(der),
        trust_roots_der=[root],
        ocsp_responses_der=[ocsp],
    )
    assert provider.provider_id == "freetsa.org"
    anchor = provider.request_timestamp(TimestampRequest(digest=digest), now=_NOW)
    assert anchor.tsa_provider_id == "freetsa.org"


def test_digicert_provider_defaults() -> None:
    digest = hashlib.sha256(b"x").digest()
    der, root, ocsp = _make_response(digest)
    provider = DigiCertProvider(
        transport=RecordedHttpTransport(der),
        trust_roots_der=[root],
        ocsp_responses_der=[ocsp],
    )
    assert provider.provider_id == "digicert.tsa-2026"
    anchor = provider.request_timestamp(TimestampRequest(digest=digest), now=_NOW)
    assert anchor.tsa_provider_id == "digicert.tsa-2026"


def test_freetsa_provider_custom_provider_id() -> None:
    digest = hashlib.sha256(b"x").digest()
    der, root, ocsp = _make_response(digest)
    provider = FreeTSAProvider(
        transport=RecordedHttpTransport(der),
        trust_roots_der=[root],
        ocsp_responses_der=[ocsp],
        provider_id="mirror.example",
    )
    assert provider.provider_id == "mirror.example"


# --- UrllibHttpTransport unit (no live network) ---


def test_urllib_transport_rejects_unreachable() -> None:
    transport = UrllibHttpTransport()
    # Use a guaranteed-unreachable host (RFC 6761 reserved TLD).
    with pytest.raises(TSAUnavailableError, match="unreachable"):
        transport.submit(
            "http://this-host-does-not-exist.invalid./tsr",
            b"any-bytes",
            timeout_seconds=2.0,
        )
