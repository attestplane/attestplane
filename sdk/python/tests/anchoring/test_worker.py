# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for :mod:`attestplane.anchoring.worker`."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from attestplane.anchoring import (
    Anchorer,
    AnchorPolicy,
    AnchorVerificationError,
    MockTSAProvider,
    TSAUnavailableError,
)


class _FlakyProvider(MockTSAProvider):
    """Wraps MockTSAProvider; raises TSAUnavailableError the first N calls."""

    def __init__(self, fail_first_n: int, *, fixed_time: datetime) -> None:
        super().__init__(provider_id="flaky", fixed_time=fixed_time)
        self._remaining_failures = fail_first_n

    def request_timestamp(self, request: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise TSAUnavailableError("simulated unavailability")
        return super().request_timestamp(request, **kwargs)


class _PoisonProvider(MockTSAProvider):
    """Raises AnchorVerificationError on every call (simulating bad TSA response)."""

    def request_timestamp(self, request: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        raise AnchorVerificationError("simulated malformed token")


# --- Basic flow ---


def test_step_once_returns_none_on_empty_queue() -> None:
    provider = MockTSAProvider(fixed_time=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC))
    anchorer = Anchorer(provider)
    assert anchorer.step_once() is None


def test_enqueue_increments_count() -> None:
    provider = MockTSAProvider(fixed_time=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC))
    anchorer = Anchorer(provider)
    anchorer.enqueue(b"\x00" * 32, seq=0)
    assert anchorer.pending_count() == 1
    assert anchorer.stats().enqueued == 1


def test_enqueue_rejects_bad_digest() -> None:
    anchorer = Anchorer(MockTSAProvider())
    with pytest.raises(ValueError, match="32-byte"):
        anchorer.enqueue(b"\x00" * 16, seq=0)


def test_enqueue_rejects_negative_seq() -> None:
    anchorer = Anchorer(MockTSAProvider())
    with pytest.raises(ValueError, match="seq"):
        anchorer.enqueue(b"\x00" * 32, seq=-1)


def test_step_once_success() -> None:
    fixed = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    provider = MockTSAProvider(fixed_time=fixed)
    anchorer = Anchorer(provider, now=lambda: fixed)

    anchorer.enqueue(b"\x01" * 32, seq=5)
    result = anchorer.step_once()

    assert result is not None
    assert result.record is not None
    assert result.record.anchored_seq == 5
    assert result.pending.status == "anchored"
    assert anchorer.stats().anchored == 1
    assert anchorer.pending_count() == 0


# --- Retry / backoff on TSAUnavailableError ---


def test_unavailable_reschedules_and_eventually_succeeds() -> None:
    fixed = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    clock = [fixed]

    def now() -> datetime:
        return clock[0]

    provider = _FlakyProvider(fail_first_n=2, fixed_time=fixed)
    anchorer = Anchorer(provider, now=now, max_backoff_seconds=8)
    anchorer.enqueue(b"\x02" * 32, seq=0)

    # First call: unavailable, requeued with next_attempt_at = now+1s.
    assert anchorer.step_once() is None
    assert anchorer.pending_count() == 1
    with anchorer._lock:
        pending = anchorer._queue[0]
    assert pending.status == "quarantined"
    assert anchorer.stats().retries_after_unavailable == 1
    assert anchorer.stats().quarantined == 1

    # Without advancing time, the item is not yet eligible for retry.
    assert anchorer.step_once() is None  # rotated back to tail
    assert anchorer.pending_count() == 1

    # Advance time past the backoff (1s) and retry. Still flaky, fails again.
    clock[0] = fixed + timedelta(seconds=2)
    assert anchorer.step_once() is None
    assert anchorer.stats().retries_after_unavailable == 2

    # Advance past the second backoff (2s) and retry. Now succeeds.
    clock[0] = fixed + timedelta(seconds=5)
    result = anchorer.step_once()
    assert result is not None
    assert result.record is not None
    assert anchorer.stats().anchored == 1


