# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Signer worker — T3 of the ADR-0005 plan per the
:doc:`T3+T4 architect review </architecture/adr_0005_t3_t4_review_20260517>`.

Two operating modes (architect review § 1 decision 3, hybrid C):

- **Synchronous**: caller invokes :meth:`Signer.sign_event` or
  :meth:`Signer.sign_segment_head` directly; immediate return.
- **Background worker**: caller invokes :meth:`Signer.start` to spawn a
  daemon thread that periodically pulls a fresh substrate snapshot
  via the configured callback, signs new segment heads, and stores
  results in an in-memory buffer (mirrors
  :class:`~attestplane.anchoring.Anchorer`).

**Decoupled from AttestSubstrate** (review § 1 decision 4). The Signer
never appears in ``substrate.append()`` call stacks. ADR-0003 § 4
"anchoring is never on the append() critical path" extends to signing.

**Canonical-JSON byte construction** (review § 1 decision 1+2):

- Segment-head payload: 5 explicit keys
  ``{"chain_id", "event_hash", "schema_version", "seq",
  "signature_schema_version"}`` canonicalised through the shared
  :mod:`attestplane.canonical` primitive.
- Per-event payload: ``canonicalize(audit_event)`` — byte-identical to
  what ``hash_event()`` produces. Zero new cross-language risk;
  ``vectors.json`` already locks this byte sequence.
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,  # noqa: F401  (conditional import — try/except guard)
    )
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "attestplane.signing.signer requires the 'signing' extras. "
        "Install with: pip install attestplane[signing]"
    ) from exc

from attestplane.canonical import canonicalize
from attestplane.hashchain import SCHEMA_VERSION as CHAIN_SCHEMA_VERSION
from attestplane.signing.base import (
    SIGNATURE_SCHEMA_VERSION,
    KeyProvider,
    SignatureMode,
    SignaturePolicy,
    SignatureRecord,
    SigningError,
    SigningMaterial,
)
from attestplane.signing.providers import MultiSignerProvider
from attestplane.types import AuditEvent, ChainedEvent, ChainHead

_FIVE_KEY_PAYLOAD: Final[tuple[str, ...]] = (
    "chain_id",
    "event_hash",
    "schema_version",
    "seq",
    "signature_schema_version",
)


def _build_segment_head_payload(chain_id: str, head: ChainHead) -> bytes:
    """Construct the exact canonical-JSON bytes signed in segment-head mode.

    Locked recipe from
    :doc:`/architecture/adr_0005_t3_t4_review_20260517` § 3:

    .. code-block:: text

        {
          "chain_id": "<str>",
          "event_hash": "<lowercase hex>",
          "schema_version": 1,
          "seq": <int>,
          "signature_schema_version": 1
        }

    Cross-language byte stability gate: TypeScript implementation must
    produce identical bytes for identical input.
    """
    if not chain_id:
        raise SigningError("segment-head signing requires non-empty chain_id")
    payload = {
        "chain_id": chain_id,
        "event_hash": head.event_hash.hex(),
        "schema_version": CHAIN_SCHEMA_VERSION,
        "seq": head.seq,
        "signature_schema_version": SIGNATURE_SCHEMA_VERSION,
    }
    # Defensive: canonicalize() output's key order is alphabetical, but
    # explicitly enumerating the 5 keys above documents the contract.
    assert set(payload) == set(_FIVE_KEY_PAYLOAD), (
        "segment-head payload key set must be exactly the five-key tuple"
    )
    return canonicalize(payload)


def _build_per_event_payload(event: AuditEvent) -> bytes:
    """Per-event mode signs the canonical bytes of the AuditEvent.

    Identical to ``hashchain.hash_event``'s canonicalize() call → already
    cross-language byte stable via ``vectors.json``.
    """
    return canonicalize(event)


@dataclass(frozen=True, slots=True)
class SignerResult:
    """One completed signing operation: ≥ 1 records for one signed seq."""

    pending_seq: int
    records: tuple[SignatureRecord, ...]
    mode: SignatureMode


@dataclass
class SignerStats:
    """Counters for observability + tests."""

    signed_events: int = 0
    signed_segment_heads: int = 0
    provider_errors: int = 0


@dataclass
class _PendingSignature:
    """One queue entry awaiting Signer worker processing."""

    head: ChainHead
    mode: SignatureMode
    audit_event: AuditEvent | None = None
    """Set for per_event mode; None for segment_head mode."""


