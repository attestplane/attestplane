# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coverage tests for attestplane.cli.verify_json — targets all uncovered branches."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from attestplane.canonical import CanonicalizationError
from attestplane.cli.main import main
from attestplane.cli.verify_json import (
    VERIFY_JSON_EXIT_CODE_PINNING_GATE_FAILURE,
    VERIFY_JSON_EXIT_CODE_USAGE_ERROR,
    VERIFY_JSON_EXIT_CODE_VERIFICATION_FAILURE,
    VERIFY_JSON_EXIT_CODE_VERIFIED,
    _anchoring_payload,
    _bundle_anchor_state,
    _bundle_explicit_anchoring_state,
    _bundle_failure_reason,
    _bundle_schema_version,
    _bundle_signer_subject,
    _bundle_taxonomy_version_failure,
    _canonical_path_to_pointer,
    _canonicalization_path,
    _canonicalization_probe,
    _reason_entry,
    _schema_path_from_bundle_error,
    _schema_reason_for_bundle_error,
    _verify_explanations,
    build_verify_json_outcome,
    verify_result_exit_code,
)
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.proof_bundle import ProofBundleBuilder
from attestplane.storage.jsonl import JsonlStorageBackend
from attestplane.types import ChainHead, EventDraft
from attestplane.verify_reason_codes import (
    VERIFY_REASON_ANCHOR_INVALID,
    VERIFY_REASON_CANONICAL_MISMATCH,
    VERIFY_REASON_REQUIRED_FIELD_MISSING,
    VERIFY_REASON_SCHEMA_INVALID,
    VERIFY_REASON_SCHEMA_UNKNOWN,
    VERIFY_REASON_SCHEMA_VERSION_MISSING,
    VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
    VERIFY_REASON_SIGNATURE_INVALID,
    VERIFY_REASON_SIGNATURE_MISSING,
    VERIFY_REASON_STRUCTURE_INVALID,
    verify_reason_code_explanation,
)

ROOT = Path(__file__).resolve().parents[3]


def _seed_bundle(tmp_path: Path, n: int = 2) -> Path:
    chain_path = tmp_path / "chain.jsonl"
    bundle_path = tmp_path / "bundle.json"
    backend = JsonlStorageBackend(chain_path)
    head = genesis_head()
    ts = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    for i in range(n):
        draft = EventDraft(event_type="eval_event", actor=f"agent://{i}", payload={"i": i})
        event = chain_extend(head, draft, now=ts, event_id=f"00000000-0000-7000-8000-{i:012d}")
        backend.append(event)
        head = ChainHead(seq=event.seq, event_hash=event.event_hash)
    backend.close()
    main(["export", str(chain_path), "--out", str(bundle_path)])
    return bundle_path


# ---------------------------------------------------------------------------
# _canonical_path_to_pointer edge cases (lines 86-114)
# ---------------------------------------------------------------------------


def test_canonical_path_not_starting_with_dollar() -> None:
    assert _canonical_path_to_pointer("payload.actor") == "/"


def test_canonical_path_bracket_without_close() -> None:
    # Unclosed bracket: "[" without "]" → break, token flushed
    result = _canonical_path_to_pointer("$.events[0")
    assert result == "/events"


def test_canonical_path_bracket_with_close() -> None:
    assert _canonical_path_to_pointer("$.events[0].field") == "/events/0/field"


def test_canonical_path_empty_parts_filtered() -> None:
    # Leading dot produces empty token between $ and next part
    assert _canonical_path_to_pointer("$.actor") == "/actor"


# ---------------------------------------------------------------------------
# _canonicalization_path (lines 117-125)
# ---------------------------------------------------------------------------


def test_canonicalization_path_no_event_index() -> None:
    exc = CanonicalizationError("$.payload: bad")
    path = _canonicalization_path(exc, event_index=None)
    assert path == "/events/payload"


def test_canonicalization_path_with_event_index() -> None:
    exc = CanonicalizationError("$.payload.artifact_ref: bad")
    path = _canonicalization_path(exc, event_index=3)
    assert path == "/events/3/event/payload/artifact_ref"


def test_canonicalization_path_no_field() -> None:
    exc = CanonicalizationError("some error")
    path = _canonicalization_path(exc, event_index=None)
    assert path == "/events"


def test_canonicalization_path_with_event_index_no_field() -> None:
    exc = CanonicalizationError("some error")
    path = _canonicalization_path(exc, event_index=5)
    assert path == "/events/5/event"


# ---------------------------------------------------------------------------
# _bundle_signer_subject (lines 159-172)
# ---------------------------------------------------------------------------


def test_bundle_signer_subject_no_signatures() -> None:
    assert _bundle_signer_subject({}) == "none"
    assert _bundle_signer_subject({"signatures": []}) == "none"


def test_bundle_signer_subject_non_dict_first() -> None:
    assert _bundle_signer_subject({"signatures": ["not_a_dict"]}) == "unknown"


def test_bundle_signer_subject_key_id() -> None:
    assert _bundle_signer_subject({"signatures": [{"key_id": "my_key"}]}) == "key_id:my_key"


def test_bundle_signer_subject_empty_key_id_fallback_to_hash() -> None:
    bundle = {"signatures": [{"key_id": "", "signed_event_hash_hex": "abc123"}]}
    assert _bundle_signer_subject(bundle) == "subject_hash:abc123"


def test_bundle_signer_subject_no_key_id_signed_hash() -> None:
    bundle = {"signatures": [{"signed_event_hash_hex": "hash_val"}]}
    assert _bundle_signer_subject(bundle) == "subject_hash:hash_val"


def test_bundle_signer_subject_no_usable_fields() -> None:
    assert _bundle_signer_subject({"signatures": [{}]}) == "unknown"


# ---------------------------------------------------------------------------
# _bundle_schema_version (lines 175-182)
# ---------------------------------------------------------------------------


def test_bundle_schema_version_no_chain_metadata() -> None:
    assert _bundle_schema_version({}) == "unknown"


def test_bundle_schema_version_non_dict_chain_metadata() -> None:
    assert _bundle_schema_version({"chain_metadata": "not_dict"}) == "unknown"


