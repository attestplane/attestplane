# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Frozen signature_vectors.json replay test (T7 acceptance gate).

Each vector is run through the public verifier API and must produce
the expected status. The same JSON file is consumed by the TS T6
implementation; cross-language drift fails CI on either side.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

pytest.importorskip("cryptography")

from attestplane.canonical import canonicalize
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.proof_bundle import deserialize_signature_record
from attestplane.signing import (
    SignatureStatus,
    TrustRootEntry,
    TrustRoots,
    verify_chain_with_signatures,
)
from attestplane.signing.signer import _build_segment_head_payload
from attestplane.types import ChainHead, EventDraft

_VECTORS_PATH = Path(__file__).resolve().parents[1] / "conformance" / "signature_vectors.json"


def _load_vectors() -> dict:
    return json.loads(_VECTORS_PATH.read_text(encoding="utf-8"))


def _rebuild_chain() -> list:
    """Reconstruct the shared 5-event chain referenced by every vector."""
    NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    chain = []
    head = genesis_head()
    for i in range(5):
        ev = chain_extend(
            head,
            EventDraft(event_type="eval_event", actor=f"a{i}", payload={"i": i}),
            now=NOW,
            event_id=f"00000000-0000-7000-8000-{i:012d}",
        )
        chain.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    return chain


def _trust_roots_from_vector(vec_entry: dict) -> TrustRoots:
    entries = []
    for tr in vec_entry["trust_roots"]:
        entries.append(
            TrustRootEntry(
                key_id=tr["key_id"],
                public_key_der=base64.standard_b64decode(tr["public_key_der_b64"]),
                valid_from=datetime.fromisoformat(tr["valid_from"].replace("Z", "+00:00")),
                valid_until=datetime.fromisoformat(tr["valid_until"].replace("Z", "+00:00")),
                provider_id=None,
                label=None,
            )
        )
    return TrustRoots(version=1, entries=tuple(entries))


def test_vectors_file_loads() -> None:
    vectors = _load_vectors()
    assert vectors["$schema_version"] == 1
    assert len(vectors["vectors"]) == 5


def test_shared_chain_event_hashes_match_rebuilt() -> None:
    """The frozen chain is reproducible from the chain_extend recipe."""
    vectors = _load_vectors()
    rebuilt = _rebuild_chain()
    for serialised, ev in zip(vectors["shared_chain"]["events"], rebuilt, strict=True):
        assert serialised["seq"] == ev.seq
        assert serialised["event_hash_hex"] == ev.event_hash.hex()


def test_segment_head_payload_recipe_locked() -> None:
    """Vector 1's canonical_payload_b64 reconstructs from the locked recipe."""
    vectors = _load_vectors()
    chain = _rebuild_chain()
    vec = vectors["vectors"][0]
    assert vec["name"] == "segment_head_signed_seed00"
    expected = _build_segment_head_payload(
        "vec-1",
        ChainHead(seq=4, event_hash=chain[4].event_hash),
    )
    assert expected == base64.standard_b64decode(vec["canonical_payload_b64"])


def test_per_event_payload_equals_canonicalize() -> None:
    """Vector 2's payload equals canonicalize(AuditEvent) — no new recipe."""
    vectors = _load_vectors()
    chain = _rebuild_chain()
    vec = vectors["vectors"][1]
    assert vec["name"] == "per_event_signed_seed01"
    expected = canonicalize(chain[2].event)
    assert expected == base64.standard_b64decode(vec["canonical_payload_b64"])


# --- Replay each vector through the verifier ---


@pytest.mark.parametrize("vector_index", range(5))
def test_vector_verifier_status(vector_index: int) -> None:
    vectors = _load_vectors()
    vec = vectors["vectors"][vector_index]
    chain = _rebuild_chain()
    NOW = datetime.fromisoformat(vectors["frozen_at"].replace("Z", "+00:00"))

    # Reconstruct SignatureRecord list.
    if "records" in vec:
        records = [deserialize_signature_record(r) for r in vec["records"]]
    else:
        records = [deserialize_signature_record(vec["record"])]

    trust_roots = _trust_roots_from_vector(vec)
    chain_id = vec["input"]["chain_id"]

    status, results, signed_count, _first_bad = verify_chain_with_signatures(
        chain,
        records,
        chain_id=chain_id,
        trust_roots=trust_roots,
        verification_time=NOW,
    )

    expected: SignatureStatus = vec["expected_verifier_status"]
    assert status == expected, (
        f"vector {vec['name']!r}: expected {expected!r}, got {status!r}; reasons={[r.reason for r in results]}"
    )


