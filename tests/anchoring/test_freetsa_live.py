# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import urllib.request
from datetime import UTC, datetime

import pytest

pytest.importorskip("asn1crypto")
pytest.importorskip("cryptography")

from cryptography import x509
from cryptography.hazmat.primitives import serialization

from attestplane.anchoring import (
    FreeTSAProvider,
    LIVE_ANCHOR_QUARANTINE_EXIT_CODE,
    TimestampRequest,
    UrllibHttpTransport,
)
from attestplane.anchoring.base import TSAUnavailableError
from attestplane.anchoring.verifier import verify_live_anchor_with_provider
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.types import EventDraft
from attestplane.verify_reason_codes import VERIFY_REASON_ANCHOR_QUARANTINED

LIVE_ROOT_URL = "https://freetsa.org/files/cacert.pem"


def _fetch_freetsa_root_der() -> bytes:
    try:
        with urllib.request.urlopen(LIVE_ROOT_URL, timeout=30) as response:
            pem = response.read()
    except OSError as exc:
        pytest.skip(f"FreeTSA root certificate unavailable: {exc}")
    cert = x509.load_pem_x509_certificate(pem)
    return cert.public_bytes(serialization.Encoding.DER)


def _live_chain() -> list:
    now = datetime.now(UTC).replace(microsecond=0)
    event = chain_extend(
        genesis_head(),
        EventDraft(event_type="eval_event", actor="agent://live-freetsa"),
        now=now,
        event_id="00000000-0000-7000-8000-000000000001",
    )
    return [event]


def test_live_freetsa_request_verifies_or_quarantines() -> None:
    chain = _live_chain()
    root_der = _fetch_freetsa_root_der()
    now = datetime.now(UTC).replace(microsecond=0)

    provider = FreeTSAProvider(
        transport=UrllibHttpTransport(),
        trust_roots_der=[root_der],
    )
    result = verify_live_anchor_with_provider(
        chain[0],
        provider,
        trust_roots_der=[root_der],
        verification_time=now,
        verify_ocsp=False,
    )

    assert result.status in {"verified", "quarantined"}
    if result.status == "quarantined":
        assert result.exit_code == LIVE_ANCHOR_QUARANTINE_EXIT_CODE
        assert result.reason_code == VERIFY_REASON_ANCHOR_QUARANTINED
        assert result.claim_verified is False
        return

    assert result.exit_code == 0
    assert result.reason_code is None
    assert result.claim_verified is True
    assert result.anchor_record is not None
    assert result.verification_result is not None
    assert result.verification_result.ok is True
    assert result.verification_result.anchor_results[0].cert_status == "VALID"
    assert result.verification_result.anchor_results[0].valid is True


class _UnavailableProvider(FreeTSAProvider):
    def request_timestamp(self, request: TimestampRequest, **kwargs):  # type: ignore[override]
        raise TSAUnavailableError("simulated FreeTSA outage")


def test_live_freetsa_quarantine_is_not_a_verified_claim() -> None:
    chain = _live_chain()
    provider = _UnavailableProvider(
        transport=UrllibHttpTransport(),
        trust_roots_der=[],
    )

    result = verify_live_anchor_with_provider(chain[0], provider)

    assert result.status == "quarantined"
    assert result.exit_code == LIVE_ANCHOR_QUARANTINE_EXIT_CODE
    assert result.reason_code == VERIFY_REASON_ANCHOR_QUARANTINED
    assert result.claim_verified is False
    assert result.anchor_record is None
    assert result.verification_result is None