def test_bundle_schema_version_missing() -> None:
    assert _bundle_schema_version({"chain_metadata": {}}) == "unknown"


def test_bundle_schema_version_non_int() -> None:
    assert _bundle_schema_version({"chain_metadata": {"schema_version": "v1"}}) == "unknown"


def test_bundle_schema_version_valid() -> None:
    assert _bundle_schema_version({"chain_metadata": {"schema_version": 1}}) == "1"


# ---------------------------------------------------------------------------
# _bundle_explicit_anchoring_state (lines 196-208)
# ---------------------------------------------------------------------------


def test_bundle_explicit_anchoring_state_none_input() -> None:
    assert _bundle_explicit_anchoring_state(None) is None


def test_bundle_explicit_anchoring_state_non_dict() -> None:
    assert _bundle_explicit_anchoring_state("not_a_dict") is None  # type: ignore[arg-type]


def test_bundle_explicit_anchoring_state_no_anchoring() -> None:
    assert _bundle_explicit_anchoring_state({}) is None


def test_bundle_explicit_anchoring_state_non_dict_anchoring() -> None:
    assert _bundle_explicit_anchoring_state({"anchoring": "bad"}) is None


def test_bundle_explicit_anchoring_state_bad_status() -> None:
    assert _bundle_explicit_anchoring_state({"anchoring": {"status": "unknown_status", "quarantined": False}}) is None


def test_bundle_explicit_anchoring_state_non_bool_quarantined() -> None:
    assert _bundle_explicit_anchoring_state({"anchoring": {"status": "anchored", "quarantined": "yes"}}) is None


def test_bundle_explicit_anchoring_state_anchored() -> None:
    assert _bundle_explicit_anchoring_state({"anchoring": {"status": "anchored", "quarantined": False}}) == "anchored"


def test_bundle_explicit_anchoring_state_quarantined() -> None:
    assert (
        _bundle_explicit_anchoring_state({"anchoring": {"status": "quarantined", "quarantined": True}}) == "quarantined"
    )


def test_bundle_explicit_anchoring_state_unanchored() -> None:
    assert (
        _bundle_explicit_anchoring_state({"anchoring": {"status": "unanchored", "quarantined": False}}) == "unanchored"
    )


# ---------------------------------------------------------------------------
# _bundle_anchor_state (lines 185-193)
# ---------------------------------------------------------------------------


def test_bundle_anchor_state_no_chain_metadata() -> None:
    assert _bundle_anchor_state({}) == "unknown"


def test_bundle_anchor_state_non_dict_chain_metadata() -> None:
    assert _bundle_anchor_state({"chain_metadata": "not_dict"}) == "unknown"


def test_bundle_anchor_state_anchor_ref_present() -> None:
    assert _bundle_anchor_state({"chain_metadata": {"anchor_ref": "https://x.com"}}) == "present"


def test_bundle_anchor_state_anchor_ref_empty() -> None:
    assert _bundle_anchor_state({"chain_metadata": {"anchor_ref": ""}}) == "absent"


def test_bundle_anchor_state_explicit_anchored() -> None:
    bundle = {"anchoring": {"status": "anchored", "quarantined": False}}
    assert _bundle_anchor_state(bundle) == "anchored"


def test_bundle_anchor_state_explicit_quarantined() -> None:
    bundle = {"anchoring": {"status": "quarantined", "quarantined": True}}
    assert _bundle_anchor_state(bundle) == "quarantined"


def test_bundle_anchor_state_explicit_unanchored() -> None:
    bundle = {"anchoring": {"status": "unanchored", "quarantined": False}}
    assert _bundle_anchor_state(bundle) == "unanchored"


# ---------------------------------------------------------------------------
# _anchoring_payload (lines 221-242)
# ---------------------------------------------------------------------------


def test_anchoring_payload_pinning_gate_failure() -> None:
    result = _anchoring_payload({}, exit_code=VERIFY_JSON_EXIT_CODE_PINNING_GATE_FAILURE)
    assert result["anchoring"]["status"] == "quarantined"
    assert result["anchoring"]["quarantined"] is True


def test_anchoring_payload_verified_exit_with_anchored_explicit() -> None:
    bundle = {"anchoring": {"status": "anchored", "quarantined": False}}
    result = _anchoring_payload(bundle, exit_code=VERIFY_JSON_EXIT_CODE_VERIFIED)
    assert result["anchoring"]["status"] == "verified"
    assert result["anchoring"]["quarantined"] is False


def test_anchoring_payload_verified_exit_with_quarantined_explicit() -> None:
    bundle = {"anchoring": {"status": "quarantined", "quarantined": True}}
    result = _anchoring_payload(bundle, exit_code=VERIFY_JSON_EXIT_CODE_VERIFICATION_FAILURE)
    assert result["anchoring"]["status"] == "quarantined"
    assert result["anchoring"]["quarantined"] is False


def test_anchoring_payload_unanchored_explicit() -> None:
    bundle = {"anchoring": {"status": "unanchored", "quarantined": False}}
    result = _anchoring_payload(bundle, exit_code=VERIFY_JSON_EXIT_CODE_VERIFIED)
    assert result["anchoring"]["status"] == "absent"


def test_anchoring_payload_no_anchoring_with_anchor_ref() -> None:
    bundle = {"chain_metadata": {"anchor_ref": "https://tsa.example.com/token"}}
    result = _anchoring_payload(bundle, exit_code=VERIFY_JSON_EXIT_CODE_VERIFIED)
    assert result["anchoring"]["status"] == "verified"


def test_anchoring_payload_no_anchoring_no_anchor_ref() -> None:
    result = _anchoring_payload({}, exit_code=VERIFY_JSON_EXIT_CODE_VERIFIED)
    assert result["anchoring"]["status"] == "absent"


def test_anchoring_payload_none_bundle() -> None:
    result = _anchoring_payload(None, exit_code=VERIFY_JSON_EXIT_CODE_VERIFIED)
    assert result["anchoring"]["status"] == "absent"


# ---------------------------------------------------------------------------
# _verify_explanations (lines 255-283)
# ---------------------------------------------------------------------------


