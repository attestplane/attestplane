# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for :mod:`attestplane.intoto`."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime

import pytest

from attestplane.hashchain import chain_extend, genesis_head
from attestplane.intoto import (
    DSSE_PAYLOAD_TYPE,
    PREDICATE_TYPE_V1,
    STATEMENT_TYPE,
    IntotoError,
    canonical_json_bytes,
    dsse_envelope_to_statement,
    proof_bundle_to_in_toto_statement,
    statement_to_dsse_envelope,
)
from attestplane.proof_bundle import (
    FrameworkMapping,
    ProofBundleBuilder,
    bundle_to_dsse_envelope,
    bundle_to_in_toto_statement,
)
from attestplane.types import ChainHead, EventDraft


def _build_bundle(n: int = 2) -> dict:
    builder = ProofBundleBuilder(chain_id="test-chain", producer_runtime="test")
    head = genesis_head()
    ts = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    events = []
    for i in range(n):
        draft = EventDraft(event_type="eval_event", actor=f"a{i}", payload={"i": i})
        ev = chain_extend(head, draft, now=ts, event_id=f"00000000-0000-7000-8000-{i:012d}")
        events.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    builder.extend(events)
    return builder.build()


def test_statement_has_correct_type() -> None:
    statement = proof_bundle_to_in_toto_statement(_build_bundle())
    assert statement["_type"] == STATEMENT_TYPE
    assert statement["predicateType"] == PREDICATE_TYPE_V1


def test_statement_subject_references_chain_head() -> None:
    bundle = _build_bundle(3)
    statement = proof_bundle_to_in_toto_statement(bundle)

    subjects = statement["subject"]
    assert len(subjects) == 1
    assert subjects[0]["name"] == bundle["chain_metadata"]["chain_id"]
    assert subjects[0]["digest"]["sha256"] == bundle["chain_metadata"]["head_hash_hex"]


def test_statement_predicate_carries_full_bundle_data() -> None:
    bundle = _build_bundle(2)
    statement = proof_bundle_to_in_toto_statement(bundle)
    predicate = statement["predicate"]

    assert predicate["chain_metadata"] == bundle["chain_metadata"]
    assert predicate["events"] == bundle["events"]
    assert predicate["verification_report"] == bundle["verification_report"]
    assert predicate["forbidden_fields"] == bundle["forbidden_fields"]


def test_statement_with_framework_mappings() -> None:
    builder = ProofBundleBuilder(chain_id="fm", producer_runtime="test")
    head = genesis_head()
    ts = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    ev = chain_extend(
        head, EventDraft(event_type="eval_event", actor="x"), now=ts, event_id="00000000-0000-7000-8000-000000000000"
    )
    builder.extend([ev])
    builder.add_framework_mapping(
        FrameworkMapping(
            obligation_id="eu_ai_act.art12.3c.matched_input_data",
            evidence_event_indexes=(0,),
            implementation_status_at_bundle_time="field_supported",
        )
    )
    bundle = builder.build()

    statement = proof_bundle_to_in_toto_statement(bundle)
    assert len(statement["predicate"]["framework_mappings"]) == 1


def test_statement_rejects_non_dict_bundle() -> None:
    with pytest.raises(IntotoError, match="must be a dict"):
        proof_bundle_to_in_toto_statement("not a dict")  # type: ignore[arg-type]


def test_statement_rejects_missing_chain_metadata() -> None:
    with pytest.raises(IntotoError, match="chain_metadata"):
        proof_bundle_to_in_toto_statement({"chain_metadata": "not a dict"})


def test_statement_rejects_missing_head_hash() -> None:
    with pytest.raises(IntotoError, match="head_hash_hex"):
        proof_bundle_to_in_toto_statement(
            {
                "chain_metadata": {"chain_id": "x"}  # missing head_hash_hex
            }
        )


def test_dsse_envelope_round_trips() -> None:
    bundle = _build_bundle(2)
    statement = proof_bundle_to_in_toto_statement(bundle)
    envelope = statement_to_dsse_envelope(statement)

    assert envelope["payloadType"] == DSSE_PAYLOAD_TYPE
    assert envelope["signatures"] == []

    # Decode payload and recover the statement byte-for-byte.
    decoded = base64.standard_b64decode(envelope["payload"])
    recovered = json.loads(decoded)
    assert recovered == statement


