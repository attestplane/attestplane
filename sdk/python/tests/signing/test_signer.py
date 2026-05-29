# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for :class:`attestplane.signing.Signer` (T3)."""

from __future__ import annotations

import threading
from datetime import UTC, datetime

import pytest

pytest.importorskip("cryptography")


from attestplane.canonical import canonicalize
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.signing import (
    InMemoryKeyProvider,
    MultiSignerProvider,
    SignaturePolicy,
    SignatureRecord,
    Signer,
    SigningError,
)
from attestplane.signing.signer import (
    _build_per_event_payload,
    _build_segment_head_payload,
)
from attestplane.types import ChainHead, EventDraft

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_SEED_00 = b"\x00" * 32
_SEED_01 = b"\x01" * 32
_SEED_02 = b"\x02" * 32


def _build_chain(n: int) -> list:
    chain = []
    head = genesis_head()
    for i in range(n):
        draft = EventDraft(
            event_type="eval_event",
            actor=f"a{i}",
            payload={"i": i},
        )
        ev = chain_extend(head, draft, now=_NOW, event_id=f"00000000-0000-7000-8000-{i:012d}")
        chain.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    return chain


# --- _build_segment_head_payload -------------------------------------------


def test_segment_head_payload_locked_recipe() -> None:
    """The 5-key canonical recipe per architect review § 1 decision 1."""
    head = ChainHead(seq=4, event_hash=bytes.fromhex("ab" * 32))
    bytes_out = _build_segment_head_payload("vec-1", head)
    # Alphabetical sort → chain_id, event_hash, schema_version, seq,
    # signature_schema_version.
    expected = (
        b'{"chain_id":"vec-1","event_hash":"'
        + b"ab" * 32
        + b'","schema_version":1,"seq":4,"signature_schema_version":1}'
    )
    assert bytes_out == expected


def test_segment_head_payload_rejects_empty_chain_id() -> None:
    head = ChainHead(seq=0, event_hash=bytes.fromhex("ab" * 32))
    with pytest.raises(SigningError, match="chain_id"):
        _build_segment_head_payload("", head)


# --- _build_per_event_payload ----------------------------------------------


def test_per_event_payload_equals_canonicalize() -> None:
    """Per-event = canonicalize(AuditEvent) = hash_event input."""
    chain = _build_chain(1)
    payload = _build_per_event_payload(chain[0].event)
    assert payload == canonicalize(chain[0].event)


# --- Signer construction --------------------------------------------------


def test_signer_rejects_empty_chain_id() -> None:
    with pytest.raises(ValueError, match="chain_id"):
        Signer(
            chain_id="",
            key_provider=InMemoryKeyProvider(seed=_SEED_00),
        )


def test_signer_default_policy() -> None:
    s = Signer(
        chain_id="x",
        key_provider=InMemoryKeyProvider(seed=_SEED_00),
    )
    # Internal state — sanity check.
    assert s._policy.batch_size == 64


# --- sign_segment_head (single provider) -----------------------------------


def test_sign_segment_head_produces_valid_record() -> None:
    provider = InMemoryKeyProvider(seed=_SEED_00)
    signer = Signer(chain_id="vec-1", key_provider=provider, now=lambda: _NOW)

    head = ChainHead(seq=4, event_hash=bytes.fromhex("ab" * 32))
    records = signer.sign_segment_head(head)

    assert len(records) == 1
    r = records[0]
    assert isinstance(r, SignatureRecord)
    assert r.signed_seq == 4
    assert r.signature_mode == "segment_head"
    assert len(r.signature) == 64
    assert r.signed_payload == _build_segment_head_payload("vec-1", head)


def test_sign_segment_head_rejects_genesis() -> None:
    provider = InMemoryKeyProvider(seed=_SEED_00)
    signer = Signer(chain_id="x", key_provider=provider)
    with pytest.raises(SigningError, match="genesis"):
        signer.sign_segment_head(ChainHead(seq=-1, event_hash=b"\x00" * 32))


def test_sign_segment_head_deterministic_for_same_seed() -> None:
    """Ed25519 deterministic signatures + same seed + same payload = byte-identical sig."""
    provider_a = InMemoryKeyProvider(seed=_SEED_00)
    provider_b = InMemoryKeyProvider(seed=_SEED_00)
    head = ChainHead(seq=4, event_hash=bytes.fromhex("ab" * 32))

    sig_a = Signer(chain_id="x", key_provider=provider_a, now=lambda: _NOW).sign_segment_head(head)
    sig_b = Signer(chain_id="x", key_provider=provider_b, now=lambda: _NOW).sign_segment_head(head)

    assert sig_a[0].signature == sig_b[0].signature
    assert sig_a[0].key_id == sig_b[0].key_id
    assert sig_a[0].signed_payload == sig_b[0].signed_payload


# --- sign_event (per-event mode) -------------------------------------------


def test_sign_event_uses_canonicalize_audit_event() -> None:
    chain = _build_chain(1)
    signer = Signer(
        chain_id="x",
        key_provider=InMemoryKeyProvider(seed=_SEED_01),
        now=lambda: _NOW,
    )
    records = signer.sign_event(chain[0])
    assert len(records) == 1
    r = records[0]
    assert r.signature_mode == "per_event"
    assert r.signed_payload == canonicalize(chain[0].event)
    assert r.signed_event_hash == chain[0].event_hash


