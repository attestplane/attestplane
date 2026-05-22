# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Pure-function hash-chain primitives.

This module is intentionally I/O-free and stateless. All state lives in the
caller (``AttestSubstrate`` or a future multi-writer backend). Every function
here is referentially transparent, which makes the substrate semantics
auditable independently of any particular storage implementation.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from attestplane.canonical import canonicalize
from attestplane.types import AuditEvent, ChainedEvent, ChainHead, EventDraft

SCHEMA_VERSION: Final[int] = 1
"""Canonicalization schema version for v0.0.1. Frozen by conformance vectors."""

GENESIS_HASH: Final[bytes] = b"\x00" * 32
"""``prev_hash`` value for the first event in any chain."""


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Outcome of walking and re-hashing a chain.

    ``first_bad_index`` is the seq of the first event that failed validation,
    or ``None`` if the chain is consistent. ``reason`` describes the failure
    in human-readable form.
    """

    ok: bool
    first_bad_index: int | None
    reason: str | None


def genesis_head() -> ChainHead:
    """Return the head used before any event has been appended."""
    return ChainHead(seq=-1, event_hash=GENESIS_HASH)


def hash_event(event: AuditEvent) -> bytes:
    """Compute the SHA-256 digest of an ``AuditEvent``'s canonical encoding."""
    return hashlib.sha256(canonicalize(event)).digest()


def chain_extend(
    tip: ChainHead,
    draft: EventDraft,
    *,
    now: datetime,
    event_id: str | None = None,
) -> ChainedEvent:
    """Extend the chain by one event.

    Pure function: given the same tip, draft, and clock, this produces a
    deterministic ``ChainedEvent`` (assuming ``event_id`` is provided). If
    ``event_id`` is ``None``, a UUIDv7 is generated from ``now``, which
    introduces non-determinism through the random component but preserves the
    time ordering needed for index locality.

    The substrate enforces append-order; this function does not verify that
    ``tip`` is the actual current tip — that responsibility lives in the
    container (``AttestSubstrate.append`` or its multi-writer successor).
    """
    if now.tzinfo is None or now.utcoffset() != UTC.utcoffset(None):
        raise ValueError("chain_extend requires a UTC-aware datetime for 'now'")

    if event_id is not None:
        resolved_event_id = event_id
    else:
        import uuid_utils

        resolved_event_id = str(uuid_utils.uuid7())
    event = AuditEvent(
        schema_version=SCHEMA_VERSION,
        event_id=resolved_event_id,
        timestamp=now,
        event_type=draft.event_type,
        actor=draft.actor,
        payload=draft.payload,
        subject_ref=draft.subject_ref,
        session_id=draft.session_id,
        reference_db_ref=draft.reference_db_ref,
        matched_input_ref=draft.matched_input_ref,
        human_verifier=draft.human_verifier,
    )
    event_hash = hash_event(event)
    return ChainedEvent(
        seq=tip.seq + 1,
        prev_hash=tip.event_hash,
        event_hash=event_hash,
        event=event,
    )


def verify_chain(events: list[ChainedEvent]) -> VerificationResult:
    """Walk a chain in order, re-hashing each event and checking linkage.

    Returns ``ok=True`` for an empty chain (a substrate with no appended
    events). Returns the seq of the first event that fails validation
    otherwise.
    """
    expected_tip = genesis_head()
    for index, item in enumerate(events):
        if item.seq != index:
            return VerificationResult(
                ok=False,
                first_bad_index=index,
                reason=f"seq mismatch at index {index}: got {item.seq}, expected {index}",
            )
        if item.prev_hash != expected_tip.event_hash:
            return VerificationResult(
                ok=False,
                first_bad_index=index,
                reason=f"prev_hash mismatch at seq {index}",
            )
        recomputed = hash_event(item.event)
        if recomputed != item.event_hash:
            return VerificationResult(
                ok=False,
                first_bad_index=index,
                reason=f"event_hash mismatch at seq {index}",
            )
        expected_tip = ChainHead(seq=item.seq, event_hash=item.event_hash)
    return VerificationResult(ok=True, first_bad_index=None, reason=None)


def head_of(events: list[ChainedEvent]) -> ChainHead:
    """Return the current head of a chain (``genesis_head()`` when empty)."""
    if not events:
        return genesis_head()
    last = events[-1]
    return ChainHead(seq=last.seq, event_hash=last.event_hash)


__all__ = [
    "GENESIS_HASH",
    "SCHEMA_VERSION",
    "VerificationResult",
    "chain_extend",
    "genesis_head",
    "hash_event",
    "head_of",
    "verify_chain",
]
