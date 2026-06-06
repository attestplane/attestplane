# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from attestplane.anchoring import (
    MockTSAProvider,
    LIVE_ANCHOR_QUARANTINE_EXIT_CODE,
    TSAUnavailableError,
    TimestampRequest,
)
from attestplane.anchoring.testing import TestTSAAuthority, TestTSAProvider
from attestplane.anchoring.verifier import verify_live_anchor_with_provider
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.types import EventDraft
from attestplane.verify_reason_codes import (
    VERIFY_REASON_ANCHOR_INVALID,
    VERIFY_REASON_ANCHOR_QUARANTINED,
)


def _one_event_chain() -> list:
    now = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    event = chain_extend(
        genesis_head(),
        EventDraft(event_type="eval_event", actor="agent://quarantine-test"),
        now=now,
        event_id="00000000-0000-7000-8000-000000000001",
    )
    return [event]


class _UnavailableProvider(MockTSAProvider):
    def request_timestamp(self, request: TimestampRequest, **kwargs: object):  # type: ignore[override]
        raise TSAUnavailableError("simulated timeout")


class _FixedAnchorProvider(MockTSAProvider):
    def __init__(self, record: Any) -> None:
        super().__init__(provider_id=record.tsa_provider_id)
        self._record = record

    def request_timestamp(self, request: TimestampRequest, **kwargs: object):  # type: ignore[override]
        return self._record


def test_unreachable_tsa_routes_to_quarantine() -> None:
    result = verify_live_anchor_with_provider(_one_event_chain()[0], _UnavailableProvider())

    assert result.status == "quarantined"
    assert result.exit_code == LIVE_ANCHOR_QUARANTINE_EXIT_CODE
    assert result.reason_code == VERIFY_REASON_ANCHOR_QUARANTINED
    assert result.claim_verified is False
    assert result.anchor_record is None
    assert result.verification_result is None


def test_tampered_timestamp_token_remains_hard_failure() -> None:
    pytest.importorskip("asn1crypto")
    pytest.importorskip("cryptography")

    from attestplane.anchoring.testing import TestTSAAuthority, TestTSAProvider

    chain = _one_event_chain()
    authority = TestTSAAuthority(now=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC))
    provider = TestTSAProvider(authority)
    anchor = provider.request_timestamp(
        TimestampRequest(digest=chain[0].event_hash),
        anchored_seq=0,
        now=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC),
    )
    token = bytearray(anchor.tsa_token)
    token[-1] ^= 0x01
    tampered_anchor = replace(anchor, tsa_token=bytes(token))
    tampered = _FixedAnchorProvider(tampered_anchor)

    result = verify_live_anchor_with_provider(
        chain[0],
        tampered,
        trust_roots_der=[authority.materials().root_cert_der],
        verification_time=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC),
    )

    assert result.status == "failed"
    assert result.exit_code == 1
    assert result.reason_code == VERIFY_REASON_ANCHOR_INVALID
    assert result.claim_verified is False
    assert result.verification_result is not None
    assert result.verification_result.ok is False


def test_expired_timestamp_token_remains_hard_failure() -> None:
    pytest.importorskip("asn1crypto")
    pytest.importorskip("cryptography")

    from attestplane.anchoring.testing import TestTSAAuthority, TestTSAProvider

    chain = _one_event_chain()
    issuance_time = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    authority = TestTSAAuthority(now=issuance_time, cert_validity_days=1)
    provider = TestTSAProvider(authority)
    anchor = provider.request_timestamp(
        TimestampRequest(digest=chain[0].event_hash),
        anchored_seq=0,
        now=issuance_time,
    )
    future = issuance_time + timedelta(days=30)
    result = verify_live_anchor_with_provider(
        chain[0],
        _FixedAnchorProvider(anchor),
        trust_roots_der=[authority.materials().root_cert_der],
        verification_time=future,
    )

    assert result.status == "failed"
    assert result.exit_code == 1
    assert result.reason_code == VERIFY_REASON_ANCHOR_INVALID
    assert result.claim_verified is False
    assert result.verification_result is not None
    assert result.verification_result.ok is False