# --- MultiSignerProvider plurality -----------------------------------------


def test_signer_with_multi_signer_produces_n_records() -> None:
    provider = MultiSignerProvider(
        [
            InMemoryKeyProvider(seed=_SEED_00, provider_id="alpha"),
            InMemoryKeyProvider(seed=_SEED_02, provider_id="beta"),
        ]
    )
    signer = Signer(chain_id="vec-1", key_provider=provider, now=lambda: _NOW)
    head = ChainHead(seq=4, event_hash=bytes.fromhex("ab" * 32))
    records = signer.sign_segment_head(head)

    assert len(records) == 2
    # Same payload, different keys + signatures.
    assert records[0].signed_payload == records[1].signed_payload
    assert records[0].key_id != records[1].key_id
    assert records[0].signature != records[1].signature


# --- Background worker mode ------------------------------------------------


def test_step_once_returns_none_on_empty_queue() -> None:
    signer = Signer(chain_id="x", key_provider=InMemoryKeyProvider(seed=_SEED_00))
    assert signer.step_once() is None


def test_enqueue_segment_head_then_step_once() -> None:
    signer = Signer(
        chain_id="x",
        key_provider=InMemoryKeyProvider(seed=_SEED_00),
        now=lambda: _NOW,
    )
    head = ChainHead(seq=0, event_hash=bytes.fromhex("ab" * 32))
    signer.enqueue_segment_head(head)
    result = signer.step_once()
    assert result is not None
    assert result.pending_seq == 0
    assert result.mode == "segment_head"
    assert len(result.records) == 1


def test_enqueue_event_per_event_path() -> None:
    chain = _build_chain(1)
    signer = Signer(
        chain_id="x",
        key_provider=InMemoryKeyProvider(seed=_SEED_01),
        now=lambda: _NOW,
    )
    signer.enqueue_event(chain[0])
    result = signer.step_once()
    assert result is not None
    assert result.mode == "per_event"
    assert result.records[0].signed_payload == canonicalize(chain[0].event)


def test_stats_tracked() -> None:
    signer = Signer(
        chain_id="x",
        key_provider=InMemoryKeyProvider(seed=_SEED_00),
        now=lambda: _NOW,
    )
    head = ChainHead(seq=0, event_hash=bytes.fromhex("ab" * 32))
    signer.sign_segment_head(head)
    signer.sign_segment_head(head)
    stats = signer.stats()
    assert stats.signed_segment_heads == 2
    assert stats.signed_events == 0


def test_drained_results_destructive() -> None:
    signer = Signer(
        chain_id="x",
        key_provider=InMemoryKeyProvider(seed=_SEED_00),
        now=lambda: _NOW,
    )
    head = ChainHead(seq=0, event_hash=bytes.fromhex("ab" * 32))
    signer.enqueue_segment_head(head)
    signer.step_once()

    first = signer.drained_results()
    assert len(first) == 1

    second = signer.drained_results()
    assert second == []


def test_background_worker_drains_queue() -> None:
    """Spawn the daemon, enqueue, and confirm it processes."""
    signer = Signer(
        chain_id="x",
        key_provider=InMemoryKeyProvider(seed=_SEED_00),
        now=lambda: _NOW,
    )
    signer.start()
    for i in range(3):
        signer.enqueue_segment_head(
            ChainHead(seq=i, event_hash=bytes([i + 1]) * 32),
        )

    deadline = threading.Event()
    timer = threading.Timer(2.0, deadline.set)
    timer.start()
    while not deadline.is_set() and signer.pending_count() > 0:
        pass
    timer.cancel()

    signer.stop(timeout=2.0)
    assert signer.stats().signed_segment_heads == 3


def test_start_is_idempotent() -> None:
    signer = Signer(chain_id="x", key_provider=InMemoryKeyProvider(seed=_SEED_00))
    signer.start()
    signer.start()
    signer.stop()


def test_stop_without_start_is_safe() -> None:
    signer = Signer(chain_id="x", key_provider=InMemoryKeyProvider(seed=_SEED_00))
    signer.stop()


def test_pull_segment_heads_from_snapshot_no_callback_returns_zero() -> None:
    signer = Signer(chain_id="x", key_provider=InMemoryKeyProvider(seed=_SEED_00))
    assert signer.pull_segment_heads_from_snapshot() == 0


def test_pull_segment_heads_from_snapshot_via_callback() -> None:
    chain = _build_chain(3)
    signer = Signer(
        chain_id="x",
        key_provider=InMemoryKeyProvider(seed=_SEED_00),
        snapshot=lambda: chain,
        policy=SignaturePolicy(batch_size=10, max_idle_seconds=60),
        now=lambda: _NOW,
    )
    enqueued = signer.pull_segment_heads_from_snapshot()
    # batch_size=10 > chain length, so only the tail is signed.
    assert enqueued == 1
    assert signer.pending_count() == 1


# --- Substrate decoupling guarantee ---------------------------------------


def test_substrate_module_does_not_import_signer() -> None:
    """Architect review § 1 decision 4 — Signer is NOT in substrate's import path."""
    import attestplane.substrate as substrate_mod

    src = open(substrate_mod.__file__).read()
    assert "from attestplane.signing" not in src
    assert "import attestplane.signing" not in src
    assert "Signer" not in src  # method name "sign" elsewhere irrelevant
