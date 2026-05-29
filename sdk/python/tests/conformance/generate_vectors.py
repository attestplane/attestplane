# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Generate the conformance vector set for the restricted-JCS profile.

This script is run once per ``schema_version`` to produce ``vectors.json``,
which is then frozen as the cross-SDK conformance contract. It is also re-run
in CI to verify that the current implementation still produces the published
hex values.

If you change canonicalization rules you MUST also bump ``SCHEMA_VERSION`` and
emit a new vector set under a new filename; never overwrite an existing
``vectors.json``.

Run:

    python -m tests.conformance.generate_vectors > tests/conformance/vectors.json
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from attestplane.canonical import canonicalize
from attestplane.hashchain import SCHEMA_VERSION, chain_extend, genesis_head
from attestplane.types import ChainHead, EventDraft, SubjectRef


def _build_inputs() -> list[dict[str, Any]]:
    """Construct the ten golden inputs.

    Each entry is a serializable representation of an ``EventDraft`` plus a
    fixed clock value and a fixed ``event_id`` so the output is deterministic.
    Reproducing the hex for entry ``i`` is purely a function of the data here
    and the canonicalization spec — no SDK is required.
    """
    base_ts = "2026-05-17T12:00:00.000000Z"
    return [
        {
            "name": "minimal",
            "description": "smallest legal EventDraft: event_type + actor only",
            "event_id": "00000000-0000-7000-8000-000000000001",
            "timestamp": base_ts,
            "draft": {
                "event_type": "ai_decision",
                "actor": "agent://test/v1",
                "payload": {},
            },
        },
        {
            "name": "payload_ascii_string",
            "description": "ASCII string and integer in payload",
            "event_id": "00000000-0000-7000-8000-000000000002",
            "timestamp": base_ts,
            "draft": {
                "event_type": "ai_decision",
                "actor": "agent://test/v1",
                "payload": {"outcome": "approved", "score": 9120},
            },
        },
        {
            "name": "payload_nested_object",
            "description": "object key ordering must canonicalize alphabetically",
            "event_id": "00000000-0000-7000-8000-000000000003",
            "timestamp": base_ts,
            "draft": {
                "event_type": "ai_decision",
                "actor": "agent://test/v1",
                "payload": {"outer": {"z": 1, "a": 2, "m": [3, 2, 1]}},
            },
        },
        {
            "name": "subject_ref_opaque",
            "description": "SubjectRef with scheme opaque",
            "event_id": "00000000-0000-7000-8000-000000000004",
            "timestamp": base_ts,
            "draft": {
                "event_type": "ai_decision",
                "actor": "agent://test/v1",
                "payload": {},
                "subject_ref": {"scheme": "opaque", "value": "user-42"},
            },
        },
        {
            "name": "subject_ref_sha256_salted",
            "description": "SubjectRef with scheme sha256_salted",
            "event_id": "00000000-0000-7000-8000-000000000005",
            "timestamp": base_ts,
            "draft": {
                "event_type": "ai_decision",
                "actor": "agent://test/v1",
                "payload": {},
                "subject_ref": {
                    "scheme": "sha256_salted",
                    "value": "2c1b00000000000000000000000000000000000000000000000000000000e9",
                },
            },
        },
        {
            "name": "art12_full",
            "description": "all four Art. 12 fields populated",
            "event_id": "00000000-0000-7000-8000-000000000006",
            "timestamp": base_ts,
            "draft": {
                "event_type": "biometric_match",
                "actor": "agent://verifier/v1",
                "payload": {"top_k": 3},
                "subject_ref": {"scheme": "opaque", "value": "data-subject-01"},
                "session_id": "session-2026-05-17-abc",
                "reference_db_ref": "db://watchlist/v3",
                "matched_input_ref": "sha256:abcdef0123",
                "human_verifier": {"scheme": "opaque", "value": "reviewer-7"},
            },
        },
        {
            "name": "payload_utf8_nfc",
            "description": "NFC-normalized non-ASCII string survives canonicalization",
            "event_id": "00000000-0000-7000-8000-000000000007",
            "timestamp": base_ts,
            "draft": {
                "event_type": "ai_decision",
                "actor": "agent://test/v1",
                "payload": {"name": "café", "city": "München"},
            },
        },
        {
            "name": "payload_bytes_base64url",
            "description": "bytes are encoded as base64url without padding",
            "event_id": "00000000-0000-7000-8000-000000000008",
            "timestamp": base_ts,
            "draft": {
                "event_type": "ai_decision",
                "actor": "agent://test/v1",
                "payload": {
                    "blob_b64u": base64.urlsafe_b64encode(b"\x00\x01\x02").rstrip(b"=").decode(),
                },
            },
        },
        {
            "name": "payload_negative_and_int64_bounds",
            "description": "negative integers and int64 boundary values",
            "event_id": "00000000-0000-7000-8000-000000000009",
            "timestamp": base_ts,
            "draft": {
                "event_type": "ai_decision",
                "actor": "agent://test/v1",
                "payload": {"min": -(2**63), "max": 2**63 - 1, "neg": -1},
            },
        },
        {
            "name": "payload_array_order_preserved",
            "description": "arrays preserve insertion order, unlike objects",
            "event_id": "00000000-0000-7000-8000-000000000010",
            "timestamp": base_ts,
            "draft": {
                "event_type": "ai_decision",
                "actor": "agent://test/v1",
                "payload": {"items": ["z", "a", "m"], "ints": [3, 1, 2]},
            },
        },
    ]