def test_v1_signed_segment_count_covers_full_segment() -> None:
    """Vector 1 segment-head at seq=4 covers seqs {0..4}."""
    vectors = _load_vectors()
    vec = vectors["vectors"][0]
    chain = _rebuild_chain()
    NOW = datetime.fromisoformat(vectors["frozen_at"].replace("Z", "+00:00"))
    records = [deserialize_signature_record(vec["record"])]
    trust_roots = _trust_roots_from_vector(vec)
    _, _, signed_count, _ = verify_chain_with_signatures(
        chain,
        records,
        chain_id=vec["input"]["chain_id"],
        trust_roots=trust_roots,
        verification_time=NOW,
    )
    assert signed_count == 5


def test_v2_per_event_signed_segment_count_is_one() -> None:
    """Vector 2 per-event at seq=2 covers only seq=2."""
    vectors = _load_vectors()
    vec = vectors["vectors"][1]
    chain = _rebuild_chain()
    NOW = datetime.fromisoformat(vectors["frozen_at"].replace("Z", "+00:00"))
    records = [deserialize_signature_record(vec["record"])]
    trust_roots = _trust_roots_from_vector(vec)
    _, _, signed_count, _ = verify_chain_with_signatures(
        chain,
        records,
        chain_id=vec["input"]["chain_id"],
        trust_roots=trust_roots,
        verification_time=NOW,
    )
    assert signed_count == 1


def test_v3_multi_signer_two_records_one_seq() -> None:
    """Vector 3 has 2 SignatureRecords on seq=4; both valid; count is still 5 (transitivity)."""
    vectors = _load_vectors()
    vec = vectors["vectors"][2]
    chain = _rebuild_chain()
    NOW = datetime.fromisoformat(vectors["frozen_at"].replace("Z", "+00:00"))
    records = [deserialize_signature_record(r) for r in vec["records"]]
    assert len(records) == 2
    # Same payload, different keys, different signatures.
    assert records[0].signed_payload == records[1].signed_payload
    assert records[0].key_id != records[1].key_id
    assert records[0].signature != records[1].signature
    trust_roots = _trust_roots_from_vector(vec)
    status, results, signed_count, _ = verify_chain_with_signatures(
        chain,
        records,
        chain_id="vec-3",
        trust_roots=trust_roots,
        verification_time=NOW,
    )
    assert status == "valid"
    assert all(r.status == "valid" for r in results)
    assert signed_count == 5


def test_v4_unknown_key_count_zero() -> None:
    vectors = _load_vectors()
    vec = vectors["vectors"][3]
    chain = _rebuild_chain()
    NOW = datetime.fromisoformat(vectors["frozen_at"].replace("Z", "+00:00"))
    records = [deserialize_signature_record(vec["record"])]
    trust_roots = _trust_roots_from_vector(vec)
    status, _, signed_count, _ = verify_chain_with_signatures(
        chain,
        records,
        chain_id="vec-4",
        trust_roots=trust_roots,
        verification_time=NOW,
    )
    assert status == "unknown_key"
    assert signed_count == 0


def test_v5_tampered_status_invalid_with_ed25519_reason() -> None:
    vectors = _load_vectors()
    vec = vectors["vectors"][4]
    chain = _rebuild_chain()
    NOW = datetime.fromisoformat(vectors["frozen_at"].replace("Z", "+00:00"))
    records = [deserialize_signature_record(vec["record"])]
    trust_roots = _trust_roots_from_vector(vec)
    status, results, signed_count, first_bad = verify_chain_with_signatures(
        chain,
        records,
        chain_id="vec-5",
        trust_roots=trust_roots,
        verification_time=NOW,
    )
    assert status == "invalid"
    assert first_bad == 0
    assert "Ed25519" in (results[0].reason or "")
    assert signed_count == 0


def test_key_id_format_locked_for_all_vectors() -> None:
    """All vectors must use the 32-hex-char key_id format."""
    vectors = _load_vectors()
    import re

    pattern = re.compile(r"^[0-9a-f]{32}$")
    for vec in vectors["vectors"]:
        records = vec["records"] if "records" in vec else [vec["record"]]
        for r in records:
            assert pattern.match(r["key_id"]), f"{vec['name']}: bad key_id {r['key_id']}"


def test_signature_format_locked_for_all_vectors() -> None:
    """All signatures must be 64 bytes (Ed25519) = 128 hex chars."""
    vectors = _load_vectors()
    for vec in vectors["vectors"]:
        records = vec["records"] if "records" in vec else [vec["record"]]
        for r in records:
            assert len(r["signature_hex"]) == 128, f"{vec['name']}: wrong sig length"
            assert all(c in "0123456789abcdef" for c in r["signature_hex"])
