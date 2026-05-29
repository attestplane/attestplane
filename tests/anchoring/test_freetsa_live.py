# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Offline regression coverage for FreeTSA anchoring verification.

These tests exercise the live FreeTSA provider code path with a recorded
RFC-3161 response so they remain deterministic and do not require
network access.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

pytest.importorskip("cryptography")
pytest.importorskip("asn1crypto")

from attestplane.anchoring import (
    AnchorQuarantineError,
    AnchorVerificationError,
    TimestampRequest,
)
from attestplane.anchoring.http import FreeTSAProvider, RecordedHttpTransport
from attestplane.anchoring.rfc3161 import parse_timestamp_response, verify_timestamp_token
from attestplane.anchoring.testing import TestTSAAuthority

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_OCSP_OK = b"ATTESTPLANE-TEST-OCSP-V1|status=good"


def _make_authority() -> TestTSAAuthority:
    return TestTSAAuthority(now=_NOW)


def test_freetsa_live_offline_passes() -> None:
    authority = _make_authority()
    digest = hashlib.sha256(b"freetsa-live-pass").digest()
    der = authority.sign_timestamp_response(digest, gen_time=_NOW)
    materials = authority.materials()
    provider = FreeTSAProvider(
        transport=RecordedHttpTransport(der),
        trust_roots_der=[materials.root_cert_der],
        ocsp_responses_der=[_OCSP_OK],
    )

    anchor = provider.request_timestamp(TimestampRequest(digest=digest), now=_NOW)
    assert anchor.tsa_provider_id == "freetsa.org"
    parsed = parse_timestamp_response(anchor.tsa_token)
    verify_timestamp_token(
        parsed,
        expected_digest=digest,
        trust_roots_der=[materials.root_cert_der],
        verification_time=_NOW,
    )


def test_freetsa_live_offline_tamper_fails_closed() -> None:
    authority = _make_authority()
    digest = hashlib.sha256(b"freetsa-live-tamper").digest()
    der = authority.sign_timestamp_response(digest, gen_time=_NOW)
    materials = authority.materials()
    provider = FreeTSAProvider(
        transport=RecordedHttpTransport(der),
        trust_roots_der=[materials.root_cert_der],
        ocsp_responses_der=[_OCSP_OK],
    )

    anchor = provider.request_timestamp(TimestampRequest(digest=digest), now=_NOW)
    tampered = bytearray(anchor.tsa_token)
    tampered[-16] ^= 0x01
    parsed = parse_timestamp_response(bytes(tampered))

    with pytest.raises(AnchorVerificationError, match="does not verify"):
        verify_timestamp_token(
            parsed,
            expected_digest=digest,
            trust_roots_der=[materials.root_cert_der],
            verification_time=_NOW,
        )


def test_freetsa_live_offline_ca_error_quarantines() -> None:
    authority = _make_authority()
    digest = hashlib.sha256(b"freetsa-live-quarantine").digest()
    der = authority.sign_timestamp_response(digest, gen_time=_NOW)
    wrong_root = TestTSAAuthority(now=_NOW, common_name="Different TSA").materials()
    provider = FreeTSAProvider(
        transport=RecordedHttpTransport(der),
        trust_roots_der=[wrong_root.root_cert_der],
        ocsp_responses_der=[_OCSP_OK],
    )

    with pytest.raises(AnchorQuarantineError, match="signature does not verify"):
        provider.request_timestamp(TimestampRequest(digest=digest), now=_NOW)