class _FakeResult:
    ok: bool = True
    chain_result: Any = None
    agreement: bool = True
    signed_attestation_schema_ok: bool = True
    signed_attestation_schema_reason: str | None = None
    metadata_ok: bool = True
    metadata_reason: str | None = None
    policy_trace_refs_ok: bool = True
    policy_trace_refs_reason: str | None = None
    retention_proofs_ok: bool = True
    retention_proofs_reason: str | None = None
    primary_reason: str | None = None
    secondary_reasons: tuple[str, ...] = ()

    def __init__(self, **kw: Any) -> None:
        for k, v in kw.items():
            setattr(self, k, v)

    class _chain_result:
        ok: bool = True
        first_bad_index: int = -1
        reason: str | None = None


def test_verify_explanations_not_explain_returns_empty() -> None:
    result = _FakeResult()
    assert _verify_explanations(result, explain=False) == []


def test_verify_explanations_none_result_returns_empty() -> None:
    assert _verify_explanations(None, explain=True) == []


def test_verify_explanations_ok_no_bundle() -> None:
    result = _FakeResult(ok=True)
    explanations = _verify_explanations(result, explain=True)
    assert len(explanations) == 1
    assert explanations[0]["primary_reason"] is None
    assert "unknown" in explanations[0]["message"]


def test_verify_explanations_ok_with_bundle() -> None:
    result = _FakeResult(ok=True)
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    explanations = _verify_explanations(result, explain=True, bundle=bundle)
    assert len(explanations) == 1
    assert explanations[0]["primary_reason"] is None
    assert "schema_version=" in explanations[0]["message"]


def test_verify_explanations_fail_with_chain_fail() -> None:
    chain_result = type(
        "cr", (), {"ok": False, "first_bad_index": 0, "reason": "hash mismatch at seq 0"}
    )()
    result = _FakeResult(ok=False, chain_result=chain_result, agreement=True)
    result.chain_result = chain_result
    explanations = _verify_explanations(result, explain=True)
    assert any(e["primary_reason"] == VERIFY_REASON_CANONICAL_MISMATCH for e in explanations)


# ---------------------------------------------------------------------------
# _schema_path_from_bundle_error (lines 286-307)
# ---------------------------------------------------------------------------


def test_schema_path_from_bundle_error_anchoring() -> None:
    assert _schema_path_from_bundle_error("anchoring.status must be string") == "/anchoring"


def test_schema_path_from_bundle_error_chain_metadata_schema_version() -> None:
    assert _schema_path_from_bundle_error("chain_metadata.schema_version=99") == "/chain_metadata/schema_version"


def test_schema_path_from_bundle_error_chain_metadata() -> None:
    assert _schema_path_from_bundle_error("chain_metadata missing required key") == "/chain_metadata"


def test_schema_path_from_bundle_error_verification_report() -> None:
    assert _schema_path_from_bundle_error("verification_report is not an object") == "/verification_report"


def test_schema_path_from_bundle_error_forbidden_fields() -> None:
    assert _schema_path_from_bundle_error("forbidden_fields must not be empty") == "/forbidden_fields"


def test_schema_path_from_bundle_error_events_bracket() -> None:
    assert _schema_path_from_bundle_error("events[0] is malformed") == "/events"


def test_schema_path_from_bundle_error_events_must() -> None:
    assert _schema_path_from_bundle_error("events must be a list") == "/events"


def test_schema_path_from_bundle_error_bundle_version() -> None:
    assert _schema_path_from_bundle_error("bundle_version must be 1") == "/bundle_version"


def test_schema_path_from_bundle_error_signatures() -> None:
    assert _schema_path_from_bundle_error("signatures must be a list") == "/signatures"


def test_schema_path_from_bundle_error_policy_trace_refs() -> None:
    assert _schema_path_from_bundle_error("policy_trace_refs missing") == "/policy_trace_refs"


def test_schema_path_from_bundle_error_retention_proofs() -> None:
    assert _schema_path_from_bundle_error("retention_proofs must be a list") == "/retention_proofs"


def test_schema_path_from_bundle_error_unknown() -> None:
    assert _schema_path_from_bundle_error("some unknown error") == "/"


# ---------------------------------------------------------------------------
# _schema_reason_for_bundle_error (lines 310-316)
# ---------------------------------------------------------------------------


def test_schema_reason_for_bundle_error_anchoring_path() -> None:
    from attestplane.verifier import BundleSchemaError

    exc = BundleSchemaError("anchoring.status must be string")
    code, path = _schema_reason_for_bundle_error(exc)
    assert path == "/anchoring"


def test_schema_reason_for_bundle_error_no_path_rewrite() -> None:
    from attestplane.verifier import BundleSchemaError

    exc = BundleSchemaError("some unknown error")
    code, path = _schema_reason_for_bundle_error(exc)
    assert path == "/"


# ---------------------------------------------------------------------------
# _bundle_taxonomy_version_failure (lines 319-359)
# ---------------------------------------------------------------------------


def test_bundle_taxonomy_version_failure_none_required() -> None:
    assert _bundle_taxonomy_version_failure({}, None) is None


def test_bundle_taxonomy_version_failure_chain_metadata_not_dict() -> None:
    result = _bundle_taxonomy_version_failure({"chain_metadata": "bad"}, required_taxonomy_version=1)
    assert result is not None
    code, path, message = result
    assert code == VERIFY_REASON_SCHEMA_INVALID
    assert path == "/chain_metadata"


def test_bundle_taxonomy_version_failure_missing_field() -> None:
    bundle: dict[str, Any] = {"chain_metadata": {}}
    result = _bundle_taxonomy_version_failure(bundle, required_taxonomy_version=1)
    assert result is not None
    code, path, message = result
    assert code == VERIFY_REASON_SCHEMA_VERSION_MISSING
    assert path == "/chain_metadata/evidence_taxonomy_version"


def test_bundle_taxonomy_version_failure_non_integer() -> None:
    bundle = {"chain_metadata": {"evidence_taxonomy_version": "v1"}}
    result = _bundle_taxonomy_version_failure(bundle, required_taxonomy_version=1)
    assert result is not None
    code, path, message = result
    assert code == VERIFY_REASON_SCHEMA_INVALID


