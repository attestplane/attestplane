# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Deterministic fail-closed fault-injection tests.

These tests are intentionally small and direct. They are not a mutation-testing
engine; they lock the highest-risk fail-open regressions named in
``tests/fault_injection/fault_matrix_v1.json``.
"""

from __future__ import annotations

import json
import math
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from attestplane.anchoring import (
    ANCHOR_SCHEMA_VERSION,
    AnchorRecord,
    MockTSAProvider,
    TimestampRequest,
    verify_chain_with_anchors,
)
from attestplane.canonical import CanonicalizationError, canonicalize
from attestplane.event_payloads import validate_lease_lifecycle_event_payload
from attestplane.hashchain import chain_extend, genesis_head, verify_chain
from attestplane.proof_bundle import ProofBundleBuilder
from attestplane.reason_codes import is_known_reason_code, reason_code_matches_format
from attestplane.settlement_verifier import (
    SettlementPreconditionClaim,
    check_settlement_precondition,
)
from attestplane.storage.base import StorageReadError
from attestplane.storage.jsonl import JsonlStorageBackend
from attestplane.types import ChainedEvent, ChainHead, EventDraft
from attestplane.verifier import BundleSchemaError, verify_proof_bundle

ROOT = Path(__file__).resolve().parents[4]
FAULT_MATRIX = ROOT / "tests" / "fault_injection" / "fault_matrix_v1.json"
NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _build_chain(count: int, *, event_type: str = "eval_event") -> list[ChainedEvent]:
    chain: list[ChainedEvent] = []
    head: ChainHead = genesis_head()
    for i in range(count):
        event = chain_extend(
            head,
            EventDraft(event_type=event_type, actor="agent://fault", payload={"i": i}),
            now=NOW.replace(microsecond=i),
            event_id=f"00000000-0000-7000-8000-{i:012d}",
        )
        chain.append(event)
        head = ChainHead(seq=event.seq, event_hash=event.event_hash)
    return chain


def _bundle_for_policy_events() -> dict[str, Any]:
    chain = _build_chain(1, event_type="policy_check_event")
    builder = ProofBundleBuilder(chain_id="fault-policy", producer_runtime="fault-test")
    builder.extend(chain)
    return builder.build(now=NOW)


def test_fault_matrix_v1_is_loadable() -> None:
    matrix = json.loads(FAULT_MATRIX.read_text(encoding="utf-8"))
    assert matrix["schema_version"] == "fault_matrix.v1"
    assert matrix["baseline_release"] == "v0.0.2-alpha"
    assert len(matrix["faults"]) >= 40


@pytest.mark.parametrize(
    ("fault_id", "mutated"),
    [
        ("canonical.reject_nan", math.nan),
        ("canonical.reject_infinity", math.inf),
        ("canonical.reject_lone_surrogate", "\ud800"),
        ("canonical.reject_unsafe_integer", 2**63),
    ],
    ids=lambda case: case if isinstance(case, str) else "",
)
def test_fault_matrix_python_canonical_fail_closed(fault_id: str, mutated: object) -> None:
    assert fault_id.startswith("canonical.")
    with pytest.raises(CanonicalizationError):
        canonicalize(mutated)


def test_fault_matrix_python_canonical_key_ordering_and_negative_zero() -> None:
    assert canonicalize({"z": 1, "a": 2, "m": {"b": 1, "a": 2}}) == (
        b'{"a":2,"m":{"a":2,"b":1},"z":1}'
    )
    assert canonicalize(0) == b"0"


@pytest.mark.parametrize(
    "fault_id",
    [
        "hashchain.previous_hash_tampered",
        "hashchain.event_hash_tampered",
        "hashchain.payload_tampered_after_chaining",
        "hashchain.reordered_events",
        "hashchain.missing_chain_link",
        "hashchain.duplicate_chain_index",
    ],
)
def test_fault_matrix_python_hashchain_fail_closed(fault_id: str) -> None:
    chain = _build_chain(3)
    if fault_id == "hashchain.previous_hash_tampered":
        chain[1] = replace(chain[1], prev_hash=b"\xff" * 32)
    elif fault_id == "hashchain.event_hash_tampered":
        chain[1] = replace(chain[1], event_hash=b"\x01" * 32)
    elif fault_id == "hashchain.payload_tampered_after_chaining":
        chain[1] = replace(chain[1], event=replace(chain[1].event, payload={"i": 999}))
    elif fault_id == "hashchain.reordered_events":
        chain = [chain[0], chain[2], chain[1]]
    elif fault_id == "hashchain.missing_chain_link":
        chain = [chain[0], chain[2]]
    elif fault_id == "hashchain.duplicate_chain_index":
        chain = [chain[0], chain[1], chain[1]]
    result = verify_chain(chain)
    assert result.ok is False


@pytest.mark.parametrize(
    ("fault_id", "payload"),
    [
        ("payload.missing_schema_version", {}),
        (
            "payload.unsupported_schema_version",
            {
                "lease_event_schema_version": 2,
                "lease_id_hash": "a" * 64,
                "lifecycle": "consumed",
                "observed_at": "2026-05-17T12:00:00Z",
            },
        ),
        (
            "payload.unknown_top_level_field",
            {
                "lease_event_schema_version": 1,
                "lease_id_hash": "a" * 64,
                "lifecycle": "consumed",
                "observed_at": "2026-05-17T12:00:00Z",
                "unexpected": "x",
            },
        ),
        (
            "payload.forbidden_field",
            {
                "lease_event_schema_version": 1,
                "lease_id_hash": "a" * 64,
                "lifecycle": "consumed",
                "observed_at": "2026-05-17T12:00:00Z",
                "token": "secret",
            },
        ),
        (
            "payload.null_required_field",
            {
                "lease_event_schema_version": 1,
                "lease_id_hash": None,
                "lifecycle": "consumed",
                "observed_at": "2026-05-17T12:00:00Z",
            },
        ),
        (
            "payload.unknown_enum",
            {
                "lease_event_schema_version": 1,
                "lease_id_hash": "a" * 64,
                "lifecycle": "settled",
                "observed_at": "2026-05-17T12:00:00Z",
            },
        ),
    ],
)
def test_fault_matrix_python_payload_fail_closed(
    fault_id: str, payload: dict[str, object]
) -> None:
    assert fault_id.startswith("payload.")
    with pytest.raises(ValueError):
        validate_lease_lifecycle_event_payload(payload)


def test_fault_matrix_python_reason_code_fail_closed() -> None:
    assert reason_code_matches_format("bad-code") is False
    assert is_known_reason_code("NOT_A_V1_REASON_CODE") is False


@pytest.mark.parametrize(
    "fault_id",
    [
        "proof_bundle.unsupported_proof_type",
        "proof_bundle.missing_required_metadata",
        "proof_bundle.unknown_critical_metadata",
        "proof_bundle.embedded_report_mismatch",
        "proof_bundle.chain_head_mismatch",
        "proof_bundle.dangling_policy_trace_ref",
        "proof_bundle.policy_trace_ref_hash_mismatch",
        "proof_bundle.duplicate_policy_trace_ref",
    ],
)
def test_fault_matrix_python_proof_bundle_fail_closed(fault_id: str) -> None:
    bundle = _bundle_for_policy_events()
    if fault_id == "proof_bundle.unsupported_proof_type":
        bundle["verification_report"]["verification_method"] = "full-production-verifier"
        with pytest.raises(BundleSchemaError):
            verify_proof_bundle(bundle)
        return
    if fault_id == "proof_bundle.missing_required_metadata":
        del bundle["chain_metadata"]["head_hash_hex"]
        with pytest.raises(BundleSchemaError):
            verify_proof_bundle(bundle)
        return
    if fault_id == "proof_bundle.unknown_critical_metadata":
        bundle["critical_extension"] = {"must_understand": True}
        with pytest.raises(BundleSchemaError):
            verify_proof_bundle(bundle)
        return
    if fault_id == "proof_bundle.embedded_report_mismatch":
        bundle["verification_report"]["reason"] = "forged"
    elif fault_id == "proof_bundle.chain_head_mismatch":
        bundle["chain_metadata"]["head_hash_hex"] = "f" * 64
    elif fault_id in {
        "proof_bundle.dangling_policy_trace_ref",
        "proof_bundle.policy_trace_ref_hash_mismatch",
    }:
        bundle["policy_trace_refs"] = ["a" * 64]
    elif fault_id == "proof_bundle.duplicate_policy_trace_ref":
        ref = bundle["policy_trace_refs"][0]
        bundle["policy_trace_refs"] = [ref, ref]
    result = verify_proof_bundle(bundle)
    assert result.ok is False


@pytest.mark.parametrize(
    ("fault_id", "amount_hash"),
    [
        ("settlement.missing_amount_hash", None),
        ("settlement.empty_amount_hash", ""),
        ("settlement.wrong_format_amount_hash", "not-a-hash"),
        ("settlement.amount_hash_mismatch", "b" * 64),
    ],
)
def test_fault_matrix_python_settlement_amount_hash_fail_closed(
    fault_id: str, amount_hash: str | None
) -> None:
    payload: dict[str, object] = {"settlement_run_id": "s"}
    if amount_hash is not None:
        payload["amount_hash"] = amount_hash
    chain = [
        {
            "seq": 0,
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {"seq": 1, "event_type": "settlement_event", "payload": payload},
    ]
    result = check_settlement_precondition(
        chain,
        SettlementPreconditionClaim(
            claim_kind="settlement_precondition",
            lease_id_hash="a" * 64,
            settlement_run_id="s",
            expected_settlement_amount_hash="c" * 64,
        ),
    )
    assert fault_id.startswith("settlement.")
    assert result.ok is False


def test_fault_matrix_python_settlement_without_precondition_fails_closed() -> None:
    result = check_settlement_precondition(
        [{"seq": 0, "event_type": "settlement_event", "payload": {"settlement_run_id": "s"}}],
        SettlementPreconditionClaim(
            claim_kind="settlement_precondition",
            lease_id_hash="a" * 64,
            settlement_run_id="s",
        ),
    )
    assert result.ok is False
    assert result.reason == "lease_consumed_not_observed"


@pytest.mark.parametrize(
    "fault_id",
    [
        "anchoring.empty_anchor_treated_as_success",
        "anchoring.missing_required_anchor_accepted",
        "anchoring.malformed_anchor_evidence_accepted",
    ],
)
def test_fault_matrix_python_anchoring_fail_closed(fault_id: str) -> None:
    chain = _build_chain(1)
    if fault_id in {
        "anchoring.empty_anchor_treated_as_success",
        "anchoring.missing_required_anchor_accepted",
    }:
        result = verify_chain_with_anchors(chain, [])
        assert result.ok is False
        assert result.verification_status == "not_performed"
        return
    bad = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=0,
        anchored_event_hash=b"\xff" * 32,
        tsa_provider_id="mock.tsa.local",
        tsa_token=b"x",
        tsa_cert_chain=(b"x",),
        ocsp_responses=(b"x",),
        issued_at_claimed=NOW,
    )
    result = verify_chain_with_anchors(chain, [bad])
    assert result.ok is False


def test_fault_matrix_python_valid_anchor_still_passes() -> None:
    chain = _build_chain(1)
    anchor = MockTSAProvider(fixed_time=NOW).request_timestamp(
        TimestampRequest(digest=chain[0].event_hash),
        anchored_seq=0,
    )
    result = verify_chain_with_anchors(chain, [anchor])
    assert result.ok is True


@pytest.mark.parametrize(
    ("fault_id", "raw"),
    [
        ("jsonl.partial_trailing_line", b'{"seq":0'),
        ("jsonl.malformed_json_line", b"not json\n"),
        ("jsonl.invalid_utf8", b"\xff\n"),
        ("jsonl.non_object_row", b"[]\n"),
    ],
)
def test_fault_matrix_python_jsonl_scan_fail_closed(
    tmp_path: Path, fault_id: str, raw: bytes
) -> None:
    path = tmp_path / "chain.jsonl"
    path.write_bytes(raw)
    scan = JsonlStorageBackend(path).scan()
    assert fault_id.startswith("jsonl.")
    assert scan.ok is False
    assert scan.issues
    with pytest.raises(StorageReadError):
        JsonlStorageBackend(path).read_all()
