# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coverage-gap tests for attestplane.proof_bundle.

Targets the uncovered lines from the initial audit:
110, 271, 273, 275, 292-293, 295, 430, 432, 439-445, 517->520, 557-559, 572-578
(and the serialisation paths: 59-61, 82-112, 154-155, 167, 179, 268-301, 324-341, 349-351, 377).
"""

from __future__ import annotations

from base64 import standard_b64encode
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from attestplane.hashchain import chain_extend, genesis_head
from attestplane.proof_bundle import (
    EmptyProofBundleError,
    FrameworkMapping,
    IncompleteProofBundleError,
    ProofBundleBuilder,
    ProofBundleError,
    _bundle_anchoring_status,
    _validate_anchoring_state,
    build_auditor_export,
    bundle_to_dsse_envelope,
    bundle_to_in_toto_statement,
    deserialize_signature_record,
)
from attestplane.types import EventDraft

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_HEX64 = "a" * 64


def _build_one_event() -> Any:
    head = genesis_head()
    draft = EventDraft(event_type="eval_event", actor="a", payload={"k": "v"})
    return chain_extend(head, draft, now=_NOW, event_id="00000000-0000-7000-8000-000000000001")


def _make_signature_record(event: Any) -> Any:
    """Build a duck-typed SimpleNamespace acting like a SignatureRecord.

    extend_signatures duck-checks attribute presence only; serialization
    calls attribute access.  We do NOT construct the real SignatureRecord
    to avoid the Ed25519 key-size constraint in the dataclass __post_init__.
    """
    rec = SimpleNamespace(
        signature_schema_version=1,
        signed_seq=event.seq,
        signed_event_hash=event.event_hash,
        signature=b"\xab" * 64,   # 64 bytes — Ed25519 size
        key_id="key-001",
        public_key_der=b"pub",
        signing_cert_chain=(b"cert1",),
        signed_at=_NOW,
        signature_mode="per_event",
        signed_payload=b"payload",
    )
    return rec


# ---------------------------------------------------------------------------
# EmptyProofBundleError / IncompleteProofBundleError default ctors (154-155, 167, 179)
# ---------------------------------------------------------------------------


def test_empty_proof_bundle_error_default_message() -> None:
    err = EmptyProofBundleError()
    assert "at least one event" in str(err)
    assert err.error_code is not None


def test_incomplete_proof_bundle_error_default_message() -> None:
    err = IncompleteProofBundleError()
    assert "schema" in str(err)
    assert err.error_code is not None


def test_proof_bundle_error_stores_code() -> None:
    from attestplane.verify_errors import VERIFY_REQUIRED_FIELDS_MISSING

    err = ProofBundleError("boom", error_code=VERIFY_REQUIRED_FIELDS_MISSING)
    assert err.error_code == VERIFY_REQUIRED_FIELDS_MISSING


# ---------------------------------------------------------------------------
# ProofBundleBuilder.minimal() — lines 268-301
# ---------------------------------------------------------------------------


def test_minimal_rejects_non_string_subject_digest() -> None:
    signer = MagicMock()
    with pytest.raises(IncompleteProofBundleError, match="lowercase 64-hex"):
        ProofBundleBuilder.minimal(12345, signer)  # type: ignore[arg-type]


def test_minimal_rejects_uppercase_hex() -> None:
    signer = MagicMock()
    with pytest.raises(IncompleteProofBundleError, match="lowercase 64-hex"):
        ProofBundleBuilder.minimal("A" * 64, signer)  # uppercase


def test_minimal_rejects_short_hex() -> None:
    signer = MagicMock()
    with pytest.raises(IncompleteProofBundleError, match="lowercase 64-hex"):
        ProofBundleBuilder.minimal("a" * 63, signer)


def test_minimal_rejects_signer_without_sign_event() -> None:
    with pytest.raises(IncompleteProofBundleError, match="sign_event"):
        ProofBundleBuilder.minimal("a" * 64, object())


def test_minimal_rejects_extra_payload_not_dict() -> None:
    signer = MagicMock()
    signer.sign_event = MagicMock(return_value=[])
    with pytest.raises(IncompleteProofBundleError, match="JSON object"):
        ProofBundleBuilder.minimal("a" * 64, signer, extra_payload="bad")  # type: ignore[arg-type]


def test_minimal_rejects_extra_payload_overriding_subject_digest() -> None:
    signer = MagicMock()
    signer.sign_event = MagicMock(return_value=[])
    with pytest.raises(IncompleteProofBundleError, match="subject_digest"):
        ProofBundleBuilder.minimal("a" * 64, signer, extra_payload={"subject_digest": "override"})


def test_minimal_signer_raises_produces_incomplete_error() -> None:
    signer = MagicMock()
    signer.sign_event = MagicMock(side_effect=RuntimeError("boom"))
    with pytest.raises(IncompleteProofBundleError, match="signer failed"):
        ProofBundleBuilder.minimal("a" * 64, signer)


def test_minimal_signer_returns_empty_raises() -> None:
    signer = MagicMock()
    signer.sign_event = MagicMock(return_value=[])
    with pytest.raises(IncompleteProofBundleError, match="no signature records"):
        ProofBundleBuilder.minimal("a" * 64, signer)


def test_minimal_happy_path() -> None:
    """minimal() returns a valid bundle with a syntactic signature."""
    event = _build_one_event()
    rec = _make_signature_record(event)

    signer = MagicMock()
    signer.sign_event = MagicMock(return_value=[rec])
    signer._chain_id = "my-chain"

    bundle = ProofBundleBuilder.minimal("a" * 64, signer)
    assert bundle["bundle_version"] == 1
    assert len(bundle["events"]) == 1
    assert "signatures" in bundle


# ---------------------------------------------------------------------------
# extend_signatures validation (324-341)
# ---------------------------------------------------------------------------


def test_extend_signatures_rejects_missing_attrs() -> None:
    builder = ProofBundleBuilder(chain_id="c", producer_runtime="t")
    bad = SimpleNamespace(signature_schema_version=1)  # missing most attrs
    with pytest.raises(ValueError, match="missing SignatureRecord fields"):
        builder.extend_signatures([bad])


def test_extend_signatures_accepts_full_record() -> None:
    event = _build_one_event()
    rec = _make_signature_record(event)
    builder = ProofBundleBuilder(chain_id="c", producer_runtime="t")
    builder.extend([event])
    builder.extend_signatures([rec])
    bundle = builder.build()
    assert "signatures" in bundle
    assert len(bundle["signatures"]) == 1


# ---------------------------------------------------------------------------
# extend_retention_proofs (349-351)
# ---------------------------------------------------------------------------


def test_extend_retention_proofs_rejects_invalid() -> None:
    builder = ProofBundleBuilder(chain_id="c", producer_runtime="t")
    with pytest.raises(ValueError, match="missing required fields"):
        builder.extend_retention_proofs([{"bad": "shape"}])


def test_extend_retention_proofs_accepts_valid(tmp_path: Any) -> None:
    """A correctly-shaped retention proof marker is accepted and emitted."""
    event = _build_one_event()
    builder = ProofBundleBuilder(chain_id="c", producer_runtime="t")
    builder.extend([event])
    # Build a syntactically valid retention proof marker
    from attestplane.retention import build_retention_marker

    proof = build_retention_marker(
        proof_id="00000000-0000-7000-8000-000000000099",
        target_event_hash_hex=event.event_hash.hex(),
        commit_event_hash_hex=event.event_hash.hex(),
        reason="gdpr_erasure",
    )
    builder.extend_retention_proofs([proof])
    bundle = builder.build()
    assert "retention_proofs" in bundle


# ---------------------------------------------------------------------------
# _validate_anchoring_state — lines 430, 432
# ---------------------------------------------------------------------------


def test_validate_anchoring_state_rejects_bad_status() -> None:
    with pytest.raises(ValueError, match="status"):
        _validate_anchoring_state({"status": "unknown_bad", "quarantined": False})


def test_validate_anchoring_state_rejects_non_bool_quarantined() -> None:
    with pytest.raises(ValueError, match="quarantined"):
        _validate_anchoring_state({"status": "anchored", "quarantined": "yes"})


def test_validate_anchoring_state_accepts_valid() -> None:
    _validate_anchoring_state({"status": "anchored", "quarantined": False})
    _validate_anchoring_state({"status": "quarantined", "quarantined": True})
    _validate_anchoring_state({"status": "unanchored", "quarantined": False})


# ---------------------------------------------------------------------------
# _bundle_anchoring_status — lines 439-445
# ---------------------------------------------------------------------------


def test_bundle_anchoring_status_no_anchoring_key() -> None:
    bundle: dict[str, Any] = {
        "chain_metadata": {"anchor_ref": None},
        "anchoring": None,
    }
    result = _bundle_anchoring_status(bundle)
    assert result is None


def test_bundle_anchoring_status_bad_status() -> None:
    bundle: dict[str, Any] = {
        "anchoring": {"status": "bad_value", "quarantined": False},
    }
    result = _bundle_anchoring_status(bundle)
    assert result is None


def test_bundle_anchoring_status_non_bool_quarantined() -> None:
    bundle: dict[str, Any] = {
        "anchoring": {"status": "anchored", "quarantined": "yes"},
    }
    result = _bundle_anchoring_status(bundle)
    assert result is None


def test_bundle_anchoring_status_happy() -> None:
    bundle: dict[str, Any] = {
        "anchoring": {"status": "quarantined", "quarantined": True},
    }
    result = _bundle_anchoring_status(bundle)
    assert result == "quarantined"


# ---------------------------------------------------------------------------
# build() with anchoring kwarg (line 377)
# ---------------------------------------------------------------------------


def test_build_with_valid_anchoring() -> None:
    event = _build_one_event()
    builder = ProofBundleBuilder(chain_id="c", producer_runtime="t")
    builder.extend([event])
    anchoring = {"status": "anchored", "quarantined": False}
    bundle = builder.build(anchoring=anchoring)
    assert bundle["anchoring"] == anchoring


def test_build_with_invalid_anchoring_raises() -> None:
    event = _build_one_event()
    builder = ProofBundleBuilder(chain_id="c", producer_runtime="t")
    builder.extend([event])
    with pytest.raises(ValueError, match="status"):
        builder.build(anchoring={"status": "bad", "quarantined": False})


# ---------------------------------------------------------------------------
# build_auditor_export — empty events branch (517->520) + anchor_ref path
# ---------------------------------------------------------------------------


def test_build_auditor_export_empty_events_uses_sentinel() -> None:
    builder = ProofBundleBuilder(chain_id="c", producer_runtime="t")
    bundle = builder.build(now=_NOW)
    export = build_auditor_export(bundle)
    assert export["chain_summary"]["event_count"] == 0
    # sentinel from verification_report.verified_at
    tr = export["chain_summary"]["time_range"]
    assert tr["earliest"] == tr["latest"]


def test_build_auditor_export_anchor_ref_in_chain_metadata() -> None:
    event = _build_one_event()
    builder = ProofBundleBuilder(chain_id="c", producer_runtime="t", anchor_ref="txhash-abc")
    builder.extend([event])
    bundle = builder.build()
    export = build_auditor_export(bundle)
    assert export["chain_summary"]["anchor_status"] == "anchored"


def test_build_auditor_export_no_anchor_ref() -> None:
    event = _build_one_event()
    builder = ProofBundleBuilder(chain_id="c", producer_runtime="t")
    builder.extend([event])
    bundle = builder.build()
    export = build_auditor_export(bundle)
    assert export["chain_summary"]["anchor_status"] == "unanchored"


def test_build_auditor_export_with_anchoring_dict() -> None:
    event = _build_one_event()
    builder = ProofBundleBuilder(chain_id="c", producer_runtime="t")
    builder.extend([event])
    bundle = builder.build(anchoring={"status": "quarantined", "quarantined": True})
    export = build_auditor_export(bundle)
    assert export["chain_summary"]["anchor_status"] == "quarantined"


# ---------------------------------------------------------------------------
# deserialize_signature_record — lines 82-112 (timestamp without Z branch = line 110)
# ---------------------------------------------------------------------------


def test_deserialize_signature_record_missing_fields() -> None:
    with pytest.raises(ValueError, match="missing fields"):
        deserialize_signature_record({"only": "one_field"})


_DERIVED_KEY_ID = "0017dea7770f7ecff7ab3c2050654612"  # derive_key_id(b"pub")


def _make_sig_raw(signed_at: str, seq: int = 0) -> dict[str, Any]:
    """Build a raw dict suitable for deserialize_signature_record.

    SignatureRecord requires: signed_event_hash=32 bytes, signature=64 bytes,
    and key_id must match derive_key_id(public_key_der).
    """
    return {
        "signature_schema_version": 1,
        "signed_seq": seq,
        "signed_event_hash_hex": "a" * 64,   # 32 bytes decoded
        "signature_hex": "b" * 128,           # 64 bytes decoded
        "key_id": _DERIVED_KEY_ID,
        "public_key_der_b64": standard_b64encode(b"pub").decode(),
        "signing_cert_chain_b64": [standard_b64encode(b"cert").decode()],
        "signed_at": signed_at,
        "signature_mode": "per_event",
        "signed_payload_b64": standard_b64encode(b"payload").decode(),
    }


def test_deserialize_signature_record_non_z_timestamp() -> None:
    """Branch: ts_text does NOT end with 'Z' → datetime.fromisoformat path."""
    raw = _make_sig_raw("2026-05-17T12:00:00.000000+00:00", seq=0)
    rec = deserialize_signature_record(raw)
    assert rec.signed_seq == 0


def test_deserialize_signature_record_z_timestamp() -> None:
    raw = _make_sig_raw("2026-05-17T12:00:00.000000Z", seq=1)
    rec = deserialize_signature_record(raw)
    assert rec.signed_seq == 1
    assert rec.signed_at.tzinfo is not None


# ---------------------------------------------------------------------------
# _serialize_signature_record round-trip (lines 59-61)
# ---------------------------------------------------------------------------


def test_serialize_signature_record_in_bundle() -> None:
    """Verify round-trip: extend_signatures → build includes serialized record."""
    event = _build_one_event()
    rec = _make_signature_record(event)
    builder = ProofBundleBuilder(chain_id="c", producer_runtime="t")
    builder.extend([event])
    builder.extend_signatures([rec])
    bundle = builder.build()
    sig = bundle["signatures"][0]
    assert sig["key_id"] == "key-001"
    assert sig["signature_mode"] == "per_event"
    # hex fields
    assert len(sig["signed_event_hash_hex"]) == 64
    assert len(sig["signature_hex"]) == 128


# ---------------------------------------------------------------------------
# bundle_to_in_toto_statement convenience re-export (lines 557-559)
# ---------------------------------------------------------------------------


def test_bundle_to_in_toto_statement_reexport() -> None:
    event = _build_one_event()
    builder = ProofBundleBuilder(chain_id="c", producer_runtime="t")
    builder.extend([event])
    bundle = builder.build()
    stmt = bundle_to_in_toto_statement(bundle)
    assert stmt["predicateType"] == "https://attestplane.io/v1/agent-runtime-event"


# ---------------------------------------------------------------------------
# bundle_to_dsse_envelope convenience re-export (lines 572-578)
# ---------------------------------------------------------------------------


def test_bundle_to_dsse_envelope_reexport() -> None:
    event = _build_one_event()
    builder = ProofBundleBuilder(chain_id="c", producer_runtime="t")
    builder.extend([event])
    bundle = builder.build()
    envelope = bundle_to_dsse_envelope(bundle)
    assert "payload" in envelope
    assert envelope["payloadType"] == "application/vnd.in-toto+json"


def test_bundle_to_dsse_envelope_with_signatures() -> None:
    event = _build_one_event()
    builder = ProofBundleBuilder(chain_id="c", producer_runtime="t")
    builder.extend([event])
    bundle = builder.build()
    sigs = [{"keyid": "kid1", "sig": "abc"}]
    envelope = bundle_to_dsse_envelope(bundle, signatures=sigs)
    assert envelope["signatures"] == sigs


# ---------------------------------------------------------------------------
# add_framework_mapping out-of-bounds (lines 307-313)
# ---------------------------------------------------------------------------


def test_add_framework_mapping_out_of_bounds_raises() -> None:
    builder = ProofBundleBuilder(chain_id="c", producer_runtime="t")
    # No events added yet — index 0 is out of bounds.
    mapping = FrameworkMapping(
        obligation_id="eu-ai-act.art12.1",
        evidence_event_indexes=(0,),
        implementation_status_at_bundle_time="mapping_target",
    )
    with pytest.raises(ValueError, match="event index 0"):
        builder.add_framework_mapping(mapping)


def test_add_framework_mapping_in_bounds_ok() -> None:
    event = _build_one_event()
    builder = ProofBundleBuilder(chain_id="c", producer_runtime="t")
    builder.extend([event])
    mapping = FrameworkMapping(
        obligation_id="eu-ai-act.art12.1",
        evidence_event_indexes=(0,),
        implementation_status_at_bundle_time="mapping_target",
    )
    builder.add_framework_mapping(mapping)
    assert len(builder.framework_mappings) == 1


# ---------------------------------------------------------------------------
# build_auditor_export with framework_coverage_registries (lines 492-501)
# ---------------------------------------------------------------------------


def test_build_auditor_export_with_framework_coverage_registries() -> None:
    from attestplane.obligations import load_eu_ai_act_article_12

    event = _build_one_event()
    builder = ProofBundleBuilder(chain_id="c", producer_runtime="t")
    builder.extend([event])
    registry = load_eu_ai_act_article_12()
    # Cover one obligation with evidence
    first_id = registry.entries[0].obligation_id
    mapping = FrameworkMapping(
        obligation_id=first_id,
        evidence_event_indexes=(0,),
        implementation_status_at_bundle_time="mapping_target",
    )
    builder.add_framework_mapping(mapping)
    bundle = builder.build()
    export = build_auditor_export(bundle, framework_coverage_registries=[registry])
    rows = export["framework_coverage"]
    assert len(rows) > 0
    # At least one row should have the covered obligation_id in with_evidence
    covered = {oid for row in rows for oid in row["obligation_ids_with_evidence"]}
    assert first_id in covered