def test_bundle_taxonomy_version_failure_mismatch() -> None:
    bundle = {"chain_metadata": {"evidence_taxonomy_version": 2}}
    result = _bundle_taxonomy_version_failure(bundle, required_taxonomy_version=1)
    assert result is not None
    code, path, message = result
    assert code == VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED


def test_bundle_taxonomy_version_failure_match() -> None:
    bundle = {"chain_metadata": {"evidence_taxonomy_version": 1}}
    assert _bundle_taxonomy_version_failure(bundle, required_taxonomy_version=1) is None


# ---------------------------------------------------------------------------
# _canonicalization_probe (lines 444-457)
# ---------------------------------------------------------------------------


def test_canonicalization_probe_no_events() -> None:
    idx, exc = _canonicalization_probe({})
    assert idx is None and exc is None


def test_canonicalization_probe_non_list_events() -> None:
    idx, exc = _canonicalization_probe({"events": "not_a_list"})
    assert idx is None and exc is None


def test_canonicalization_probe_malformed_event_skips() -> None:
    # Non-deserializable event → exception caught → returns None, None
    idx, exc = _canonicalization_probe({"events": [{"bad": "event"}]})
    assert idx is None and exc is None


def test_canonicalization_probe_valid_events_no_error(tmp_path: Path) -> None:
    bundle_path = _seed_bundle(tmp_path, n=1)
    bundle = json.loads(bundle_path.read_text())
    idx, exc = _canonicalization_probe(bundle)
    assert idx is None and exc is None


def test_canonicalization_probe_detects_error() -> None:
    # Use the canonicalization-edge fixture which has NFC-normalization issue
    fixture = ROOT / "fixtures" / "reject" / "canonicalization-edge.json"
    bundle = json.loads(fixture.read_text(encoding="utf-8"))
    idx, exc = _canonicalization_probe(bundle)
    assert exc is not None


# ---------------------------------------------------------------------------
# _bundle_failure_reason — all branches (lines 460-587)
# ---------------------------------------------------------------------------


def test_bundle_failure_reason_none_result() -> None:
    assert _bundle_failure_reason(None, explain=False) == []


def _make_fake_result(**kw: Any) -> Any:
    chain_result = type(
        "cr",
        (),
        {"ok": True, "first_bad_index": -1, "reason": None},
    )()
    base = dict(
        ok=False,
        chain_result=chain_result,
        agreement=True,
        signed_attestation_schema_ok=True,
        signed_attestation_schema_reason=None,
        metadata_ok=True,
        metadata_reason=None,
        policy_trace_refs_ok=True,
        policy_trace_refs_reason=None,
        retention_proofs_ok=True,
        retention_proofs_reason=None,
        primary_reason=None,
    )
    base.update(kw)
    return type("Result", (), base)()


def test_bundle_failure_reason_chain_result_failure() -> None:
    chain_result = type("cr", (), {"ok": False, "first_bad_index": 0, "reason": "hash mismatch"})()
    result = _make_fake_result(chain_result=chain_result)
    reasons = _bundle_failure_reason(result, explain=False)
    assert any(r["code"] == VERIFY_REASON_CANONICAL_MISMATCH for r in reasons)


def test_bundle_failure_reason_agreement_failure() -> None:
    result = _make_fake_result(agreement=False)
    reasons = _bundle_failure_reason(result, explain=False)
    assert any(r["code"] == VERIFY_REASON_CANONICAL_MISMATCH for r in reasons)


def test_bundle_failure_reason_signed_attestation_events_path() -> None:
    result = _make_fake_result(
        signed_attestation_schema_ok=False,
        signed_attestation_schema_reason="events must contain at least one event",
        primary_reason=VERIFY_REASON_REQUIRED_FIELD_MISSING,
    )
    reasons = _bundle_failure_reason(result, explain=False)
    sig_reasons = [r for r in reasons if r["code"] == VERIFY_REASON_REQUIRED_FIELD_MISSING]
    assert sig_reasons
    assert sig_reasons[0]["path"] == "/events"


def test_bundle_failure_reason_signed_attestation_missing() -> None:
    result = _make_fake_result(
        signed_attestation_schema_ok=False,
        signed_attestation_schema_reason="no signed attestation",
        primary_reason=VERIFY_REASON_SIGNATURE_MISSING,
    )
    reasons = _bundle_failure_reason(result, explain=False)
    sig_reasons = [r for r in reasons if r["code"] == VERIFY_REASON_SIGNATURE_MISSING]
    assert sig_reasons
    assert sig_reasons[0]["path"] == "/signatures"


def test_bundle_failure_reason_signed_attestation_unknown_reason_fallback() -> None:
    result = _make_fake_result(
        signed_attestation_schema_ok=False,
        signed_attestation_schema_reason="something else",
        primary_reason=VERIFY_REASON_SCHEMA_UNKNOWN,  # not in approved set
    )
    reasons = _bundle_failure_reason(result, explain=False)
    assert any(r["code"] == VERIFY_REASON_SIGNATURE_INVALID for r in reasons)


def test_bundle_failure_reason_metadata_schema_version_missing() -> None:
    result = _make_fake_result(
        metadata_ok=False,
        metadata_reason="chain_metadata.schema_version is missing",
    )
    reasons = _bundle_failure_reason(result, explain=False)
    assert any(r["code"] == VERIFY_REASON_SCHEMA_VERSION_MISSING for r in reasons)
    assert any(r["path"] == "/chain_metadata/schema_version" for r in reasons)


def test_bundle_failure_reason_metadata_schema_version_not_integer() -> None:
    result = _make_fake_result(
        metadata_ok=False,
        metadata_reason="chain_metadata.schema_version must be an integer",
    )
    reasons = _bundle_failure_reason(result, explain=False)
    assert any(r["code"] == VERIFY_REASON_SCHEMA_INVALID for r in reasons)
    assert any(r["path"] == "/chain_metadata/schema_version" for r in reasons)


