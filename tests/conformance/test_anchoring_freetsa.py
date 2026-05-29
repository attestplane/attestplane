# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for the live FreeTSA quarantine path.

This pins the 2026-05-27 nightly-anchor failure mode as a deterministic
offline fixture: a live TSA provider id that cannot be claim-safely
confirmed must quarantine the bundle instead of asserting a verified
anchor.
"""

from __future__ import annotations

from datetime import UTC, datetime

from attestplane.anchoring import (
    MockTSAProvider,
    TimestampRequest,
    verify_chain_with_anchors,
)
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.types import ChainHead, EventDraft

_FIXTURE = {
    "name": "2026-05-27_freeTSA_live_anchor_quarantine",
    "provider_id": "freetsa.org",
    "issued_at": datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC),
    "expected_status": "quarantined",
}


def _build_chain(n: int) -> list:
    chain = []
    head = genesis_head()
    issued_at = _FIXTURE["issued_at"]
    for i in range(n):
        draft = EventDraft(
            event_type="eval_event",
            actor=f"agent://test/{i}",
            payload={"i": i},
        )
        ev = chain_extend(
            head,
            draft,
            now=issued_at,
            event_id=f"00000000-0000-7000-8000-{i:012d}",
        )
        chain.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    return chain


def test_recorded_freetsa_live_anchor_without_trust_roots_quarantines() -> None:
    chain = _build_chain(1)
    provider = MockTSAProvider(
        provider_id=_FIXTURE["provider_id"],
        fixed_time=_FIXTURE["issued_at"],
    )
    anchor = provider.request_timestamp(
        TimestampRequest(digest=chain[0].event_hash),
        anchored_seq=0,
    )

    result = verify_chain_with_anchors(chain, [anchor])

    assert result.ok is False
    assert result.verification_status == _FIXTURE["expected_status"]
    assert result.anchored_seqs == frozenset()
    assert result.unanchored_seqs == frozenset({0})
    assert result.anchor_results[0].valid is True
    assert result.anchor_results[0].cert_status == "VALID_UNVERIFIED"


def test_non_live_provider_without_trust_roots_stays_claim_neutral() -> None:
    chain = _build_chain(1)
    provider = MockTSAProvider(
        provider_id="mock.tsa.local", fixed_time=_FIXTURE["issued_at"]
    )
    anchor = provider.request_timestamp(
        TimestampRequest(digest=chain[0].event_hash),
        anchored_seq=0,
    )

    result = verify_chain_with_anchors(chain, [anchor])

    assert result.ok is True
    assert result.verification_status == "verified"
    assert result.anchored_seqs == frozenset({0})
    assert result.unanchored_seqs == frozenset()
