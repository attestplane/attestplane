# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ``AttestSubstrate`` container."""

from __future__ import annotations

import threading
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from attestplane import AttestSubstrate, EventDraft, SubjectRef
from attestplane.hashchain import GENESIS_HASH


def _draft(i: int) -> EventDraft:
    return EventDraft(event_type="ai_decision", actor="agent-a", payload={"i": i})


def test_empty_substrate_state() -> None:
    sub = AttestSubstrate()
    assert len(sub) == 0
    assert sub.head_seq() == -1
    assert sub.tip().event_hash == GENESIS_HASH
    assert sub.verify().ok is True
    assert list(sub) == []


def test_append_assigns_chain_fields() -> None:
    sub = AttestSubstrate()
    a = sub.append(_draft(0), now=datetime(2026, 5, 17, tzinfo=UTC))
    assert a.seq == 0
    assert a.prev_hash == GENESIS_HASH
    assert sub.head_seq() == 0
    assert sub.tip().event_hash == a.event_hash
    assert len(sub) == 1


def test_three_appends_link_correctly_and_verify() -> None:
    sub = AttestSubstrate()
    events = [
        sub.append(_draft(i), now=datetime(2026, 5, 17, 12, 0, 0, i, tzinfo=UTC))
        for i in range(3)
    ]
    assert [e.seq for e in events] == [0, 1, 2]
    assert events[1].prev_hash == events[0].event_hash
    assert events[2].prev_hash == events[1].event_hash
    assert sub.verify().ok is True


def test_iterator_takes_snapshot() -> None:
    sub = AttestSubstrate()
    sub.append(_draft(0), now=datetime(2026, 5, 17, tzinfo=UTC))
    snapshot_iter = iter(sub)
    sub.append(_draft(1), now=datetime(2026, 5, 17, 12, 0, 0, 1, tzinfo=UTC))
    collected = list(snapshot_iter)
    assert len(collected) == 1


def test_from_events_rehydrates() -> None:
    source = AttestSubstrate()
    for i in range(3):
        source.append(_draft(i), now=datetime(2026, 5, 17, 12, 0, 0, i, tzinfo=UTC))
    rehydrated = AttestSubstrate.from_events(source.snapshot())
    assert len(rehydrated) == 3
    assert rehydrated.tip() == source.tip()
    assert rehydrated.verify().ok is True


def test_from_events_rejects_broken_chain() -> None:
    source = AttestSubstrate()
    for i in range(2):
        source.append(_draft(i), now=datetime(2026, 5, 17, 12, 0, 0, i, tzinfo=UTC))
    events = source.snapshot()
    tampered = list(events)
    tampered[0] = replace(tampered[0], event_hash=b"\x00" * 32)
    with pytest.raises(ValueError, match="rehydrate"):
        AttestSubstrate.from_events(tampered)


def test_concurrent_append_produces_valid_chain() -> None:
    sub = AttestSubstrate()
    n_threads = 8
    per_thread = 25
    errors: list[BaseException] = []

    def worker(tid: int) -> None:
        try:
            for i in range(per_thread):
                sub.append(
                    EventDraft(
                        event_type="ai_decision",
                        actor=f"agent-{tid}",
                        payload={"tid": tid, "i": i},
                    )
                )
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(sub) == n_threads * per_thread
    result = sub.verify()
    assert result.ok is True, result.reason
    seqs = [e.seq for e in sub.snapshot()]
    assert seqs == list(range(len(sub)))


def test_event_id_is_uuidv7() -> None:
    sub = AttestSubstrate()
    e = sub.append(_draft(0), now=datetime(2026, 5, 17, tzinfo=UTC))
    parts = e.event.event_id.split("-")
    assert len(parts) == 5
    assert parts[2][0] == "7"


def test_art12_fields_are_included_in_hash() -> None:
    sub_a = AttestSubstrate()
    sub_b = AttestSubstrate()
    now = datetime(2026, 5, 17, tzinfo=UTC)
    bare = EventDraft(event_type="t", actor="a")
    enriched = EventDraft(
        event_type="t",
        actor="a",
        session_id="session-xyz",
        reference_db_ref="db://watchlist/v1",
        matched_input_ref="hash:abc",
        human_verifier=SubjectRef(scheme="opaque", value="reviewer-1"),
    )
    ev_a = sub_a.append(bare, now=now)
    ev_b = sub_b.append(enriched, now=now)
    assert ev_a.event_hash != ev_b.event_hash


def test_subject_ref_none_scheme_requires_empty_value() -> None:
    with pytest.raises(ValueError, match="empty"):
        SubjectRef(scheme="none", value="x")


def test_subject_ref_non_none_scheme_requires_non_empty_value() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        SubjectRef(scheme="opaque", value="")


def test_event_draft_requires_event_type_and_actor() -> None:
    with pytest.raises(ValueError, match="event_type"):
        EventDraft(event_type="", actor="a")
    with pytest.raises(ValueError, match="actor"):
        EventDraft(event_type="t", actor="")