def test_bundle_failure_reason_metadata_schema_version_unsupported() -> None:
    result = _make_fake_result(
        metadata_ok=False,
        metadata_reason="chain_metadata.schema_version=99; this verifier handles schema_version values (1,)",
    )
    reasons = _bundle_failure_reason(result, explain=False)
    assert any(r["code"] == VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED for r in reasons)


def test_bundle_failure_reason_metadata_unknown_required_field_chain_metadata() -> None:
    result = _make_fake_result(
        metadata_ok=False,
        metadata_reason="chain_metadata.new_field is an unknown required field",
    )
    reasons = _bundle_failure_reason(result, explain=False)
    assert any(r["code"] == VERIFY_REASON_SCHEMA_UNKNOWN for r in reasons)
    assert any(r["path"] == "/chain_metadata/new_field" for r in reasons)


def test_bundle_failure_reason_metadata_unknown_required_field_verification_report() -> None:
    result = _make_fake_result(
        metadata_ok=False,
        metadata_reason="verification_report.new_field is an unknown required field",
    )
    reasons = _bundle_failure_reason(result, explain=False)
    assert any(r["code"] == VERIFY_REASON_SCHEMA_UNKNOWN for r in reasons)
    assert any(r["path"] == "/verification_report/new_field" for r in reasons)


def test_bundle_failure_reason_metadata_unknown_required_field_no_match() -> None:
    """Detail says 'unknown required field' but doesn't match the regex pattern."""
    result = _make_fake_result(
        metadata_ok=False,
        metadata_reason="chain_metadata.deep.nested.field is an unknown required field",
    )
    reasons = _bundle_failure_reason(result, explain=False)
    assert any(r["code"] == VERIFY_REASON_SCHEMA_UNKNOWN for r in reasons)
    # Falls back to /chain_metadata path since it starts with chain_metadata.
    assert any(r["path"] == "/chain_metadata" for r in reasons)


def test_bundle_failure_reason_metadata_unknown_required_field_verification_report_fallback() -> None:
    """verification_report.xyz but doesn't match full regex."""
    result = _make_fake_result(
        metadata_ok=False,
        metadata_reason="verification_report.deep.nested is an unknown required field",
    )
    reasons = _bundle_failure_reason(result, explain=False)
    assert any(r["path"] == "/verification_report" for r in reasons)


def test_bundle_failure_reason_metadata_chain_metadata_other() -> None:
    result = _make_fake_result(
        metadata_ok=False,
        metadata_reason="chain_metadata.anchor_ref has wrong type",
    )
    reasons = _bundle_failure_reason(result, explain=False)
    assert any(r["code"] == VERIFY_REASON_STRUCTURE_INVALID for r in reasons)
    assert any(r["path"] == "/chain_metadata" for r in reasons)


def test_bundle_failure_reason_metadata_verification_report_other() -> None:
    result = _make_fake_result(
        metadata_ok=False,
        metadata_reason="some other error",
    )
    reasons = _bundle_failure_reason(result, explain=False)
    assert any(r["path"] == "/verification_report" for r in reasons)


def test_bundle_failure_reason_metadata_none_detail() -> None:
    result = _make_fake_result(
        metadata_ok=False,
        metadata_reason=None,
    )
    reasons = _bundle_failure_reason(result, explain=False)
    assert any(r["code"] == VERIFY_REASON_STRUCTURE_INVALID for r in reasons)


def test_bundle_failure_reason_policy_trace_refs_failure() -> None:
    result = _make_fake_result(
        policy_trace_refs_ok=False,
        policy_trace_refs_reason="bad trace ref",
    )
    reasons = _bundle_failure_reason(result, explain=False)
    assert any(r["code"] == VERIFY_REASON_STRUCTURE_INVALID and r["path"] == "/policy_trace_refs" for r in reasons)


def test_bundle_failure_reason_retention_proofs_failure() -> None:
    result = _make_fake_result(
        retention_proofs_ok=False,
        retention_proofs_reason="bad retention proof",
    )
    reasons = _bundle_failure_reason(result, explain=False)
    assert any(r["code"] == VERIFY_REASON_STRUCTURE_INVALID and r["path"] == "/retention_proofs" for r in reasons)


def test_bundle_failure_reason_anchor_quarantined() -> None:
    result = _make_fake_result()
    bundle = {"anchoring": {"status": "quarantined", "quarantined": True}}
    reasons = _bundle_failure_reason(result, explain=False, bundle=bundle)
    assert any(r["code"] == VERIFY_REASON_ANCHOR_INVALID and r["path"] == "/anchoring" for r in reasons)


def test_bundle_failure_reason_with_explain_flag() -> None:
    result = _make_fake_result(
        metadata_ok=False,
        metadata_reason="chain_metadata.schema_version is missing",
    )
    reasons = _bundle_failure_reason(result, explain=True)
    for r in reasons:
        if "explanation" in r:
            assert r["explanation"]


def test_bundle_failure_reason_empty_no_specific_failure() -> None:
    # No specific failure triggers the fallback (lines 577-586)
    result = _make_fake_result()
    reasons = _bundle_failure_reason(result, explain=False)
    assert len(reasons) == 1
    assert reasons[0]["code"] == VERIFY_REASON_STRUCTURE_INVALID
    assert reasons[0]["path"] == "/"


# ---------------------------------------------------------------------------
# verify_result_exit_code (lines 423-437)
# ---------------------------------------------------------------------------


def test_verify_result_exit_code_none() -> None:
    assert verify_result_exit_code(None) == VERIFY_JSON_EXIT_CODE_VERIFICATION_FAILURE


def test_verify_result_exit_code_ok() -> None:
    result = type("r", (), {"ok": True, "anchoring_quarantined": False})()
    assert verify_result_exit_code(result) == VERIFY_JSON_EXIT_CODE_VERIFIED


def test_verify_result_exit_code_quarantined() -> None:
    result = type("r", (), {"ok": False, "anchoring_quarantined": True})()
    assert verify_result_exit_code(result) == VERIFY_JSON_EXIT_CODE_PINNING_GATE_FAILURE