def _make_signature_record(
    mat: SigningMaterial,
    *,
    signed_seq: int,
    signed_event_hash: bytes,
    signed_payload: bytes,
    signature_mode: SignatureMode,
    signed_at: datetime,
) -> SignatureRecord:
    sig = mat.private_key.sign(signed_payload)
    return SignatureRecord(
        signature_schema_version=SIGNATURE_SCHEMA_VERSION,
        signed_seq=signed_seq,
        signed_event_hash=signed_event_hash,
        signature=sig,
        key_id=mat.key_id,
        public_key_der=mat.public_key_der,
        signing_cert_chain=mat.signing_cert_chain,
        signed_at=signed_at,
        signature_mode=signature_mode,
        signed_payload=signed_payload,
    )


def _resolve_materials(
    provider: KeyProvider | MultiSignerProvider,
) -> list[SigningMaterial]:
    """Return a list of signing materials, one per provider in plurality mode."""
    if isinstance(provider, MultiSignerProvider):
        return provider.get_signing_materials()
    return [provider.get_signing_material()]


class Signer:
    """Event-signing producer.

    :param chain_id: substrate-instance identifier embedded in
        segment-head signed payloads. Must be non-empty (segment-head
        mode would otherwise fail at payload construction).
    :param key_provider: a :class:`~attestplane.signing.KeyProvider` or
        :class:`~attestplane.signing.MultiSignerProvider` (plurality
        any-of-n).
    :param policy: when the background worker fires. Defaults to the
        :class:`~attestplane.signing.SignaturePolicy` defaults.
    :param snapshot: callable returning the substrate's current chain.
        Required for background-worker operation; optional for
        synchronous-only callers.
    :param now: clock injection for deterministic tests.
    """

    def __init__(
        self,
        *,
        chain_id: str,
        key_provider: KeyProvider | MultiSignerProvider,
        policy: SignaturePolicy | None = None,
        snapshot: Callable[[], list[ChainedEvent]] | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not chain_id:
            raise ValueError("Signer chain_id must be non-empty")
        self._chain_id = chain_id
        self._key_provider = key_provider
        self._policy = policy or SignaturePolicy()
        self._snapshot = snapshot
        self._now = now

        # Background-worker state.
        self._queue: deque[_PendingSignature] = deque()
        self._results: list[SignerResult] = []
        self._stats = SignerStats()
        self._lock = threading.Lock()
        self._wakeup = threading.Event()
        self._shutdown = threading.Event()
        self._thread: threading.Thread | None = None
        # Track the last-signed segment-head seq so background worker
        # can detect new segments without re-signing duplicates.
        self._last_signed_segment_head_seq: int = -1

    # ----- Synchronous API ---------------------------------------------

    def sign_event(self, event: ChainedEvent) -> list[SignatureRecord]:
        """Sign one event in per-event mode."""
        materials = _resolve_materials(self._key_provider)
        signed_at = self._now()
        if signed_at.tzinfo is None:
            raise SigningError("Signer.sign_event requires UTC-aware now()")
        payload = _build_per_event_payload(event.event)
        records = [
            _make_signature_record(
                mat,
                signed_seq=event.seq,
                signed_event_hash=event.event_hash,
                signed_payload=payload,
                signature_mode="per_event",
                signed_at=signed_at,
            )
            for mat in materials
        ]
        with self._lock:
            self._stats.signed_events += 1
        return records

    def sign_segment_head(self, head: ChainHead) -> list[SignatureRecord]:
        """Sign one chain head in segment-head mode."""
        if head.seq < 0:
            raise SigningError(
                "Signer.sign_segment_head requires a real chain head "
                "(seq >= 0); refusing to sign genesis sentinel"
            )
        materials = _resolve_materials(self._key_provider)
        signed_at = self._now()
        if signed_at.tzinfo is None:
            raise SigningError("Signer.sign_segment_head requires UTC-aware now()")
        payload = _build_segment_head_payload(self._chain_id, head)
        records = [
            _make_signature_record(
                mat,
                signed_seq=head.seq,
                signed_event_hash=head.event_hash,
                signed_payload=payload,
                signature_mode="segment_head",
                signed_at=signed_at,
            )
            for mat in materials
        ]
        with self._lock:
            self._stats.signed_segment_heads += 1
        return records

    # ----- Background worker --------------------------------------------

    def enqueue_segment_head(self, head: ChainHead) -> None:
        """Add a segment head to the worker queue."""
        if head.seq < 0:
            raise SigningError(
                "enqueue_segment_head requires a real chain head (seq >= 0)"
            )
        with self._lock:
            self._queue.append(_PendingSignature(head=head, mode="segment_head"))
        self._wakeup.set()

    def enqueue_event(self, event: ChainedEvent) -> None:
        """Add a single event to the worker queue for per-event signing."""
        with self._lock:
            self._queue.append(_PendingSignature(
                head=ChainHead(seq=event.seq, event_hash=event.event_hash),
                mode="per_event",
                audit_event=event.event,
            ))
        self._wakeup.set()

    def step_once(self) -> SignerResult | None:
        """Process one queue item synchronously (testing entry).

        Returns the produced result, or ``None`` if the queue is empty.
        """
        with self._lock:
            if not self._queue:
                return None
            pending = self._queue.popleft()

        try:
            if pending.mode == "segment_head":
                records = self.sign_segment_head(pending.head)
            else:
                assert pending.audit_event is not None
                chained = ChainedEvent(
                    seq=pending.head.seq,
                    prev_hash=b"\x00" * 32,  # ignored for per-event payload
                    event_hash=pending.head.event_hash,
                    event=pending.audit_event,
                )
                records = self.sign_event(chained)
        except Exception as exc:
            with self._lock:
                self._stats.provider_errors += 1
            raise SigningError(
                f"Signer.step_once failed on seq={pending.head.seq} "
                f"mode={pending.mode}: {exc}"
            ) from exc

        result = SignerResult(
            pending_seq=pending.head.seq,
            records=tuple(records),
            mode=pending.mode,
        )
        with self._lock:
            self._results.append(result)
            if pending.mode == "segment_head":
                self._last_signed_segment_head_seq = max(
                    self._last_signed_segment_head_seq, pending.head.seq,
                )
        return result

    def pull_segment_heads_from_snapshot(self) -> int:
        """Walk the snapshot for new segment heads to enqueue.

        Returns the number of newly-enqueued heads. Triggered by the
        background worker on each wake cycle; never invoked from the
        synchronous API path.
        """
        if self._snapshot is None:
            return 0
        chain = self._snapshot()
        if not chain:
            return 0
        # Find heads at every batch_size-th seq, plus the tail.
        batch_size = self._policy.batch_size
        head_seq = chain[-1].seq
        with self._lock:
            last_signed = self._last_signed_segment_head_seq
        candidate_seqs = []
        # Emit a segment head at every batch_size boundary AFTER
        # last_signed. Always include the final tail.
        first_candidate = last_signed + 1
        for s in range(first_candidate, head_seq + 1):
            if (s + 1) % batch_size == 0 or s == head_seq:
                candidate_seqs.append(s)
        enqueued = 0
        for seq in candidate_seqs:
            head = ChainHead(seq=chain[seq].seq, event_hash=chain[seq].event_hash)
            self.enqueue_segment_head(head)
            enqueued += 1
        return enqueued

    def start(self) -> None:
        """Spawn the daemon worker thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._shutdown.clear()
        thread = threading.Thread(
            target=self._run, daemon=True, name="attestplane-signer",
        )
        thread.start()
        self._thread = thread

    def stop(self, timeout: float | None = 5.0) -> None:
        """Signal shutdown and wait for the worker thread."""
        self._shutdown.set()
        self._wakeup.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _run(self) -> None:
        while not self._shutdown.is_set():
            self._wakeup.wait(timeout=1.0)
            self._wakeup.clear()
            # Pull from snapshot, enqueue new segment heads.
            try:
                self.pull_segment_heads_from_snapshot()
            except Exception:
                with self._lock:
                    self._stats.provider_errors += 1
            while not self._shutdown.is_set():
                try:
                    if self.step_once() is None:
                        break
                except SigningError:
                    # Already counted in step_once via provider_errors.
                    break

    # ----- Observability ------------------------------------------------

    def stats(self) -> SignerStats:
        """Atomic snapshot of the worker's counters."""
        with self._lock:
            return SignerStats(
                signed_events=self._stats.signed_events,
                signed_segment_heads=self._stats.signed_segment_heads,
                provider_errors=self._stats.provider_errors,
            )

    def drained_results(self) -> list[SignerResult]:
        """Atomically remove and return all completed results."""
        with self._lock:
            out = list(self._results)
            self._results.clear()
            return out

    def pending_count(self) -> int:
        """Number of items still in the worker queue."""
        with self._lock:
            return len(self._queue)


__all__ = [
    "Signer",
    "SignerResult",
    "SignerStats",
]
