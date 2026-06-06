# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coverage-gap tests for attestplane.signing.signer.

Targets missing lines: 229, 255, 277, 316-319, 346, 394-396, 401-403.
"""

from __future__ import annotations

import time
from datetime import datetime
from unittest.mock import MagicMock

import pytest

pytest.importorskip("cryptography")

from attestplane.hashchain import chain_extend, genesis_head
from attestplane.signing import (
    InMemoryKeyProvider,
    SignaturePolicy,
    Signer,
    SigningError,
)
from attestplane.signing.base import KeyProviderError
from attestplane.types import ChainHead, EventDraft

_SEED_00 = b"\x00" * 32
_NOW_NAIVE = datetime(2026, 5, 17, 12, 0, 0)  # no tzinfo


def _build_chain(n: int) -> list:
    from datetime import UTC

    now = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    chain = []
    head = genesis_head()
    for i in range(n):
        draft = EventDraft(event_type="eval_event", actor=f"a{i}", payload={"i": i})
        ev = chain_extend(head, draft, now=now, event_id=f"00000000-0000-7000-8000-{i:012d}")
        chain.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    return chain


# ---------------------------------------------------------------------------
# Line 229: sign_event with naive (tz-unaware) now()
# ---------------------------------------------------------------------------


def test_sign_event_rejects_naive_datetime() -> None:
    """Line 229: sign_event raises when now() returns naive datetime."""
    signer = Signer(
        chain_id="x",
        key_provider=InMemoryKeyProvider(seed=_SEED_00),
        now=lambda: _NOW_NAIVE,
    )
    chain = _build_chain(1)
    with pytest.raises(SigningError, match="UTC-aware"):
        signer.sign_event(chain[0])


# ---------------------------------------------------------------------------
# Line 255: sign_segment_head with naive (tz-unaware) now()
# ---------------------------------------------------------------------------


def test_sign_segment_head_rejects_naive_datetime() -> None:
    """Line 255: sign_segment_head raises when now() returns naive datetime."""
    signer = Signer(
        chain_id="x",
        key_provider=InMemoryKeyProvider(seed=_SEED_00),
        now=lambda: _NOW_NAIVE,
    )
    head = ChainHead(seq=0, event_hash=b"\xab" * 32)
    with pytest.raises(SigningError, match="UTC-aware"):
        signer.sign_segment_head(head)


# ---------------------------------------------------------------------------
# Line 277: enqueue_segment_head with seq < 0
# ---------------------------------------------------------------------------


def test_enqueue_segment_head_rejects_negative_seq() -> None:
    """Line 277: enqueue_segment_head raises for genesis sentinel."""
    signer = Signer(chain_id="x", key_provider=InMemoryKeyProvider(seed=_SEED_00))
    with pytest.raises(SigningError, match="seq >= 0"):
        signer.enqueue_segment_head(ChainHead(seq=-1, event_hash=b"\x00" * 32))


# ---------------------------------------------------------------------------
# Lines 316-319: step_once exception path (provider_errors + re-raise)
# ---------------------------------------------------------------------------


def test_step_once_exception_increments_provider_errors() -> None:
    """Lines 316-319: step_once catches Exception, increments provider_errors, re-raises."""
    from datetime import UTC

    now_utc = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)

    # Provider that raises KeyProviderError on get_signing_material
    bad_provider = MagicMock()
    bad_provider.provider_id = "bad"
    bad_provider.schema_version = 1
    bad_provider.get_signing_material.side_effect = KeyProviderError("simulated failure")

    signer = Signer(
        chain_id="x",
        key_provider=bad_provider,
        now=lambda: now_utc,
    )
    head = ChainHead(seq=0, event_hash=b"\xab" * 32)
    signer.enqueue_segment_head(head)

    with pytest.raises(SigningError, match="step_once failed"):
        signer.step_once()

    assert signer.stats().provider_errors == 1


# ---------------------------------------------------------------------------
# Line 346: pull_segment_heads_from_snapshot with empty chain
# ---------------------------------------------------------------------------


def test_pull_segment_heads_empty_chain_returns_zero() -> None:
    """Line 346: snapshot returns empty list → returns 0 without enqueuing."""
    signer = Signer(
        chain_id="x",
        key_provider=InMemoryKeyProvider(seed=_SEED_00),
        snapshot=lambda: [],
    )
    result = signer.pull_segment_heads_from_snapshot()
    assert result == 0
    assert signer.pending_count() == 0


# ---------------------------------------------------------------------------
# Lines 394-396: _run exception in pull_segment_heads_from_snapshot
# ---------------------------------------------------------------------------


def test_run_snapshot_exception_increments_provider_errors() -> None:
    """Lines 394-396: _run catches Exception from pull_segment_heads_from_snapshot."""
    from datetime import UTC

    now_utc = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    call_count = [0]

    def bad_snapshot():
        call_count[0] += 1
        raise RuntimeError("snapshot exploded")

    signer = Signer(
        chain_id="x",
        key_provider=InMemoryKeyProvider(seed=_SEED_00),
        snapshot=bad_snapshot,
        now=lambda: now_utc,
    )
    signer.start()
    # Wake immediately so snapshot is called
    signer._wakeup.set()
    deadline = time.time() + 2.0
    while time.time() < deadline and call_count[0] == 0:
        time.sleep(0.01)
    signer.stop(timeout=2.0)
    # provider_errors should have been incremented by the exception handler
    assert signer.stats().provider_errors >= 1


# ---------------------------------------------------------------------------
# Lines 401-403: _run SigningError from step_once breaks inner loop
# ---------------------------------------------------------------------------


def test_run_signing_error_in_step_once_breaks_inner_loop() -> None:
    """Lines 401-403: _run catches SigningError from step_once, breaks inner loop."""
    from datetime import UTC

    now_utc = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)

    # Provider that raises on first call
    call_count = [0]
    real_provider = InMemoryKeyProvider(seed=_SEED_00)

    bad_provider = MagicMock()
    bad_provider.provider_id = "bad"
    bad_provider.schema_version = 1

    def side_effect():
        call_count[0] += 1
        if call_count[0] == 1:
            raise KeyProviderError("first call fails")
        return real_provider.get_signing_material()

    bad_provider.get_signing_material.side_effect = side_effect

    signer = Signer(
        chain_id="x",
        key_provider=bad_provider,
        now=lambda: now_utc,
    )
    # Enqueue an item that will trigger the exception in step_once
    head = ChainHead(seq=0, event_hash=b"\xab" * 32)
    with signer._lock:
        from attestplane.signing.signer import _PendingSignature
        signer._queue.append(_PendingSignature(head=head, mode="segment_head"))

    signer.start()
    signer._wakeup.set()
    deadline = time.time() + 2.0
    while time.time() < deadline and signer.stats().provider_errors == 0:
        time.sleep(0.01)
    signer.stop(timeout=2.0)
    assert signer.stats().provider_errors >= 1


# ---------------------------------------------------------------------------
# Extra: pull_segment_heads_from_snapshot with batch boundaries
# ---------------------------------------------------------------------------


def test_pull_segment_heads_batch_boundary_enqueues() -> None:
    """Ensure batch_size-aligned segment heads are enqueued."""
    from datetime import UTC

    now_utc = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    chain = _build_chain(10)

    signer = Signer(
        chain_id="x",
        key_provider=InMemoryKeyProvider(seed=_SEED_00),
        snapshot=lambda: chain,
        policy=SignaturePolicy(batch_size=4),
        now=lambda: now_utc,
    )
    enqueued = signer.pull_segment_heads_from_snapshot()
    # batch_size=4: boundaries at s where (s+1) % 4 == 0 → s=3,7 + tail s=9
    assert enqueued >= 2
    assert signer.pending_count() == enqueued