def test_verify_result_exit_code_failure() -> None:
    result = type("r", (), {"ok": False, "anchoring_quarantined": False})()
    assert verify_result_exit_code(result) == VERIFY_JSON_EXIT_CODE_VERIFICATION_FAILURE


# ---------------------------------------------------------------------------
# build_verify_json_outcome — all exception paths
# ---------------------------------------------------------------------------


def test_build_verify_json_outcome_file_not_found(tmp_path: Path) -> None:
    missing = tmp_path / "no_such.json"
    outcome = build_verify_json_outcome(
        missing,
        require_non_empty=False,
        require_signed_attestation=False,
        explain=False,
    )
    assert outcome.exit_code == VERIFY_JSON_EXIT_CODE_USAGE_ERROR
    assert outcome.payload["reason_code"] == VERIFY_REASON_SCHEMA_INVALID


def test_build_verify_json_outcome_file_not_found_explain(tmp_path: Path) -> None:
    missing = tmp_path / "no_such.json"
    outcome = build_verify_json_outcome(
        missing,
        require_non_empty=False,
        require_signed_attestation=False,
        explain=True,
    )
    assert outcome.exit_code == VERIFY_JSON_EXIT_CODE_USAGE_ERROR
    assert "explanation" in outcome.payload


def test_build_verify_json_outcome_invalid_utf8(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_bytes(b"\xff\xfe")
    outcome = build_verify_json_outcome(
        bad,
        require_non_empty=False,
        require_signed_attestation=False,
        explain=False,
    )
    assert outcome.exit_code == VERIFY_JSON_EXIT_CODE_USAGE_ERROR
    assert outcome.payload["reason_code"] == VERIFY_REASON_SCHEMA_INVALID


def test_build_verify_json_outcome_invalid_utf8_explain(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_bytes(b"\xff\xfe")
    outcome = build_verify_json_outcome(
        bad,
        require_non_empty=False,
        require_signed_attestation=False,
        explain=True,
    )
    assert "explanation" in outcome.payload


def test_build_verify_json_outcome_duplicate_keys(tmp_path: Path) -> None:
    bad = tmp_path / "dup.json"
    bad.write_text('{"a": 1, "a": 2}', encoding="utf-8")
    outcome = build_verify_json_outcome(
        bad,
        require_non_empty=False,
        require_signed_attestation=False,
        explain=False,
    )
    assert outcome.exit_code == VERIFY_JSON_EXIT_CODE_USAGE_ERROR
    assert outcome.payload["reason_code"] == VERIFY_REASON_STRUCTURE_INVALID


def test_build_verify_json_outcome_duplicate_keys_explain(tmp_path: Path) -> None:
    bad = tmp_path / "dup.json"
    bad.write_text('{"chain_metadata": {}, "chain_metadata": {}}', encoding="utf-8")
    outcome = build_verify_json_outcome(
        bad,
        require_non_empty=False,
        require_signed_attestation=False,
        explain=True,
    )
    assert "explanation" in outcome.payload


def test_build_verify_json_outcome_duplicate_key_no_regex_match(tmp_path: Path) -> None:
    """Branch 651->653: _DuplicateKeyError whose message doesn't match the regex (path stays '/')."""
    from unittest import mock as _mock  # noqa: PLC0415

    bad = tmp_path / "dup.json"
    bad.write_text('{"a": 1, "a": 2}', encoding="utf-8")

    # Patch re.search to return None so the regex doesn't match
    with _mock.patch("attestplane.cli.verify_json.re.search", return_value=None):
        outcome = build_verify_json_outcome(
            bad,
            require_non_empty=False,
            require_signed_attestation=False,
            explain=False,
        )
    assert outcome.exit_code == VERIFY_JSON_EXIT_CODE_USAGE_ERROR
    assert outcome.payload["reasons"][0]["path"] == "/"


def test_build_verify_json_outcome_invalid_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{bad json", encoding="utf-8")
    outcome = build_verify_json_outcome(
        bad,
        require_non_empty=False,
        require_signed_attestation=False,
        explain=False,
    )
    assert outcome.exit_code == VERIFY_JSON_EXIT_CODE_USAGE_ERROR
    assert outcome.payload["reason_code"] == VERIFY_REASON_SCHEMA_INVALID


def test_build_verify_json_outcome_invalid_json_explain(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{bad json", encoding="utf-8")
    outcome = build_verify_json_outcome(
        bad,
        require_non_empty=False,
        require_signed_attestation=False,
        explain=True,
    )
    assert "explanation" in outcome.payload


def test_build_verify_json_outcome_non_object_root(tmp_path: Path) -> None:
    bad = tmp_path / "array.json"
    bad.write_text("[]", encoding="utf-8")
    outcome = build_verify_json_outcome(
        bad,
        require_non_empty=False,
        require_signed_attestation=False,
        explain=False,
    )
    assert outcome.exit_code == VERIFY_JSON_EXIT_CODE_PINNING_GATE_FAILURE
    assert outcome.payload["reason_code"] == VERIFY_REASON_SCHEMA_INVALID


def test_build_verify_json_outcome_non_object_root_explain(tmp_path: Path) -> None:
    bad = tmp_path / "array.json"
    bad.write_text("[]", encoding="utf-8")
    outcome = build_verify_json_outcome(
        bad,
        require_non_empty=False,
        require_signed_attestation=False,
        explain=True,
    )
    assert "explanation" in outcome.payload


def test_build_verify_json_outcome_taxonomy_version_failure(tmp_path: Path) -> None:
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    outcome = build_verify_json_outcome(
        path,
        require_non_empty=False,
        require_signed_attestation=False,
        require_taxonomy_version=99,
        explain=False,
    )
    assert outcome.exit_code == VERIFY_JSON_EXIT_CODE_PINNING_GATE_FAILURE


def test_build_verify_json_outcome_taxonomy_version_failure_explain(tmp_path: Path) -> None:
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    outcome = build_verify_json_outcome(
        path,
        require_non_empty=False,
        require_signed_attestation=False,
        require_taxonomy_version=99,
        explain=True,
    )
    assert "explanation" in outcome.payload


def test_build_verify_json_outcome_canonicalization_probe_failure(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "reject" / "canonicalization-edge.json"
    outcome = build_verify_json_outcome(
        fixture,
        require_non_empty=False,
        require_signed_attestation=False,
        explain=False,
    )
    assert outcome.exit_code == VERIFY_JSON_EXIT_CODE_VERIFICATION_FAILURE
    assert outcome.payload["reason_code"] == VERIFY_REASON_CANONICAL_MISMATCH


def test_build_verify_json_outcome_canonicalization_probe_failure_explain(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "reject" / "canonicalization-edge.json"
    outcome = build_verify_json_outcome(
        fixture,
        require_non_empty=False,
        require_signed_attestation=False,
        explain=True,
    )
    assert "explanation" in outcome.payload


def test_build_verify_json_outcome_bundle_schema_error(tmp_path: Path) -> None:
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    bundle["forbidden_fields"] = ["bad_field"]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    outcome = build_verify_json_outcome(
        path,
        require_non_empty=False,
        require_signed_attestation=False,
        explain=False,
    )
    assert outcome.exit_code == VERIFY_JSON_EXIT_CODE_PINNING_GATE_FAILURE


def test_build_verify_json_outcome_bundle_schema_error_explain(tmp_path: Path) -> None:
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    bundle["forbidden_fields"] = ["bad_field"]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    outcome = build_verify_json_outcome(
        path,
        require_non_empty=False,
        require_signed_attestation=False,
        explain=True,
    )
    assert "explanation" in outcome.payload


def test_build_verify_json_outcome_pass_with_explain(tmp_path: Path) -> None:
    bundle_path = _seed_bundle(tmp_path, n=2)
    outcome = build_verify_json_outcome(
        bundle_path,
        require_non_empty=False,
        require_signed_attestation=False,
        explain=True,
    )
    assert outcome.exit_code == VERIFY_JSON_EXIT_CODE_VERIFIED
    assert "explanation" in outcome.payload


def test_build_verify_json_outcome_fail_with_explain(tmp_path: Path) -> None:
    bundle_path = _seed_bundle(tmp_path, n=2)
    bundle = json.loads(bundle_path.read_text())
    bundle["events"][0]["event"]["payload"] = {"tampered": True}
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

    outcome = build_verify_json_outcome(
        bundle_path,
        require_non_empty=False,
        require_signed_attestation=False,
        explain=True,
    )
    assert outcome.exit_code != VERIFY_JSON_EXIT_CODE_VERIFIED
    assert "explanation" in outcome.payload


def test_build_verify_json_outcome_fail_error_code_sets_stderr(tmp_path: Path) -> None:
    """Verifier fail with VERIFY_REQUIRED_FIELDS_MISSING → stderr_code set."""
    empty_bundle = ProofBundleBuilder(chain_id="empty", producer_runtime="test").build()
    path = tmp_path / "empty.json"
    path.write_text(json.dumps(empty_bundle), encoding="utf-8")

    outcome = build_verify_json_outcome(
        path,
        require_non_empty=True,
        require_signed_attestation=False,
        explain=False,
    )
    assert outcome.exit_code == VERIFY_JSON_EXIT_CODE_PINNING_GATE_FAILURE
    assert outcome.stderr_code is not None


def test_build_verify_json_outcome_fail_no_error_code_no_stderr(tmp_path: Path) -> None:
    """Verifier fail without schema error code → stderr_code is None."""
    bundle_path = _seed_bundle(tmp_path, n=2)
    bundle = json.loads(bundle_path.read_text())
    bundle["events"][0]["event"]["payload"] = {"tampered": True}
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

    outcome = build_verify_json_outcome(
        bundle_path,
        require_non_empty=False,
        require_signed_attestation=False,
        explain=False,
    )
    assert outcome.exit_code == VERIFY_JSON_EXIT_CODE_VERIFICATION_FAILURE
    assert outcome.stderr_code is None


# ---------------------------------------------------------------------------
# _canonical_path_to_pointer token before bracket (lines 101-104)
# ---------------------------------------------------------------------------


def test_canonical_path_token_before_bracket() -> None:
    # 'a[0]' after '$.' — 'a' is in token when '[' is encountered
    assert _canonical_path_to_pointer("$.a[0]") == "/a/0"
    # Without token before bracket
    assert _canonical_path_to_pointer("$.[0]") == "/0"


# ---------------------------------------------------------------------------
# _schema_reason_for_bundle_error — SCHEMA_VERSION_MISSING path rewrite (line 315)
# ---------------------------------------------------------------------------


def test_schema_reason_for_bundle_error_schema_version_missing_path_rewrite() -> None:
    """Line 315: when classify returns SCHEMA_VERSION_MISSING and path=='/': rewrite path."""
    from unittest import mock as _mock  # noqa: PLC0415

    from attestplane.verifier import BundleSchemaError

    with _mock.patch(
        "attestplane.cli.verify_json.classify_bundle_schema_error",
        return_value=VERIFY_REASON_SCHEMA_VERSION_MISSING,
    ):
        code, path = _schema_reason_for_bundle_error(BundleSchemaError("some unknown error"))
    assert code == VERIFY_REASON_SCHEMA_VERSION_MISSING
    assert path == "/chain_metadata/schema_version"


# ---------------------------------------------------------------------------
# _json_pass with explanation (line 414->416)
# ---------------------------------------------------------------------------


def test_json_pass_with_explanation(tmp_path: Path) -> None:
    """Line 414->416: _json_pass when explanation is not None (True branch)."""
    bundle_path = _seed_bundle(tmp_path, n=1)
    outcome = build_verify_json_outcome(
        bundle_path,
        require_non_empty=False,
        require_signed_attestation=False,
        explain=True,
    )
    assert outcome.exit_code == VERIFY_JSON_EXIT_CODE_VERIFIED
    assert "explanation" in outcome.payload
    assert outcome.payload["explanation"] is not None


def test_json_pass_without_explanation(tmp_path: Path) -> None:
    """Branch 414->416 False: _json_pass when explanation IS None (explain=False)."""
    bundle_path = _seed_bundle(tmp_path, n=1)
    outcome = build_verify_json_outcome(
        bundle_path,
        require_non_empty=False,
        require_signed_attestation=False,
        explain=False,
    )
    assert outcome.exit_code == VERIFY_JSON_EXIT_CODE_VERIFIED
    assert "explanation" not in outcome.payload


# ---------------------------------------------------------------------------
# _bundle_failure_reason — unknown required field fallback paths (lines 526-534)
# ---------------------------------------------------------------------------


def test_bundle_failure_reason_unknown_field_chain_metadata_no_regex_match() -> None:
    """Line 526-527: 'unknown required field' in detail, starts with chain_metadata. but no regex match."""
    result = _make_fake_result(
        metadata_ok=False,
        metadata_reason="chain_metadata.deep.nested.field is an unknown required field",
    )
    reasons = _bundle_failure_reason(result, explain=False)
    assert any(r["code"] == VERIFY_REASON_SCHEMA_UNKNOWN for r in reasons)
    assert any(r["path"] == "/chain_metadata" for r in reasons)


def test_bundle_failure_reason_unknown_field_verification_report_no_regex_match() -> None:
    """Line 528-529: 'unknown required field', starts with verification_report. but no regex match."""
    result = _make_fake_result(
        metadata_ok=False,
        metadata_reason="verification_report.deep.nested is an unknown required field",
    )
    reasons = _bundle_failure_reason(result, explain=False)
    assert any(r["code"] == VERIFY_REASON_SCHEMA_UNKNOWN for r in reasons)
    assert any(r["path"] == "/verification_report" for r in reasons)


def test_bundle_failure_reason_unknown_field_other_section_no_match() -> None:
    """Branch 528->534: 'unknown required field', doesn't start with chain_metadata or verification_report."""
    result = _make_fake_result(
        metadata_ok=False,
        metadata_reason="some_other_section.field is an unknown required field",
    )
    reasons = _bundle_failure_reason(result, explain=False)
    assert any(r["code"] == VERIFY_REASON_SCHEMA_UNKNOWN for r in reasons)
    # Falls through to verification_report default
    assert any(r["path"] == "/verification_report" for r in reasons)


# ---------------------------------------------------------------------------
# build_verify_json_outcome — CanonicalizationError from verify_proof_bundle (lines 771-773)
# ---------------------------------------------------------------------------


def test_build_verify_json_outcome_canonicalization_error_from_verifier(tmp_path: Path) -> None:
    """Lines 771-773: CanonicalizationError raised by verify_proof_bundle (not from probe)."""
    from unittest import mock as _mock  # noqa: PLC0415

    from attestplane.canonical import CanonicalizationError as _CanonicalizationError
    from attestplane.proof_bundle import ProofBundleBuilder as _PBB

    bundle = _PBB(chain_id="test", producer_runtime="test").build()
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    # Probe returns (None, None) but verify_proof_bundle raises CanonicalizationError
    with _mock.patch("attestplane.cli.verify_json._canonicalization_probe", return_value=(None, None)), _mock.patch(
        "attestplane.cli.verify_json.verify_proof_bundle",
        side_effect=_CanonicalizationError("simulated canon error"),
    ):
        outcome = build_verify_json_outcome(
            path,
            require_non_empty=False,
            require_signed_attestation=False,
            explain=False,
        )
    assert outcome.exit_code == VERIFY_JSON_EXIT_CODE_VERIFICATION_FAILURE
    assert outcome.payload["reason_code"] == VERIFY_REASON_CANONICAL_MISMATCH


def test_build_verify_json_outcome_canonicalization_error_from_verifier_explain(tmp_path: Path) -> None:
    """Lines 771-773 with explain=True."""
    from unittest import mock as _mock  # noqa: PLC0415

    from attestplane.canonical import CanonicalizationError as _CanonicalizationError
    from attestplane.proof_bundle import ProofBundleBuilder as _PBB

    bundle = _PBB(chain_id="test", producer_runtime="test").build()
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    with _mock.patch("attestplane.cli.verify_json._canonicalization_probe", return_value=(None, None)), _mock.patch(
        "attestplane.cli.verify_json.verify_proof_bundle",
        side_effect=_CanonicalizationError("simulated canon error"),
    ):
        outcome = build_verify_json_outcome(
            path,
            require_non_empty=False,
            require_signed_attestation=False,
            explain=True,
        )
    assert "explanation" in outcome.payload


# ---------------------------------------------------------------------------
# _reason_entry with explain=True (lines 128-144)
# ---------------------------------------------------------------------------


def test_reason_entry_explain_true_adds_explanation() -> None:
    entry = _reason_entry(
        VERIFY_REASON_SCHEMA_INVALID,
        "/foo",
        summary="short msg",
        detail="detailed message",
        explain=True,
    )
    assert "explanation" in entry
    assert entry["explanation"] == verify_reason_code_explanation(VERIFY_REASON_SCHEMA_INVALID)
    assert entry["message"] == "detailed message"


def test_reason_entry_explain_false_uses_summary() -> None:
    entry = _reason_entry(
        VERIFY_REASON_SCHEMA_INVALID,
        "/foo",
        summary="short msg",
        detail="detailed message",
        explain=False,
    )
    assert "explanation" not in entry
    assert entry["message"] == "short msg"


def test_reason_entry_explain_true_no_detail_uses_summary() -> None:
    entry = _reason_entry(
        VERIFY_REASON_SCHEMA_INVALID,
        "/foo",
        summary="short msg",
        detail=None,
        explain=True,
    )
    assert entry["message"] == "short msg"


# ---------------------------------------------------------------------------
# Full CLI round-trips — verify --json with quarantined anchoring
# ---------------------------------------------------------------------------


def test_verify_json_quarantined_bundle_exit_code_2(capsys: pytest.CaptureFixture[str]) -> None:
    fixture = Path(__file__).resolve().parent / "conformance" / "free_tsa_quarantined_bundle.json"
    rc = main(["verify", "--json", str(fixture)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == VERIFY_JSON_EXIT_CODE_PINNING_GATE_FAILURE
    assert payload["result"] == "fail"
    assert payload["anchoring"]["quarantined"] is True
