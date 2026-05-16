# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""``AttestSubstrate`` — append-only audit-event container.

This is a thin wrapper around the pure ``hashchain`` functions plus a process-
local ``threading.Lock``. The container is intentionally minimal so that the
chain semantics remain testable against the pure functions alone; future
multi-writer backends (M6) replace this class without touching ``hashchain``.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from datetime import UTC, datetime

from attestplane.hashchain import (
    VerificationResult,
    chain_extend,
    genesis_head,
    head_of,
    verify_chain,
)
from attestplane.types import ChainedEvent, ChainHead, EventDraft


class AttestSubstrate:
    """In-memory append-only audit log with hash-chain integrity.

    Threading: ``append``, ``tip``, ``verify``, ``__len__``, and ``__iter__``
    are safe to call concurrently from multiple threads of the same process.
    Iteration takes a snapshot at call time and is not affected by appends
    that happen after iteration begins.

    Process boundaries: this container holds no durable storage. Crash or
    process exit loses the chain. Persistent backends are a separate ADR
    (anticipated ADR-0004).
    """

    __slots__ = ("_events", "_lock", "_tip")

    def __init__(self) -> None:
        self._events: list[ChainedEvent] = []
        self._lock = threading.Lock()
        self._tip: ChainHead = genesis_head()

    def append(
        self,
        draft: EventDraft,
        *,
        now: datetime | None = None,
    ) -> ChainedEvent:
        """Append a new event to the chain.

        The substrate assigns ``event_id`` (UUIDv7), ``timestamp``,
        ``seq``, ``prev_hash``, and ``event_hash``. Callers cannot influence
        chain fields; this is intentional, as it is the property an external
        auditor needs to argue that the chain has not been forged.

        ``now`` defaults to ``datetime.now(timezone.utc)``. An explicit value
        is accepted to make tests deterministic and to allow callers to inject
        a vetted clock source.
        """
        actual_now = now if now is not None else datetime.now(UTC)
        with self._lock:
            chained = chain_extend(self._tip, draft, now=actual_now)
            self._events.append(chained)
            self._tip = ChainHead(seq=chained.seq, event_hash=chained.event_hash)
            return chained

    def tip(self) -> ChainHead:
        """Return the current chain head atomically."""
        with self._lock:
            return self._tip

    def verify(self) -> VerificationResult:
        """Re-walk the chain and return the first inconsistency, if any."""
        with self._lock:
            snapshot = list(self._events)
        return verify_chain(snapshot)

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)

    def __iter__(self) -> Iterator[ChainedEvent]:
        with self._lock:
            snapshot = list(self._events)
        return iter(snapshot)

    def __repr__(self) -> str:
        return f"AttestSubstrate(len={len(self)}, tip_seq={self._tip.seq})"

    def snapshot(self) -> list[ChainedEvent]:
        """Return a shallow copy of the chain for offline inspection."""
        with self._lock:
            return list(self._events)

    def head_seq(self) -> int:
        """Return the seq of the current head (``-1`` for an empty chain)."""
        with self._lock:
            return self._tip.seq

    @classmethod
    def from_events(cls, events: list[ChainedEvent]) -> AttestSubstrate:
        """Reconstruct a substrate from a verified chain.

        Raises ``ValueError`` if the events do not form a valid chain. Use
        this to rehydrate from a durable store, conformance-test fixture, or
        wire-protocol transfer.
        """
        result = verify_chain(events)
        if not result.ok:
            raise ValueError(f"cannot rehydrate substrate: {result.reason}")
        instance = cls()
        instance._events = list(events)
        instance._tip = head_of(events)
        return instance