def test_backoff_caps_at_max() -> None:
    fixed = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    clock = [fixed]

    def now() -> datetime:
        return clock[0]

    provider = MockTSAProvider(provider_id="p", fail_with=TSAUnavailableError("dead"))
    anchorer = Anchorer(provider, now=now, max_backoff_seconds=4)
    anchorer.enqueue(b"\x03" * 32, seq=0)

    for _ in range(6):
        # Advance well past any plausible backoff each iteration.
        clock[0] += timedelta(seconds=100)
        anchorer.step_once()

    # After enough attempts, backoff has plateaued.
    with anchorer._lock:
        pending = anchorer._queue[0]
    assert pending.attempts >= 6
    next_attempt = pending.next_attempt_at
    assert next_attempt is not None
    # next_attempt was computed from anchorer._now_plus(min(2**(n-1), max_backoff))
    # last delta seen by the test should be at most max_backoff.
    delta = (next_attempt - clock[0]).total_seconds()
    assert 0 <= delta <= 4


# --- Quarantine on AnchorVerificationError ---


def test_verification_error_quarantines_immediately() -> None:
    fixed = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    anchorer = Anchorer(_PoisonProvider(), now=lambda: fixed)

    anchorer.enqueue(b"\x04" * 32, seq=0)
    result = anchorer.step_once()

    assert result is not None
    assert result.record is None
    assert result.pending.status == "failed_permanent"
    assert "malformed token" in (result.pending.last_error or "")
    assert anchorer.stats().failed_permanent == 1
    assert anchorer.stats().quarantined == 0
    # No retry: queue is now empty.
    assert anchorer.pending_count() == 0


# --- Clock skew tracking ---


def test_clock_skew_warning_emitted_when_skew_exceeds_threshold() -> None:
    tsa_time = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    local_time = tsa_time + timedelta(seconds=300)  # 5 minutes ahead

    provider = MockTSAProvider(fixed_time=tsa_time)
    anchorer = Anchorer(provider, now=lambda: local_time, clock_skew_warn_seconds=60)
    anchorer.enqueue(b"\x05" * 32, seq=0)

    result = anchorer.step_once()
    assert result is not None
    assert abs(result.clock_skew_seconds) >= 60
    assert anchorer.stats().clock_skew_warnings == 1


def test_clock_skew_below_threshold_no_warning() -> None:
    tsa_time = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    local_time = tsa_time + timedelta(seconds=10)

    provider = MockTSAProvider(fixed_time=tsa_time)
    anchorer = Anchorer(provider, now=lambda: local_time, clock_skew_warn_seconds=60)
    anchorer.enqueue(b"\x06" * 32, seq=0)

    anchorer.step_once()
    assert anchorer.stats().clock_skew_warnings == 0


# --- Drained results ---


def test_drained_results_is_destructive() -> None:
    fixed = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    provider = MockTSAProvider(fixed_time=fixed)
    anchorer = Anchorer(provider, now=lambda: fixed)
    for i in range(3):
        anchorer.enqueue(bytes([i]) * 32, seq=i)
        anchorer.step_once()

    first = anchorer.drained_results()
    assert len(first) == 3

    second = anchorer.drained_results()
    assert second == []


# --- Threaded operation (smoke) ---


def test_start_and_stop_processes_queued_items() -> None:
    fixed = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    provider = MockTSAProvider(fixed_time=fixed)
    anchorer = Anchorer(provider, now=lambda: fixed, sleep=lambda _: None)

    anchorer.start()
    for i in range(5):
        anchorer.enqueue(bytes([i + 1]) * 32, seq=i)

    # Wait briefly for the worker thread to drain the queue.
    done = threading.Event()
    deadline = threading.Timer(2.0, done.set)
    deadline.start()
    while not done.is_set() and anchorer.pending_count() > 0:
        pass
    deadline.cancel()

    anchorer.stop(timeout=2.0)

    assert anchorer.stats().anchored == 5


def test_start_is_idempotent() -> None:
    anchorer = Anchorer(MockTSAProvider())
    anchorer.start()
    anchorer.start()  # second call is a no-op
    anchorer.stop()


def test_stop_without_start_is_safe() -> None:
    anchorer = Anchorer(MockTSAProvider())
    anchorer.stop()  # no thread to join; must not raise


# --- AnchorPolicy passthrough ---


def test_custom_policy_accepted() -> None:
    anchorer = Anchorer(MockTSAProvider(), policy=AnchorPolicy(batch_size=128, max_idle_seconds=120))
    assert anchorer._policy.batch_size == 128
