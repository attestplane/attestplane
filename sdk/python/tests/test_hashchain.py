# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the pure hashchain primitives."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from attestplane.canonical import canonicalize
from attestplane.hashchain import (
    GENESIS_HASH,
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    chain_extend,
    genesis_head,
    head_of,
    verify_chain,
)
from attestplane.types import EventDraft, SubjectRef


def _utc(year: int, month: int, day: int, *, micro: int = 0) -> datetime:
    return datetime(year, month, day, 12, 0, 0, micro, tzinfo=UTC)


def test_genesis_head_constants() -> None:
    head = genesis_head()
    assert head.seq == -1
    assert head.event_hash == GENESIS_HASH
    assert len(GENESIS_HASH) == 32
    assert GENESIS_HASH == b"\x00" * 32


def test_schema_version_is_frozen_at_v1() -> None:
    assert SCHEMA_VERSION == 1
    assert SUPPORTED_SCHEMA_VERSIONS == (1,)


def test_chain_extend_assigns_seq_and_links_genesis() -> None:
    draft = EventDraft(event_type="ai_decision", actor="agent-a")
    chained = chain_extend(genesis_head(), draft, now=_utc(2026, 5, 17), event_id="evt-1")
    assert chained.seq == 0
    assert chained.prev_hash == GENESIS_HASH
    assert chained.event.schema_version == SCHEMA_VERSION
    assert chained.event.event_id == "evt-1"


def test_chain_extend_is_deterministic_given_event_id() -> None:
    draft = EventDraft(event_type="ai_decision", actor="agent-a", payload={"k": 1})
    a = chain_extend(genesis_head(), draft, now=_utc(2026, 5, 17), event_id="x")
    b = chain_extend(genesis_head(), draft, now=_utc(2026, 5, 17), event_id="x")
    assert a == b
    assert a.event_hash == b.event_hash


def test_chain_extend_rejects_non_utc() -> None:
    draft = EventDraft(event_type="t", actor="a")
    naive = datetime(2026, 5, 17, 12, 0, 0)
    with pytest.raises(ValueError, match="UTC"):
        chain_extend(genesis_head(), draft, now=naive)


def test_chain_extend_generates_uuidv7_when_not_provided() -> None:
    draft = EventDraft(event_type="t", actor="a")
    chained = chain_extend(genesis_head(), draft, now=_utc(2026, 5, 17))
    assert len(chained.event.event_id) == 36
    assert chained.event.event_id[14] == "7"


def test_hash_event_matches_sha256_of_canonical_form() -> None:
    draft = EventDraft(event_type="t", actor="a", payload={"x": 1})
    chained = chain_extend(genesis_head(), draft, now=_utc(2026, 5, 17), event_id="e")
    expected = hashlib.sha256(canonicalize(chained.event)).digest()
    assert chained.event_hash == expected


def test_verify_chain_empty_is_ok() -> None:
    result = verify_chain([])
    assert result.ok is True
    assert result.first_bad_index is None


def test_verify_chain_three_appends_ok() -> None:
    events = []
    head = genesis_head()
    for i in range(3):
        draft = EventDraft(event_type="t", actor="a", payload={"i": i})
        chained = chain_extend(head, draft, now=_utc(2026, 5, 17, micro=i), event_id=f"e{i}")
        events.append(chained)
        head = head_of(events)
    result = verify_chain(events)
    assert result.ok is True


def test_verify_chain_detects_payload_tamper_at_index_1() -> None:
    events = []
    head = genesis_head()
    for i in range(3):
        draft = EventDraft(event_type="t", actor="a", payload={"i": i})
        chained = chain_extend(head, draft, now=_utc(2026, 5, 17, micro=i), event_id=f"e{i}")
        events.append(chained)
        head = head_of(events)
    tampered_event = replace(events[1].event, payload={"i": 99})
    events[1] = replace(events[1], event=tampered_event)
    result = verify_chain(events)
    assert result.ok is False
    assert result.first_bad_index == 1
    assert "event_hash" in (result.reason or "")


def test_verify_chain_detects_broken_prev_hash() -> None:
    events = []
    head = genesis_head()
    for i in range(2):
        draft = EventDraft(event_type="t", actor="a")
        chained = chain_extend(head, draft, now=_utc(2026, 5, 17, micro=i), event_id=f"e{i}")
        events.append(chained)
        head = head_of(events)
    events[1] = replace(events[1], prev_hash=b"\xff" * 32)
    result = verify_chain(events)
    assert result.ok is False
    assert result.first_bad_index == 1
    assert "prev_hash" in (result.reason or "")


def test_verify_chain_detects_seq_skip() -> None:
    head = genesis_head()
    draft = EventDraft(event_type="t", actor="a")
    a = chain_extend(head, draft, now=_utc(2026, 5, 17), event_id="e0")
    bad = replace(a, seq=5)
    result = verify_chain([bad])
    assert result.ok is False
    assert "seq mismatch" in (result.reason or "")


def test_subject_ref_changes_change_hash() -> None:
    base = EventDraft(event_type="t", actor="a")
    with_subject = EventDraft(
        event_type="t",
        actor="a",
        subject_ref=SubjectRef(scheme="opaque", value="user-1"),
    )
    a = chain_extend(genesis_head(), base, now=_utc(2026, 5, 17), event_id="e")
    b = chain_extend(genesis_head(), with_subject, now=_utc(2026, 5, 17), event_id="e")
    assert a.event_hash != b.event_hash


def test_micro_timestamp_difference_changes_hash() -> None:
    draft = EventDraft(event_type="t", actor="a")
    t1 = _utc(2026, 5, 17, micro=0)
    t2 = t1 + timedelta(microseconds=1)
    a = chain_extend(genesis_head(), draft, now=t1, event_id="e")
    b = chain_extend(genesis_head(), draft, now=t2, event_id="e")
    assert a.event_hash != b.event_hash
