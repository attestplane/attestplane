# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Property-based tests for the canonicalization and hash-chain layers.

These tests use Hypothesis to generate large numbers of random inputs that
satisfy the restricted-JSON profile of ADR-0002, and verify that load-bearing
invariants hold uniformly:

- canonicalize is deterministic regardless of dict insertion order.
- chain_extend is pure: same (tip, draft, now, event_id) → same ChainedEvent.
- A chain produced by repeated chain_extend always verifies.
- Tampering with the payload, prev_hash, seq, or event_hash of any event
  causes verify_chain to fail at an index no later than the tampered one.
"""

from __future__ import annotations

import string
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from attestplane import (
    AttestSubstrate,
    EventDraft,
    SubjectRef,
)
from attestplane.canonical import canonicalize
from attestplane.hashchain import (
    chain_extend,
    genesis_head,
    hash_event,
    head_of,
    verify_chain,
)
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st


def _safe_text() -> st.SearchStrategy[str]:
    """Restricted-profile-safe strings: ASCII printable, NFC-stable."""
    return st.text(
        alphabet=string.ascii_letters + string.digits + "-_.@/:",
        min_size=0,
        max_size=20,
    )


def _restricted_json_value() -> st.SearchStrategy[Any]:
    """Recursive JSON values that satisfy the restricted-JSON profile."""
    primitives = st.none() | st.booleans() | st.integers(min_value=-(2**63), max_value=2**63 - 1) | _safe_text()
    return st.recursive(
        primitives,
        lambda children: st.lists(children, max_size=4) | st.dictionaries(_safe_text(), children, max_size=4),
        max_leaves=12,
    )


_subject_ref = st.builds(
    SubjectRef,
    scheme=st.sampled_from(["opaque", "sha256_salted"]),
    value=_safe_text().filter(lambda s: len(s) > 0),
)


_non_empty_safe_text = _safe_text().filter(lambda s: len(s) > 0)


_event_draft = st.builds(
    EventDraft,
    event_type=_non_empty_safe_text,
    actor=_non_empty_safe_text,
    payload=st.dictionaries(_safe_text(), _restricted_json_value(), max_size=4),
    subject_ref=st.one_of(st.none(), _subject_ref),
    session_id=st.one_of(st.none(), _safe_text()),
    reference_db_ref=st.one_of(st.none(), _safe_text()),
    matched_input_ref=st.one_of(st.none(), _safe_text()),
    human_verifier=st.one_of(st.none(), _subject_ref),
)


_FIXED_NOW = datetime(2026, 5, 17, tzinfo=UTC)


@given(draft=_event_draft)
def test_chain_extend_is_pure(draft: EventDraft) -> None:
    a = chain_extend(genesis_head(), draft, now=_FIXED_NOW, event_id="x")
    b = chain_extend(genesis_head(), draft, now=_FIXED_NOW, event_id="x")
    assert a == b
    assert a.event_hash == b.event_hash


@given(draft=_event_draft)
def test_hash_event_is_deterministic(draft: EventDraft) -> None:
    chained = chain_extend(genesis_head(), draft, now=_FIXED_NOW, event_id="x")
    assert hash_event(chained.event) == chained.event_hash
    assert hash_event(chained.event) == hash_event(chained.event)


@given(draft=_event_draft)
def test_canonicalize_event_is_deterministic(draft: EventDraft) -> None:
    chained = chain_extend(genesis_head(), draft, now=_FIXED_NOW, event_id="x")
    assert canonicalize(chained.event) == canonicalize(chained.event)


@given(
    keys=st.lists(_safe_text(), min_size=2, max_size=8, unique=True),
    values=st.lists(_restricted_json_value(), min_size=2, max_size=8),
)
def test_canonicalize_object_is_insertion_order_invariant(keys: list[str], values: list[Any]) -> None:
    n = min(len(keys), len(values))
    items = list(zip(keys[:n], values[:n], strict=True))
    forward = dict(items)
    reverse = dict(reversed(items))
    assert canonicalize(forward) == canonicalize(reverse)


@given(drafts=st.lists(_event_draft, min_size=1, max_size=10))
def test_chain_of_n_appends_verifies(drafts: list[EventDraft]) -> None:
    sub = AttestSubstrate()
    for i, draft in enumerate(drafts):
        sub.append(draft, now=_FIXED_NOW + timedelta(microseconds=i))
    assert len(sub) == len(drafts)
    result = sub.verify()
    assert result.ok, result.reason


@given(drafts=st.lists(_event_draft, min_size=2, max_size=8), data=st.data())
def test_tampering_with_event_hash_is_detected(drafts: list[EventDraft], data: st.DataObject) -> None:
    sub = AttestSubstrate()
    for i, draft in enumerate(drafts):
        sub.append(draft, now=_FIXED_NOW + timedelta(microseconds=i))
    events = sub.snapshot()
    i = data.draw(st.integers(min_value=0, max_value=len(events) - 1))
    tampered = list(events)
    tampered[i] = replace(tampered[i], event_hash=b"\xff" * 32)
    result = verify_chain(tampered)
    assert not result.ok
    assert result.first_bad_index is not None
    assert result.first_bad_index <= i


@given(drafts=st.lists(_event_draft, min_size=2, max_size=8), data=st.data())
def test_tampering_with_prev_hash_is_detected(drafts: list[EventDraft], data: st.DataObject) -> None:
    sub = AttestSubstrate()
    for i, draft in enumerate(drafts):
        sub.append(draft, now=_FIXED_NOW + timedelta(microseconds=i))
    events = sub.snapshot()
    i = data.draw(st.integers(min_value=1, max_value=len(events) - 1))
    tampered = list(events)
    tampered[i] = replace(tampered[i], prev_hash=b"\x00" * 32)
    result = verify_chain(tampered)
    assert not result.ok
    assert result.first_bad_index is not None
    assert result.first_bad_index <= i


@given(drafts=st.lists(_event_draft, min_size=2, max_size=8), data=st.data())
def test_tampering_with_seq_is_detected(drafts: list[EventDraft], data: st.DataObject) -> None:
    sub = AttestSubstrate()
    for i, draft in enumerate(drafts):
        sub.append(draft, now=_FIXED_NOW + timedelta(microseconds=i))
    events = sub.snapshot()
    i = data.draw(st.integers(min_value=0, max_value=len(events) - 1))
    tampered = list(events)
    bad_seq = tampered[i].seq + 100
    tampered[i] = replace(tampered[i], seq=bad_seq)
    result = verify_chain(tampered)
    assert not result.ok
    assert result.first_bad_index is not None
    assert result.first_bad_index <= i


@given(drafts=st.lists(_event_draft, min_size=2, max_size=6))
def test_chain_extend_advances_tip(drafts: list[EventDraft]) -> None:
    tip = genesis_head()
    chain: list[Any] = []
    for i, draft in enumerate(drafts):
        now = _FIXED_NOW + timedelta(microseconds=i)
        chained = chain_extend(tip, draft, now=now, event_id=f"e{i}")
        assert chained.seq == i
        assert chained.prev_hash == tip.event_hash
        chain.append(chained)
        tip = head_of(chain)
        assert tip.seq == i
        assert tip.event_hash == chained.event_hash


@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=30)
@given(drafts=st.lists(_event_draft, min_size=3, max_size=20))
def test_rehydrate_then_verify_round_trip(drafts: list[EventDraft]) -> None:
    source = AttestSubstrate()
    for i, draft in enumerate(drafts):
        source.append(draft, now=_FIXED_NOW + timedelta(microseconds=i))
    rehydrated = AttestSubstrate.from_events(source.snapshot())
    assert rehydrated.tip() == source.tip()
    assert rehydrated.verify().ok
    assert [e.event_hash for e in rehydrated.snapshot()] == [e.event_hash for e in source.snapshot()]
