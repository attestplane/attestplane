# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Replay frozen `anchor_vectors.json` through the verifier.

The vectors were produced once by an in-tree TestTSAAuthority instance
and now live as a frozen artifact. Each replay re-parses the
TimeStampResp DER, re-verifies the RSA signature, re-checks the cert
chain to the embedded root, and asserts the verifier reports
cert_status=VALID.

If this test fails the verifier or the rfc3161 module has drifted in a
way that admits a previously-valid anchor as invalid (or vice versa).
Block release immediately.
"""

from __future__ import annotations

import json
from base64 import b64decode
from datetime import UTC, datetime
from pathlib import Path

import pytest

pytest.importorskip("cryptography")
pytest.importorskip("asn1crypto")

from attestplane.anchoring import (
    ANCHOR_SCHEMA_VERSION,
    AnchorRecord,
    verify_chain_with_anchors,
)
from attestplane.anchoring.rfc3161 import (
    parse_timestamp_response,
    verify_timestamp_token,
)
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.types import ChainHead, EventDraft

_VECTORS_PATH = Path(__file__).parent.parent / "conformance" / "anchor_vectors.json"


def _load() -> dict:
    return json.loads(_VECTORS_PATH.read_text(encoding="utf-8"))


def test_anchor_vectors_file_exists_and_loads() -> None:
    vectors = _load()
    assert vectors["$schema_version"] == 1
    assert len(vectors["entries"]) >= 3
    assert vectors["test_tsa_root_cert_b64"]


@pytest.mark.parametrize("vector_index", range(3))
def test_anchor_vector_round_trips_through_low_level_verifier(vector_index: int) -> None:
    vectors = _load()
    entry = vectors["entries"][vector_index]
    root_der = b64decode(vectors["test_tsa_root_cert_b64"])
    token_der = b64decode(entry["tsa_token_b64"])
    expected_digest = bytes.fromhex(entry["anchored_event_hash_hex"])
    verification_time = datetime.fromisoformat(vectors["verification_time"])
    if verification_time.tzinfo is None:
        verification_time = verification_time.replace(tzinfo=UTC)

    parsed = parse_timestamp_response(token_der)
    assert parsed.message_imprint == expected_digest

    # Must not raise.
    verify_timestamp_token(
        parsed,
        expected_digest=expected_digest,
        trust_roots_der=[root_der],
        verification_time=verification_time,
    )


@pytest.mark.parametrize("vector_index", range(3))
def test_anchor_vector_replays_through_verify_chain_with_anchors(vector_index: int) -> None:
    vectors = _load()
    entry = vectors["entries"][vector_index]
    root_der = b64decode(vectors["test_tsa_root_cert_b64"])
    expected_digest = bytes.fromhex(entry["anchored_event_hash_hex"])

    # Build a synthetic chain that has an event with `expected_digest`
    # at position `anchored_seq`.
    anchored_seq = entry["anchored_seq"]
    chain = []
    head = genesis_head()
    for i in range(anchored_seq + 1):
        # For positions below the target, use any draft.
        # For the target position, we need event_hash == expected_digest;
        # that's not generally constructible without controlling timestamps
        # and event_ids. Instead, we replace the head_event_hash via a
        # constructed ChainedEvent — but that breaks chain integrity for
        # OTHER positions.
        #
        # The simpler approach: skip the chain-integrity dimension here
        # and call verify_chain_with_anchors on a chain that consists ONLY
        # of a single hand-built ChainedEvent whose seq matches and whose
        # event_hash matches expected_digest. That event won't actually
        # chain-verify, but we want the anchor verification path.
        pass

    # Construct a one-event "chain" whose only ChainedEvent matches the
    # anchor's expected_digest at the right seq. We then check that
    # verify_chain_with_anchors reports the anchor as VALID even when the
    # underlying chain fails verification (the two outcomes are
    # independent).
    if anchored_seq == 0:
        # Build a normal one-event chain and overwrite its event_hash.
        draft = EventDraft(event_type="eval_event", actor="x", payload={})
        ts = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
        ev = chain_extend(
            head, draft, now=ts,
            event_id="00000000-0000-7000-8000-000000000000",
        )
        from dataclasses import replace
        ev = replace(ev, event_hash=expected_digest)
        chain = [ev]
    else:
        # For non-zero seq we need a chain of length seq+1. The simpler
        # path: also use chain_extend to construct events at each
        # position, then replace just the target's event_hash. Chain
        # verification will fail because the prev_hash linkage breaks,
        # but the anchor path is what we care about here.
        from dataclasses import replace
        ts = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
        for i in range(anchored_seq + 1):
            draft = EventDraft(event_type="eval_event", actor=f"x{i}", payload={"i": i})
            ev = chain_extend(
                head, draft, now=ts,
                event_id=f"00000000-0000-7000-8000-{i:012d}",
            )
            chain.append(ev)
            head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
        chain[anchored_seq] = replace(chain[anchored_seq], event_hash=expected_digest)

    anchor = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=anchored_seq,
        anchored_event_hash=expected_digest,
        tsa_provider_id=entry["tsa_provider_id"],
        tsa_token=b64decode(entry["tsa_token_b64"]),
        tsa_cert_chain=tuple(b64decode(c) for c in entry["tsa_cert_chain_b64"]),
        ocsp_responses=tuple(b64decode(o) for o in entry["ocsp_responses_b64"]),
        issued_at_claimed=datetime.fromisoformat(entry["issued_at_claimed"]).replace(tzinfo=UTC)
            if datetime.fromisoformat(entry["issued_at_claimed"]).tzinfo is None
            else datetime.fromisoformat(entry["issued_at_claimed"]),
    )
    verification_time = datetime.fromisoformat(vectors["verification_time"])
    if verification_time.tzinfo is None:
        verification_time = verification_time.replace(tzinfo=UTC)

    result = verify_chain_with_anchors(
        chain, [anchor],
        trust_roots_der=[root_der],
        verification_time=verification_time,
    )

    # The anchor itself MUST verify as VALID.
    assert result.anchor_results[0].cert_status == "VALID"
    assert result.anchor_results[0].valid is True


def test_anchor_vectors_have_real_tsa_token_bytes() -> None:
    """Smoke check: the TimeStampResp blobs are nontrivial size (real CMS)."""
    vectors = _load()
    for entry in vectors["entries"]:
        token = b64decode(entry["tsa_token_b64"])
        assert len(token) > 500, f"{entry['name']}: token suspiciously small"


def test_anchor_vectors_cert_chain_has_leaf_and_root() -> None:
    vectors = _load()
    for entry in vectors["entries"]:
        assert len(entry["tsa_cert_chain_b64"]) == 2
