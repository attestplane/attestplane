# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Anchorer background worker per ADR-0003 § 4.

The :class:`Anchorer` consumes a durable per-substrate queue of pending
chain heads, fires :class:`TimestampRequest` calls at the configured
:class:`TSAProvider`, and stores the resulting :class:`AnchorRecord`
instances in an in-memory store. ``substrate.append()`` is **never**
blocked on the worker; the queue is the boundary.

This module ships the in-process reference worker. Multi-writer /
durable-queue backends are M6+ deliverables and depend on the
storage-backend ADR.

Threading model
---------------

The worker runs on a dedicated daemon thread. The main thread (running
``substrate.append``) writes pending entries via :meth:`Anchorer.enqueue`;
the worker thread reads and processes. A :class:`threading.Event`
signals shutdown.

Retry policy (ADR-0003 § 4 failure-mode table)
----------------------------------------------

- :class:`TSAUnavailableError` → exponential backoff
  (1 s, 2 s, 4 s, 8 s, 16 s, capped at :attr:`max_backoff_seconds`).
  Re-queue at tail unless the provider opts into claim-safe
  quarantine on unavailability.
- :class:`AnchorVerificationError` → quarantine. Item moves to
  ``quarantined`` state and is not retried automatically.
- Successful anchor → store result, transition to ``anchored``.

Clock-skew tracking
-------------------

When the TSA's claimed ``issued_at_claimed`` deviates from the local
clock by more than :attr:`clock_skew_warn_seconds`, the worker records a
clock-skew warning. The TSA's time is treated as authoritative
(ADR-0003 § 4); the warning is informational.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from attestplane.anchoring.base import (
    AnchorPolicy,
    AnchorRecord,
    AnchorStatus,
    AnchorVerificationError,
    TimestampRequest,
    TSAProvider,
    TSAUnavailableError,
)


@dataclass
class PendingAnchor:
    """One entry in the anchorer's work queue."""

    digest: bytes
    seq: int
    enqueued_at: datetime
    attempts: int = 0
    next_attempt_at: datetime | None = None
    last_error: str | None = None
    status: AnchorStatus = "pending"


@dataclass
class WorkerStats:
    """Lightweight counters; useful for observability and tests."""

    enqueued: int = 0
    anchored: int = 0
    quarantined: int = 0
    retries_after_unavailable: int = 0
    clock_skew_warnings: int = 0


@dataclass
class AnchorerResult:
    """Per-completed-anchor record + provenance metadata."""

    pending: PendingAnchor
    record: AnchorRecord | None
    clock_skew_seconds: float


