# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Anchor quarantine regression coverage.

This file pins the claim-safe verifier boundary for anchors that cannot be
cryptographically verified because trust roots are unavailable.
"""

from __future__ import annotations

from datetime import UTC, datetime

from attestplane.anchoring import TimestampRequest, verify_chain_with_anchors
from attestplane.anchoring.testing import TestTSAAuthority, TestTSAProvider
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.types import ChainHead, EventDraft

NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _build_chain(n: int) -> list:
    chain = []
    head = genesis_head()
    for i in range(n):
        draft = EventDraft(
            event_type="eval_event",
            actor=f"agent://test/{i}",
            payload={"i": i},
        )
        ev = chain_extend(head, draft, now=NOW, event_id=f"00000000-0000-7000-8000-{i:012d}")
        chain.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    return chain


def test_anchor_quarantine_without_trust_roots_stays_unverifiable() -> None:
    chain = _build_chain(1)
    authority = TestTSAAuthority(now=NOW)
    provider = TestTSAProvider(authority)
    anchor = provider.request_timestamp(
        TimestampRequest(digest=chain[0].event_hash),
        anchored_seq=0,
        now=NOW,
    )

    result = verify_chain_with_anchors(chain, [anchor])

    assert result.ok is False
    assert result.verification_status == "not_performed"
    assert result.reason_code == "anchor.unverifiable"
    assert result.anchor_results[0].valid is False
    assert result.anchor_results[0].reason_code == "anchor.unverifiable"
    assert result.anchor_results[0].cert_status == "VALID_UNVERIFIED"