def _build_draft(payload: dict[str, Any]) -> EventDraft:
    return EventDraft(
        event_type=payload["event_type"],
        actor=payload["actor"],
        payload=payload.get("payload", {}),
        subject_ref=_subject_ref(payload.get("subject_ref")),
        session_id=payload.get("session_id"),
        reference_db_ref=payload.get("reference_db_ref"),
        matched_input_ref=payload.get("matched_input_ref"),
        human_verifier=_subject_ref(payload.get("human_verifier")),
    )


def _subject_ref(raw: dict[str, Any] | None) -> SubjectRef | None:
    if raw is None:
        return None
    return SubjectRef(scheme=raw["scheme"], value=raw["value"])


def generate() -> dict[str, Any]:
    inputs = _build_inputs()
    head = genesis_head()
    entries: list[dict[str, Any]] = []
    chain_running_hash = head.event_hash
    for entry in inputs:
        ts = datetime.strptime(entry["timestamp"], "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(UTC)
        draft = _build_draft(entry["draft"])
        chained = chain_extend(head, draft, now=ts, event_id=entry["event_id"])
        canonical_bytes = canonicalize(chained.event)
        entry_record = {
            "name": entry["name"],
            "description": entry["description"],
            "seq": chained.seq,
            "event_id": chained.event.event_id,
            "timestamp": entry["timestamp"],
            "draft": entry["draft"],
            "prev_hash_hex": chained.prev_hash.hex(),
            "canonical_bytes_sha256_hex": hashlib.sha256(canonical_bytes).hexdigest(),
            "event_hash_hex": chained.event_hash.hex(),
        }
        entries.append(entry_record)
        head = head_record_from(chained)
        chain_running_hash = chained.event_hash
    return {
        "schema_version": SCHEMA_VERSION,
        "spec": "Attestplane restricted-JCS canonicalization, ADR-0002",
        "generated_with": "sdk/python @ attestplane v0.0.1",
        "final_chain_head_hex": chain_running_hash.hex(),
        "entries": entries,
    }


def head_record_from(chained: Any) -> ChainHead:
    return ChainHead(seq=chained.seq, event_hash=chained.event_hash)


if __name__ == "__main__":
    print(json.dumps(generate(), indent=2, sort_keys=True, ensure_ascii=False))