class Anchorer:
    """In-process anchorer worker.

    :param provider: the :class:`TSAProvider` to call. For plurality,
        wrap a :class:`MultiTSAProvider` and the worker stores all
        records it returns.
    :param policy: trigger policy (currently advisory; the worker
        anchors one digest per :meth:`enqueue` call regardless of
        ``batch_size`` / ``max_idle_seconds`` in v1).
    :param max_backoff_seconds: cap for exponential backoff on
        :class:`TSAUnavailableError`.
    :param clock_skew_warn_seconds: emit a clock-skew warning when
        ``|local - tsa_claimed_time| > this``.
    :param now: callable returning the current UTC datetime. Injected
        for deterministic tests.
    :param sleep: callable that pauses execution. Injected for tests
        to avoid real waiting in retry paths.
    """

    def __init__(
        self,
        provider: TSAProvider,
        *,
        policy: AnchorPolicy | None = None,
        max_backoff_seconds: int = 16,
        clock_skew_warn_seconds: int = 60,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._provider = provider
        self._policy = policy or AnchorPolicy()
        self._max_backoff = max_backoff_seconds
        self._clock_skew_warn = clock_skew_warn_seconds
        self._now = now
        self._sleep = sleep
        self._queue: deque[PendingAnchor] = deque()
        self._results: list[AnchorerResult] = []
        self._lock = threading.Lock()
        self._wakeup = threading.Event()
        self._shutdown = threading.Event()
        self._thread: threading.Thread | None = None
        self._stats = WorkerStats()

    # ----- Public API -----

    def enqueue(self, digest: bytes, seq: int) -> None:
        """Add a chain head to the anchor queue. Non-blocking."""
        if len(digest) != 32:
            raise ValueError("Anchorer.enqueue requires a 32-byte SHA-256 digest")
        if seq < 0:
            raise ValueError("Anchorer.enqueue requires seq >= 0")
        pending = PendingAnchor(digest=digest, seq=seq, enqueued_at=self._now())
        with self._lock:
            self._queue.append(pending)
            self._stats.enqueued += 1
        self._wakeup.set()

    def start(self) -> None:
        """Spawn the worker thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._shutdown.clear()
        thread = threading.Thread(target=self._run, daemon=True, name="attestplane-anchorer")
        thread.start()
        self._thread = thread

    def stop(self, timeout: float | None = 5.0) -> None:
        """Signal shutdown and wait for the worker thread to exit."""
        self._shutdown.set()
        self._wakeup.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def stats(self) -> WorkerStats:
        """Return a snapshot of the worker's counters."""
        with self._lock:
            return WorkerStats(
                enqueued=self._stats.enqueued,
                anchored=self._stats.anchored,
                quarantined=self._stats.quarantined,
                retries_after_unavailable=self._stats.retries_after_unavailable,
                clock_skew_warnings=self._stats.clock_skew_warnings,
            )

    def drained_results(self) -> list[AnchorerResult]:
        """Atomically remove and return all completed results so far."""
        with self._lock:
            out = list(self._results)
            self._results.clear()
            return out

    def pending_count(self) -> int:
        with self._lock:
            return len(self._queue)

    # ----- Synchronous single-step (for tests and small deployments) -----

    def step_once(self) -> AnchorerResult | None:
        """Process one queue item synchronously.

        Returns the resulting :class:`AnchorerResult`, or ``None`` if the
        queue is empty. On :class:`TSAUnavailableError` the item is
        rescheduled (re-queued at tail with bumped backoff) and ``None``
        is returned. On :class:`AnchorVerificationError` the item is
        quarantined and a result with ``record=None`` is returned.

        This method is what unit tests call to exercise the worker
        without spinning a real thread.
        """
        with self._lock:
            if not self._queue:
                return None
            pending = self._queue.popleft()

        now = self._now()
        if pending.next_attempt_at is not None and pending.next_attempt_at > now:
            # Not yet eligible for retry; push back to tail.
            with self._lock:
                self._queue.append(pending)
            return None

        request = TimestampRequest(digest=pending.digest)
        try:
            # The mock provider accepts an anchored_seq kwarg; production
            # providers (live TSAs) ignore it because the seq is bookkeeping
            # state outside the TSA's view. The kwarg is forwarded so the
            # mock can echo the correct seq into AnchorRecord for tests.
            record = self._provider.request_timestamp(
                request,
                anchored_seq=pending.seq,  # type: ignore[call-arg]
            )
        except TSAUnavailableError as exc:
            pending.attempts += 1
            if getattr(self._provider, "quarantine_on_unavailable", False):
                pending.status = "quarantined"
                pending.last_error = f"TSAUnavailableError: {exc}"
                with self._lock:
                    self._stats.quarantined += 1
                    result = AnchorerResult(
                        pending=pending,
                        record=None,
                        clock_skew_seconds=0.0,
                    )
                    self._results.append(result)
                return result
            backoff = min(2 ** (pending.attempts - 1), self._max_backoff)
            pending.next_attempt_at = self._now_plus(backoff)
            pending.last_error = f"TSAUnavailableError: {exc}"
            with self._lock:
                self._queue.append(pending)
                self._stats.retries_after_unavailable += 1
            return None
        except AnchorVerificationError as exc:
            pending.attempts += 1
            pending.status = "quarantined"
            pending.last_error = f"AnchorVerificationError: {exc}"
            with self._lock:
                self._stats.quarantined += 1
                result = AnchorerResult(pending=pending, record=None, clock_skew_seconds=0.0)
                self._results.append(result)
            return result

        # Success path.
        skew = self._clock_skew(record.issued_at_claimed, now)
        if abs(skew) > self._clock_skew_warn:
            with self._lock:
                self._stats.clock_skew_warnings += 1
        pending.status = "anchored"
        pending.attempts += 1
        result = AnchorerResult(pending=pending, record=record, clock_skew_seconds=skew)
        with self._lock:
            self._results.append(result)
            self._stats.anchored += 1
        return result

    # ----- Internals -----

    def _run(self) -> None:
        while not self._shutdown.is_set():
            self._wakeup.wait(timeout=1.0)
            self._wakeup.clear()
            while not self._shutdown.is_set():
                if self.step_once() is None:
                    break

    def _now_plus(self, seconds: float) -> datetime:
        from datetime import timedelta

        return self._now() + timedelta(seconds=seconds)

    @staticmethod
    def _clock_skew(tsa_time: datetime, local_now: datetime) -> float:
        return (tsa_time - local_now).total_seconds()


__all__ = [
    "Anchorer",
    "AnchorerResult",
    "PendingAnchor",
    "WorkerStats",
]