def test_dsse_envelope_with_signatures() -> None:
    bundle = _build_bundle()
    statement = proof_bundle_to_in_toto_statement(bundle)
    sigs = [{"keyid": "test-key", "sig": "AABB"}]
    envelope = statement_to_dsse_envelope(statement, signatures=sigs)
    assert envelope["signatures"] == sigs


def test_dsse_envelope_to_statement_inverse() -> None:
    bundle = _build_bundle(2)
    statement = proof_bundle_to_in_toto_statement(bundle)
    envelope = statement_to_dsse_envelope(statement)
    recovered = dsse_envelope_to_statement(envelope)
    assert recovered == statement


def test_dsse_envelope_rejects_wrong_payload_type() -> None:
    with pytest.raises(IntotoError, match="payloadType"):
        dsse_envelope_to_statement(
            {
                "payloadType": "application/wrong",
                "payload": "AA==",
                "signatures": [],
            }
        )


def test_dsse_envelope_rejects_invalid_base64() -> None:
    with pytest.raises(IntotoError, match="base64"):
        dsse_envelope_to_statement(
            {
                "payloadType": DSSE_PAYLOAD_TYPE,
                "payload": "***not base64***",
                "signatures": [],
            }
        )


def test_dsse_envelope_rejects_non_object_payload() -> None:
    payload = base64.standard_b64encode(b'"not an object"').decode("ascii")
    with pytest.raises(IntotoError, match="object"):
        dsse_envelope_to_statement(
            {
                "payloadType": DSSE_PAYLOAD_TYPE,
                "payload": payload,
                "signatures": [],
            }
        )


def test_dsse_envelope_rejects_non_dict_envelope() -> None:
    """dsse_envelope_to_statement rejects a non-dict input."""
    with pytest.raises(IntotoError, match="must be a dict"):
        dsse_envelope_to_statement("not a dict")  # type: ignore[arg-type]


def test_dsse_envelope_rejects_non_string_payload() -> None:
    """dsse_envelope_to_statement rejects envelope with non-string payload."""
    with pytest.raises(IntotoError, match="base64 string"):
        dsse_envelope_to_statement(
            {
                "payloadType": DSSE_PAYLOAD_TYPE,
                "payload": 12345,
                "signatures": [],
            }
        )


def test_dsse_envelope_rejects_malformed_json_payload() -> None:
    """dsse_envelope_to_statement rejects envelope whose payload is not valid JSON."""
    payload = base64.standard_b64encode(b"not valid json").decode("ascii")
    with pytest.raises(IntotoError, match="not valid JSON"):
        dsse_envelope_to_statement(
            {
                "payloadType": DSSE_PAYLOAD_TYPE,
                "payload": payload,
                "signatures": [],
            }
        )


def test_canonical_json_is_deterministic() -> None:
    a = canonical_json_bytes({"b": 1, "a": 2})
    b = canonical_json_bytes({"a": 2, "b": 1})
    assert a == b
    assert a == b'{"a":2,"b":1}'


def test_proof_bundle_convenience_helpers_round_trip() -> None:
    bundle = _build_bundle(2)
    statement = bundle_to_in_toto_statement(bundle)
    envelope = bundle_to_dsse_envelope(bundle)
    assert dsse_envelope_to_statement(envelope) == statement


def test_predicate_type_url_is_correct() -> None:
    """Lock the predicateType URL — changing requires a v2 ADR."""
    assert PREDICATE_TYPE_V1 == "https://attestplane.io/v1/agent-runtime-event"


def test_dsse_payload_type_is_in_toto_canonical() -> None:
    """Lock payloadType to the in-toto canonical media type."""
    assert DSSE_PAYLOAD_TYPE == "application/vnd.in-toto+json"


def test_statement_type_matches_in_toto_v1() -> None:
    """Lock _type to the in-toto Statement v1 URL."""
    assert STATEMENT_TYPE == "https://in-toto.io/Statement/v1"
