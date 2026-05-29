# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Conformance test against the frozen ``vectors.json``.

If this test fails, the canonicalization or chain-extend semantics have drifted
from the ADR-0002 contract. Reproducing the published hex requires either
fixing the implementation or, if the change is intentional, bumping
``SCHEMA_VERSION`` and emitting a new vector set under a new filename.

The existing ``vectors.json`` is never overwritten in place.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from attestplane.canonical import canonicalize
from attestplane.hashchain import SCHEMA_VERSION, chain_extend, genesis_head, head_of
from attestplane.types import ChainHead, EventDraft, SubjectRef

_VECTORS_PATH = Path(__file__).parent / "conformance" / "vectors.json"


def _load_vectors() -> dict[str, Any]:
    return json.loads(_VECTORS_PATH.read_text(encoding="utf-8"))


def _build_draft(raw: dict[str, Any]) -> EventDraft:
    def subject(value: dict[str, Any] | None) -> SubjectRef | None:
        if value is None:
            return None
        return SubjectRef(scheme=value["scheme"], value=value["value"])

    return EventDraft(
        event_type=raw["event_type"],
        actor=raw["actor"],
        payload=raw.get("payload", {}),
        subject_ref=subject(raw.get("subject_ref")),
        session_id=raw.get("session_id"),
        reference_db_ref=raw.get("reference_db_ref"),
        matched_input_ref=raw.get("matched_input_ref"),
        human_verifier=subject(raw.get("human_verifier")),
    )


def test_schema_version_matches() -> None:
    vectors = _load_vectors()
    assert vectors["schema_version"] == SCHEMA_VERSION


def test_ten_vectors_exist() -> None:
    vectors = _load_vectors()
    assert len(vectors["entries"]) == 10


@pytest.mark.parametrize("index", range(10))
def test_vector_event_hash_reproducible(index: int) -> None:
    vectors = _load_vectors()
    entry = vectors["entries"][index]
    ts = datetime.strptime(entry["timestamp"], "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(UTC)
    head = genesis_head() if index == 0 else _head_at(vectors, index - 1)
    chained = chain_extend(head, _build_draft(entry["draft"]), now=ts, event_id=entry["event_id"])
    assert chained.event_hash.hex() == entry["event_hash_hex"], f"vector {entry['name']!r}: event_hash drift"
    assert hashlib.sha256(canonicalize(chained.event)).hexdigest() == entry["canonical_bytes_sha256_hex"]
    assert chained.prev_hash.hex() == entry["prev_hash_hex"]
    assert chained.seq == entry["seq"]


def test_final_chain_head_matches() -> None:
    vectors = _load_vectors()
    head = genesis_head()
    chain = []
    for entry in vectors["entries"]:
        ts = datetime.strptime(entry["timestamp"], "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(UTC)
        chained = chain_extend(head, _build_draft(entry["draft"]), now=ts, event_id=entry["event_id"])
        chain.append(chained)
        head = head_of(chain)
    assert head.event_hash.hex() == vectors["final_chain_head_hex"]


def _head_at(vectors: dict[str, Any], index: int) -> ChainHead:
    return ChainHead(
        seq=vectors["entries"][index]["seq"],
        event_hash=bytes.fromhex(vectors["entries"][index]["event_hash_hex"]),
    )
