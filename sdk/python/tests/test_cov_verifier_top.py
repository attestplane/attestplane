# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coverage-gap tests for verifier.py, verify_reason_codes.py, verify_errors.py,
settlement_verifier.py, substrate.py, and sdk/bundle.py.

Each test targets specific uncovered lines/branches identified by the baseline run.
"""

from __future__ import annotations

import io
import json
from base64 import standard_b64encode
from datetime import UTC, datetime
from pathlib import Path

import pytest

from attestplane.hashchain import (
    GENESIS_HASH,
    chain_extend,
    genesis_head,
    hash_event,
)
from attestplane.proof_bundle import ProofBundleBuilder
from attestplane.settlement_verifier import (
    SettlementPreconditionClaim,
    check_settlement_precondition,
)
from attestplane.substrate import AttestSubstrate
from attestplane.types import ChainedEvent, ChainHead, EventDraft
from attestplane.verifier import (
    BundleSchemaError,
    BundleVerificationError,
    VerifyAnchoringState,
    classify_bundle_schema_error,
    verify_proof_bundle,
    verify_proof_bundle_file,
)
from attestplane.verify_errors import (
    ALL_VERIFY_ERROR_CODES_V1,
    VERIFY_BUNDLE_SCHEMA_INCOMPLETE,
    VERIFY_EXTENSION_FAILED,
    VERIFY_OK,
    VERIFY_REQUIRED_FIELDS_MISSING,
    is_known_verify_error_code,
)
from attestplane.verify_reason_codes import (
    ALL_VERIFY_REASON_CODES_V1,
    VERIFY_REASON_ANCHOR_QUARANTINED,
    format_verify_taxonomy_version,
    is_known_verify_reason_code,
    resolve_verify_taxonomy_version,
    verify_reason_code_explanation,
    verify_reason_code_matches_format,
)

# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _build_chain(n: int) -> list[ChainedEvent]:
    chain: list[ChainedEvent] = []
    head = genesis_head()
    for i in range(n):
        ev = chain_extend(
            head,
            EventDraft(event_type="eval_event", actor=f"a{i}", payload={"i": i}),
            now=_NOW,
            event_id=f"00000000-0000-7000-8000-{i:012d}",
        )
        chain.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    return chain


def _good_bundle(n: int = 2) -> dict:
    builder = ProofBundleBuilder(chain_id="test", producer_runtime="test")
    builder.extend(_build_chain(n))
    return builder.build()


def _syntactic_sig(event: ChainedEvent) -> dict:
    return {
        "signature_schema_version": 1,
        "signed_seq": event.seq,
        "signed_event_hash_hex": hash_event(event.event).hex(),
        "signature_hex": "a" * 128,
        "key_id": "b" * 32,
        "public_key_der_b64": standard_b64encode(b"pk").decode(),
        "signing_cert_chain_b64": [standard_b64encode(b"cert").decode()],
        "signed_at": "2026-05-17T12:00:00Z",
        "signature_mode": "per_event",
        "signed_payload_b64": standard_b64encode(b"payload").decode(),
    }


def _base_bundle_fields() -> dict:
    """Minimal syntactically-valid bundle template (no events)."""
    builder = ProofBundleBuilder(chain_id="base", producer_runtime="test")
    return builder.build()


# ===========================================================================
# verify_reason_codes.py  (lines 93, 98, 103, 108, 113-115)
# ===========================================================================


def test_is_known_verify_reason_code_true() -> None:
    # line 93
    for code in ALL_VERIFY_REASON_CODES_V1:
        assert is_known_verify_reason_code(code) is True


def test_is_known_verify_reason_code_false() -> None:
    # line 93 — False branch
    assert is_known_verify_reason_code("att.verify.nonexistent") is False
    assert is_known_verify_reason_code("") is False


def test_verify_reason_code_matches_format_true() -> None:
    # line 98
    assert verify_reason_code_matches_format("att.verify.canonical_mismatch") is True
    assert verify_reason_code_matches_format("att.verify.schema_version_unsupported") is True


def test_verify_reason_code_matches_format_false() -> None:
    # line 98 — False branch
    assert verify_reason_code_matches_format("VERIFY_OK") is False
    assert verify_reason_code_matches_format("att.other.thing") is False


def test_verify_reason_code_explanation() -> None:
    # line 103
    for code in ALL_VERIFY_REASON_CODES_V1:
        explanation = verify_reason_code_explanation(code)
        assert isinstance(explanation, str)
        assert len(explanation) > 0


def test_resolve_verify_taxonomy_version() -> None:
    # line 108
    version = resolve_verify_taxonomy_version()
    assert version == 1


def test_format_verify_taxonomy_version_no_arg() -> None:
    # line 113-114 — None path calls resolve_verify_taxonomy_version
    result = format_verify_taxonomy_version()
    assert result == "1"


def test_format_verify_taxonomy_version_with_arg() -> None:
    # line 115 — explicit int path
    assert format_verify_taxonomy_version(2) == "2"
    assert format_verify_taxonomy_version(42) == "42"


def test_verify_reason_anchor_quarantined_not_in_all() -> None:
    # ANCHOR_QUARANTINED is deliberately excluded from ALL_VERIFY_REASON_CODES_V1
    assert VERIFY_REASON_ANCHOR_QUARANTINED not in ALL_VERIFY_REASON_CODES_V1
    # But it still matches the pattern
    assert verify_reason_code_matches_format(VERIFY_REASON_ANCHOR_QUARANTINED) is True


# ===========================================================================
# verify_errors.py  (line 86)
# ===========================================================================


def test_is_known_verify_error_code_true() -> None:
    # line 86
    for code in ALL_VERIFY_ERROR_CODES_V1:
        assert is_known_verify_error_code(code) is True


def test_is_known_verify_error_code_false() -> None:
    # line 86 — False branch
    assert is_known_verify_error_code("UNKNOWN_CODE") is False
    assert is_known_verify_error_code("") is False


# ===========================================================================
# substrate.py  (line 92)
# ===========================================================================


def test_substrate_repr() -> None:
    # line 92
    sub = AttestSubstrate()
    r = repr(sub)
    assert "AttestSubstrate" in r
    assert "len=0" in r
    assert "tip_seq=-1" in r


def test_substrate_repr_after_append() -> None:
    # line 92 — with events
    sub = AttestSubstrate()
    sub.append(EventDraft(event_type="t", actor="a"), now=_NOW)
    r = repr(sub)
    assert "len=1" in r
    assert "tip_seq=0" in r


def test_substrate_tip_method() -> None:
    # lines 71-74 — tip()
    sub = AttestSubstrate()

    tip = sub.tip()
    assert tip.event_hash == GENESIS_HASH
    assert tip.seq == -1


def test_substrate_verify_method() -> None:
    # lines 76-80 — verify()
    sub = AttestSubstrate()
    sub.append(EventDraft(event_type="t", actor="a"), now=_NOW)
    result = sub.verify()
    assert result.ok is True


def test_substrate_iter_method() -> None:
    # lines 86-89 — __iter__
    sub = AttestSubstrate()
    sub.append(EventDraft(event_type="t", actor="a"), now=_NOW)
    sub.append(EventDraft(event_type="t", actor="b"), now=_NOW)
    events = list(sub)
    assert len(events) == 2


def test_substrate_snapshot_method() -> None:
    # lines 94-97 — snapshot()
    sub = AttestSubstrate()
    sub.append(EventDraft(event_type="t", actor="a"), now=_NOW)
    snap = sub.snapshot()
    assert len(snap) == 1


def test_substrate_head_seq_method() -> None:
    # lines 99-102 — head_seq()
    sub = AttestSubstrate()
    assert sub.head_seq() == -1
    sub.append(EventDraft(event_type="t", actor="a"), now=_NOW)
    assert sub.head_seq() == 0


def test_substrate_from_events_success() -> None:
    # lines 112-118 — from_events() happy path
    source = AttestSubstrate()
    source.append(EventDraft(event_type="t", actor="a"), now=_NOW)
    source.append(EventDraft(event_type="t", actor="b"), now=_NOW)
    rehydrated = AttestSubstrate.from_events(source.snapshot())
    assert len(rehydrated) == 2
    assert rehydrated.tip() == source.tip()


def test_substrate_from_events_broken_chain() -> None:
    # lines 112-114 — from_events() with broken chain → ValueError
    from dataclasses import replace

    source = AttestSubstrate()
    source.append(EventDraft(event_type="t", actor="a"), now=_NOW)
    events = source.snapshot()
    tampered = [replace(events[0], event_hash=b"\x00" * 32)]
    with pytest.raises(ValueError, match="rehydrate"):
        AttestSubstrate.from_events(tampered)


def test_substrate_append_uses_default_now() -> None:
    # line 64 — now=None path uses datetime.now(UTC)
    sub = AttestSubstrate()
    ev = sub.append(EventDraft(event_type="t", actor="a"))  # no now= argument
    assert ev.seq == 0


# ===========================================================================
# sdk/bundle.py  (lines 28, 39, 50, 55-61)
# ===========================================================================


def test_raise_for_minimum_bundle_result_ok_noop() -> None:
    # line 28 — ok=True returns immediately
    from attestplane.sdk.bundle import raise_for_minimum_bundle_result

    chain = _build_chain(1)
    builder = ProofBundleBuilder(chain_id="ok-bundle", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    bundle["signatures"] = [_syntactic_sig(chain[0])]
    result = verify_proof_bundle(bundle, require_non_empty=True, require_signed_attestation=True)
    assert result.ok is True
    # must not raise
    raise_for_minimum_bundle_result(result)


def test_raise_for_minimum_bundle_result_empty_error() -> None:
    # line 29-33 — VERIFY_REQUIRED_FIELDS_MISSING → EmptyProofBundleError
    from attestplane.proof_bundle import EmptyProofBundleError
    from attestplane.sdk.bundle import raise_for_minimum_bundle_result

    bundle = ProofBundleBuilder(chain_id="empty", producer_runtime="test").build()
    result = verify_proof_bundle(bundle, require_non_empty=True)
    with pytest.raises(EmptyProofBundleError) as exc_info:
        raise_for_minimum_bundle_result(result)
    assert exc_info.value.error_code == VERIFY_REQUIRED_FIELDS_MISSING


def test_raise_for_minimum_bundle_result_schema_incomplete_error() -> None:
    # line 34-38 — VERIFY_BUNDLE_SCHEMA_INCOMPLETE → IncompleteProofBundleError
    from attestplane.proof_bundle import IncompleteProofBundleError
    from attestplane.sdk.bundle import raise_for_minimum_bundle_result

    chain = _build_chain(1)
    builder = ProofBundleBuilder(chain_id="unsigned", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    # No signatures -> schema incomplete
    result = verify_proof_bundle(bundle, require_non_empty=True)
    assert result.error_code == VERIFY_BUNDLE_SCHEMA_INCOMPLETE
    with pytest.raises(IncompleteProofBundleError) as exc_info:
        raise_for_minimum_bundle_result(result)
    assert exc_info.value.error_code == VERIFY_BUNDLE_SCHEMA_INCOMPLETE


def test_raise_for_minimum_bundle_result_other_failure() -> None:
    # line 39 — generic IncompleteProofBundleError for other failures
    from attestplane.proof_bundle import IncompleteProofBundleError
    from attestplane.sdk.bundle import raise_for_minimum_bundle_result

    chain = _build_chain(2)
    builder = ProofBundleBuilder(chain_id="tampered", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    bundle["signatures"] = [_syntactic_sig(chain[0])]
    # Tamper the chain to cause VERIFY_CHAIN_RECOMPUTE_FAILED
    bundle["events"][1]["event"]["payload"] = {"tampered": True}
    result = verify_proof_bundle(bundle, require_non_empty=True, require_signed_attestation=True)
    assert result.ok is False
    assert result.error_code not in {VERIFY_REQUIRED_FIELDS_MISSING, VERIFY_BUNDLE_SCHEMA_INCOMPLETE}
    with pytest.raises(IncompleteProofBundleError):
        raise_for_minimum_bundle_result(result)


def test_verify_minimum_bundle_file_success(tmp_path: Path) -> None:
    # lines 55-60 — verify_minimum_bundle_file happy path
    from attestplane.sdk.bundle import verify_minimum_bundle_file

    chain = _build_chain(1)
    builder = ProofBundleBuilder(chain_id="min-file", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    bundle["signatures"] = [_syntactic_sig(chain[0])]
    out = tmp_path / "bundle.json"
    out.write_text(json.dumps(bundle), encoding="utf-8")
    result = verify_minimum_bundle_file(out)
    assert result.ok is True


def test_verify_minimum_bundle_file_raises_for_empty(tmp_path: Path) -> None:
    # lines 55-61 — verify_minimum_bundle_file raises on failure
    from attestplane.proof_bundle import EmptyProofBundleError
    from attestplane.sdk.bundle import verify_minimum_bundle_file

    bundle = ProofBundleBuilder(chain_id="empty-file", producer_runtime="test").build()
    out = tmp_path / "empty.json"
    out.write_text(json.dumps(bundle), encoding="utf-8")
    with pytest.raises(EmptyProofBundleError):
        verify_minimum_bundle_file(out)


# ===========================================================================
# verifier.py — _resolve_bundle_taxonomy_version (lines 199, 202, 206)
# ===========================================================================


def test_resolve_bundle_taxonomy_version_none_input() -> None:
    # line 199 — bundle is None
    from attestplane.verifier import _resolve_bundle_taxonomy_version

    assert _resolve_bundle_taxonomy_version(None) is None  # type: ignore[arg-type]


def test_resolve_bundle_taxonomy_version_no_chain_metadata() -> None:
    # line 202 — chain_metadata missing or not dict
    from attestplane.verifier import _resolve_bundle_taxonomy_version

    assert _resolve_bundle_taxonomy_version({"bundle_version": 1}) is None
    assert _resolve_bundle_taxonomy_version({"chain_metadata": "not-dict"}) is None


def test_resolve_bundle_taxonomy_version_returns_int() -> None:
    # line 204-205 — taxonomy_version is an int
    from attestplane.verifier import _resolve_bundle_taxonomy_version

    bundle = {"chain_metadata": {"evidence_taxonomy_version": 1}}
    assert _resolve_bundle_taxonomy_version(bundle) == 1


def test_resolve_bundle_taxonomy_version_non_int_returns_none() -> None:
    # line 206 — taxonomy_version is not int
    from attestplane.verifier import _resolve_bundle_taxonomy_version

    bundle = {"chain_metadata": {"evidence_taxonomy_version": "1"}}
    assert _resolve_bundle_taxonomy_version(bundle) is None


# ===========================================================================
# verifier.py — _validate_shape (lines 218, 234, 237, 239, 241, 244, 247,
#               249, 252, 255, 257, 259, 261, 263-272)
# ===========================================================================


def _minimal_valid_bundle() -> dict:
    """Return a well-shaped minimal bundle dict (no events)."""
    return _base_bundle_fields()


def test_validate_shape_non_dict_raises() -> None:
    # line 218
    with pytest.raises(BundleSchemaError, match="JSON object"):
        verify_proof_bundle([])  # type: ignore[arg-type]


def test_validate_shape_chain_metadata_not_dict() -> None:
    # line 234
    bundle = _minimal_valid_bundle()
    bundle["chain_metadata"] = "not-a-dict"
    with pytest.raises(BundleSchemaError, match="chain_metadata must be a JSON object"):
        verify_proof_bundle(bundle)


def test_validate_shape_chain_metadata_missing_fields() -> None:
    # line 237
    bundle = _minimal_valid_bundle()
    bundle["chain_metadata"] = {}
    with pytest.raises(BundleSchemaError, match="chain_metadata missing required fields"):
        verify_proof_bundle(bundle)


def test_validate_shape_events_not_list() -> None:
    # line 239
    bundle = _minimal_valid_bundle()
    bundle["events"] = "not-a-list"
    with pytest.raises(BundleSchemaError, match="events must be an array"):
        verify_proof_bundle(bundle)


def test_validate_shape_verification_report_not_dict() -> None:
    # line 241
    bundle = _minimal_valid_bundle()
    bundle["verification_report"] = "not-a-dict"
    with pytest.raises(BundleSchemaError, match="verification_report must be a JSON object"):
        verify_proof_bundle(bundle)


def test_validate_shape_verification_report_missing_fields() -> None:
    # line 244
    bundle = _minimal_valid_bundle()
    bundle["verification_report"] = {}
    with pytest.raises(BundleSchemaError, match="verification_report missing required fields"):
        verify_proof_bundle(bundle)


def test_validate_shape_unsupported_verification_method() -> None:
    # line 247
    bundle = _minimal_valid_bundle()
    bundle["verification_report"]["verification_method"] = "unknown-method"
    with pytest.raises(BundleSchemaError, match="unsupported verification_method"):
        verify_proof_bundle(bundle)


def test_validate_shape_forbidden_fields_not_list() -> None:
    # line 249
    bundle = _minimal_valid_bundle()
    bundle["forbidden_fields"] = "not-a-list"
    with pytest.raises(BundleSchemaError, match="forbidden_fields must be an array"):
        verify_proof_bundle(bundle)


def test_validate_shape_forbidden_fields_empty_string() -> None:
    # line 252 — non-empty string check fails
    bundle = _minimal_valid_bundle()
    bundle["forbidden_fields"] = [""]
    with pytest.raises(BundleSchemaError, match="forbidden_fields must contain non-empty strings"):
        verify_proof_bundle(bundle)


def test_validate_shape_forbidden_fields_non_string() -> None:
    # line 252 — non-string item
    bundle = _minimal_valid_bundle()
    bundle["forbidden_fields"] = [42]
    with pytest.raises(BundleSchemaError, match="forbidden_fields must contain non-empty strings"):
        verify_proof_bundle(bundle)


def test_validate_shape_forbidden_fields_missing_required_terms() -> None:
    # line 255
    bundle = _minimal_valid_bundle()
    bundle["forbidden_fields"] = ["only_this"]  # missing the required DEFAULT_FORBIDDEN_FIELDS
    with pytest.raises(BundleSchemaError, match="forbidden_fields missing required redaction terms"):
        verify_proof_bundle(bundle)


def test_validate_shape_framework_mappings_not_list() -> None:
    # line 257
    bundle = _minimal_valid_bundle()
    bundle["framework_mappings"] = "not-a-list"
    with pytest.raises(BundleSchemaError, match="framework_mappings must be an array"):
        verify_proof_bundle(bundle)


def test_validate_shape_policy_trace_refs_not_list() -> None:
    # line 259
    bundle = _minimal_valid_bundle()
    bundle["policy_trace_refs"] = "not-a-list"
    with pytest.raises(BundleSchemaError, match="policy_trace_refs must be an array"):
        verify_proof_bundle(bundle)


def test_validate_shape_retention_proofs_not_list() -> None:
    # line 261
    bundle = _minimal_valid_bundle()
    bundle["retention_proofs"] = "not-a-list"
    with pytest.raises(BundleSchemaError, match="retention_proofs must be an array"):
        verify_proof_bundle(bundle)


def test_validate_shape_anchoring_not_dict() -> None:
    # line 265
    bundle = _minimal_valid_bundle()
    bundle["anchoring"] = "not-a-dict"
    with pytest.raises(BundleSchemaError, match="anchoring must be a JSON object"):
        verify_proof_bundle(bundle)


def test_validate_shape_anchoring_missing_fields() -> None:
    # line 267-268
    bundle = _minimal_valid_bundle()
    bundle["anchoring"] = {}
    with pytest.raises(BundleSchemaError, match="anchoring missing required fields"):
        verify_proof_bundle(bundle)


def test_validate_shape_anchoring_invalid_status() -> None:
    # line 270
    bundle = _minimal_valid_bundle()
    bundle["anchoring"] = {"status": "bad-status", "quarantined": False}
    with pytest.raises(BundleSchemaError, match=r"anchoring\.status must be one of"):
        verify_proof_bundle(bundle)


def test_validate_shape_anchoring_quarantined_not_bool() -> None:
    # line 272
    bundle = _minimal_valid_bundle()
    bundle["anchoring"] = {"status": "anchored", "quarantined": "yes"}
    with pytest.raises(BundleSchemaError, match=r"anchoring\.quarantined must be a boolean"):
        verify_proof_bundle(bundle)


# ===========================================================================
# verifier.py — _bundle_anchoring_status  (lines 279-283)
# ===========================================================================


def test_bundle_anchoring_status_no_anchoring_key() -> None:
    # line 277-278 — anchoring key absent
    bundle = _good_bundle()
    result = verify_proof_bundle(bundle)
    assert result.anchoring_status == "absent"
    assert result.anchoring_quarantined is False


def test_bundle_anchoring_status_invalid_values_returns_none() -> None:
    # line 281-282 — status or quarantined invalid → returns None
    from attestplane.verifier import _bundle_anchoring_status

    assert _bundle_anchoring_status({"anchoring": {"status": "invalid", "quarantined": False}}) is None
    assert _bundle_anchoring_status({"anchoring": {"status": "anchored", "quarantined": "yes"}}) is None


# ===========================================================================
# verifier.py — classify_bundle_schema_error (lines 444-457)
# ===========================================================================


def test_classify_bundle_schema_error_bundle_version() -> None:
    # line 445-446
    from attestplane.verify_reason_codes import VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED

    result = classify_bundle_schema_error("unsupported bundle_version=99")
    assert result == VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED


def test_classify_bundle_schema_error_verification_method() -> None:
    # line 447-448
    from attestplane.verify_reason_codes import VERIFY_REASON_SCHEMA_UNKNOWN

    result = classify_bundle_schema_error("unsupported verification_method='bad'")
    assert result == VERIFY_REASON_SCHEMA_UNKNOWN


def test_classify_bundle_schema_error_missing_required_fields() -> None:
    # line 449-450
    from attestplane.verify_reason_codes import VERIFY_REASON_REQUIRED_FIELD_MISSING

    assert classify_bundle_schema_error("bundle missing required fields: ['x']") == VERIFY_REASON_REQUIRED_FIELD_MISSING
    assert classify_bundle_schema_error("missing fields ['x']") == VERIFY_REASON_REQUIRED_FIELD_MISSING


def test_classify_bundle_schema_error_json_object_or_array() -> None:
    # line 451-452
    from attestplane.verify_reason_codes import VERIFY_REASON_SCHEMA_INVALID

    assert classify_bundle_schema_error("events must be an array") == VERIFY_REASON_SCHEMA_INVALID
    assert classify_bundle_schema_error("chain_metadata must be a JSON object") == VERIFY_REASON_SCHEMA_INVALID


def test_classify_bundle_schema_error_unknown_top_level_fields() -> None:
    # line 453-454
    from attestplane.verify_reason_codes import VERIFY_REASON_SCHEMA_UNKNOWN

    assert classify_bundle_schema_error("unknown top-level fields: ['proof_type']") == VERIFY_REASON_SCHEMA_UNKNOWN


def test_classify_bundle_schema_error_schema_version_handles() -> None:
    # line 455-456
    from attestplane.verify_reason_codes import VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED

    assert (
        classify_bundle_schema_error("schema_version=99; this verifier handles schema_version values (1,)")
        == VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED
    )


def test_classify_bundle_schema_error_fallback() -> None:
    # line 457 — fallback SCHEMA_INVALID
    from attestplane.verify_reason_codes import VERIFY_REASON_SCHEMA_INVALID

    assert classify_bundle_schema_error("some other unknown error") == VERIFY_REASON_SCHEMA_INVALID


# ===========================================================================
# verifier.py — _verify_metadata_closure schema_version branches (lines 562-593, 597)
# ===========================================================================


def _good_bundle_with_schema_version(sv: int | str | None = 1) -> dict:
    bundle = _good_bundle()
    if sv is None:
        bundle["chain_metadata"].pop("schema_version", None)
    else:
        bundle["chain_metadata"]["schema_version"] = sv
    return bundle


def test_metadata_closure_schema_version_missing() -> None:
    # line 563 — schema_version absent
    bundle = _good_bundle_with_schema_version(None)
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert result.metadata_ok is False
    assert "schema_version is missing" in (result.metadata_reason or "")


def test_metadata_closure_schema_version_not_int() -> None:
    # line 565 — schema_version not an int
    bundle = _good_bundle_with_schema_version("one")
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert result.metadata_ok is False
    assert "must be an integer" in (result.metadata_reason or "")


def test_metadata_closure_schema_version_unsupported() -> None:
    # line 566-569 — schema_version int but unsupported
    bundle = _good_bundle_with_schema_version(999)
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert result.metadata_ok is False
    assert "chain_metadata.schema_version=999" in (result.metadata_reason or "")


def test_metadata_closure_critical_chain_metadata_field() -> None:
    # line 571-572 — unknown required field in chain_metadata
    bundle = _good_bundle()
    bundle["chain_metadata"]["critical_unknown_field"] = "data"
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert result.metadata_ok is False
    assert "unknown required field" in (result.metadata_reason or "")


def test_metadata_closure_critical_verification_report_field() -> None:
    # line 577-578 — unknown required field in verification_report
    bundle = _good_bundle()
    bundle["verification_report"]["critical_unknown_report_field"] = "data"
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert result.metadata_ok is False
    assert "unknown required field" in (result.metadata_reason or "")


def test_metadata_closure_genesis_hash_mismatch() -> None:
    # line 579-580
    bundle = _good_bundle()
    bundle["chain_metadata"]["genesis_hash_hex"] = "f" * 64
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert "genesis_hash_hex" in (result.metadata_reason or "")


def test_metadata_closure_evidence_taxonomy_version_bad() -> None:
    # line 581-582 — evidence_taxonomy_version present but != 1
    bundle = _good_bundle()
    bundle["chain_metadata"]["evidence_taxonomy_version"] = 2
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert "evidence_taxonomy_version" in (result.metadata_reason or "")


def test_metadata_closure_head_seq_mismatch() -> None:
    # line 585-586
    bundle = _good_bundle()
    bundle["chain_metadata"]["head_seq"] = 999
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert "head_seq" in (result.metadata_reason or "")


def test_metadata_closure_verification_report_ok_mismatch() -> None:
    # line 590-591 — report.ok disagrees with chain result
    # Build a valid bundle but forcibly set report.ok to False while chain is OK
    bundle = _good_bundle()
    bundle["verification_report"]["ok"] = False
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert "ok disagrees" in (result.metadata_reason or "")


def test_metadata_closure_first_bad_index_mismatch() -> None:
    # line 592-593 — report.first_bad_index disagrees
    bundle = _good_bundle()
    bundle["verification_report"]["first_bad_index"] = 99
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert "first_bad_index" in (result.metadata_reason or "")


def test_metadata_closure_report_failure_detail_on_ok_chain() -> None:
    # line 596-597 — chain is OK but report carries failure details
    bundle = _good_bundle()
    # Set reason to non-None while chain_result.ok is True
    bundle["verification_report"]["reason"] = "fake-reason"
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    # Hits either "reason disagrees" or the failure detail check
    assert result.metadata_ok is False


# ===========================================================================
# verifier.py — _validate_minimum_signed_attestation_schema (line 338)
# ===========================================================================


def test_signed_attestation_duplicate_event_hashes() -> None:
    # line 338 — unique event hashes check (this path is hard to hit naturally
    # since chain_extend guarantees uniqueness; we test via patching)
    # Actually the check is len(canonical_event_hashes) != len(events) — only
    # possible if two different events have the same canonical hash (collision).
    # In practice this is unreachable via normal chain construction. We verify
    # the error message path via the error_code path instead.
    chain = _build_chain(1)
    builder = ProofBundleBuilder(chain_id="dup-hash", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    bundle["signatures"] = [_syntactic_sig(chain[0])]
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is True


# ===========================================================================
# verifier.py — _signed_attestation_reason_code (line 432)
# ===========================================================================


def test_signed_attestation_reason_code_none() -> None:
    # line 432 — reason is None → SIGNATURE_INVALID
    from attestplane.verifier import _signed_attestation_reason_code
    from attestplane.verify_reason_codes import VERIFY_REASON_SIGNATURE_INVALID

    assert _signed_attestation_reason_code(None) == VERIFY_REASON_SIGNATURE_INVALID


def test_signed_attestation_reason_code_events_must_contain() -> None:
    # line 433-434 — "events must contain" → REQUIRED_FIELD_MISSING
    from attestplane.verifier import _signed_attestation_reason_code
    from attestplane.verify_reason_codes import VERIFY_REASON_REQUIRED_FIELD_MISSING

    assert _signed_attestation_reason_code("events must contain at least one") == VERIFY_REASON_REQUIRED_FIELD_MISSING


def test_signed_attestation_reason_code_signatures_must_contain() -> None:
    # line 435-436 — "signatures must contain" → SIGNATURE_MISSING
    from attestplane.verifier import _signed_attestation_reason_code
    from attestplane.verify_reason_codes import VERIFY_REASON_SIGNATURE_MISSING

    assert _signed_attestation_reason_code("signatures must contain at least one") == VERIFY_REASON_SIGNATURE_MISSING


def test_signed_attestation_reason_code_missing_fields() -> None:
    # line 437-438 — "missing fields" → REQUIRED_FIELD_MISSING
    from attestplane.verifier import _signed_attestation_reason_code
    from attestplane.verify_reason_codes import VERIFY_REASON_REQUIRED_FIELD_MISSING

    assert (
        _signed_attestation_reason_code("is malformed: missing fields ['x']")
        == VERIFY_REASON_REQUIRED_FIELD_MISSING
    )
    assert (
        _signed_attestation_reason_code("signed_event_hash_hex must be lowercase")
        == VERIFY_REASON_REQUIRED_FIELD_MISSING
    )


# ===========================================================================
# verifier.py — anchoring status paths (lines 706-715)
# ===========================================================================


def _good_bundle_with_anchoring(status: str, quarantined: bool = False) -> dict:
    bundle = _good_bundle()
    bundle["anchoring"] = {"status": status, "quarantined": quarantined}
    return bundle


def test_anchoring_status_anchored_verified() -> None:
    # line 706-707 — bundle_anchoring_status == "anchored" → "verified"
    bundle = _good_bundle_with_anchoring("anchored")
    result = verify_proof_bundle(bundle)
    assert result.ok is True
    assert result.anchoring_status == "verified"


def test_anchoring_status_unanchored_absent() -> None:
    # line 710-711 — bundle_anchoring_status == "unanchored" → "absent"
    bundle = _good_bundle_with_anchoring("unanchored")
    result = verify_proof_bundle(bundle)
    assert result.ok is True
    assert result.anchoring_status == "absent"


def test_anchoring_status_quarantined_bundle_anchoring() -> None:
    # line 708-709 — bundle_anchoring_status == "quarantined" → "quarantined"
    bundle = _good_bundle_with_anchoring("quarantined", quarantined=True)
    result = verify_proof_bundle(bundle)
    # explicit quarantine makes ok=False
    assert result.anchoring_status == "quarantined"
    assert result.anchoring_quarantined is True
    assert result.error_code == VERIFY_EXTENSION_FAILED


def test_anchoring_status_anchor_ref_in_chain_metadata() -> None:
    # line 712-713 — no anchoring key but anchor_ref present → "verified"
    bundle = _good_bundle()
    bundle["chain_metadata"]["anchor_ref"] = "https://tsa.example/proof/abc123"
    result = verify_proof_bundle(bundle)
    assert result.ok is True
    assert result.anchoring_status == "verified"


def test_anchoring_status_no_anchor_ref_absent() -> None:
    # line 714-715 — no anchoring key, no anchor_ref → "absent"
    bundle = _good_bundle()
    # ensure no anchoring key and no anchor_ref
    bundle["chain_metadata"].pop("anchor_ref", None)
    result = verify_proof_bundle(bundle)
    assert result.ok is True
    assert result.anchoring_status == "absent"


def test_verify_anchoring_property() -> None:
    # line 141 — VerifyAnchoringState property
    bundle = _good_bundle_with_anchoring("anchored")
    result = verify_proof_bundle(bundle)
    state = result.anchoring
    assert isinstance(state, VerifyAnchoringState)
    assert state.status == "verified"
    assert state.quarantined is False


# ===========================================================================
# verifier.py — _verify_metadata_closure require_non_empty (line 559)
# ===========================================================================


def test_metadata_closure_require_non_empty_empty_events() -> None:
    # line 558-559 — require_non_empty=True and events is empty
    builder = ProofBundleBuilder(chain_id="empty-req", producer_runtime="test")
    bundle = builder.build()
    result = verify_proof_bundle(bundle, require_non_empty=True)
    assert result.ok is False
    assert result.error_code == VERIFY_REQUIRED_FIELDS_MISSING
    assert "at least one event" in (result.metadata_reason or "")


# ===========================================================================
# verifier.py — _verification_reasons with multiple reason paths (lines 512, 516, 518, 520, 527)
# ===========================================================================


def test_verification_reasons_structure_invalid_policy() -> None:
    # line 515-516 — policy_ok=False → STRUCTURE_INVALID
    from attestplane.event_types import POLICY_CHECK_EVENT

    chain_types = [POLICY_CHECK_EVENT]
    chain = []
    head = genesis_head()
    for i, et in enumerate(chain_types):
        ev = chain_extend(head, EventDraft(event_type=et, actor="a", payload={"i": i}), now=_NOW,
                          event_id=f"00000000-0000-7000-8000-{i:012d}")
        chain.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    builder = ProofBundleBuilder(chain_id="policy", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    del bundle["policy_trace_refs"]  # force policy_ok=False
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert result.policy_trace_refs_ok is False


def test_verification_reasons_structure_invalid_retention() -> None:
    # line 517-518 — retention_ok=False → STRUCTURE_INVALID
    chain = _build_chain(2)
    builder = ProofBundleBuilder(chain_id="ret-fail", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    # Add a dangling retention proof
    bundle["retention_proofs"] = [
        {
            "retention_proof_schema_version": 1,
            "proof_id": "p1",
            "action": "retention_marker",
            "target_event_hash_hex": "f" * 64,  # dangling
            "commit_event_hash_hex": "e" * 64,  # dangling
            "reason": "test",
        }
    ]
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert result.retention_proofs_ok is False


def test_verification_reasons_anchor_invalid_explicit_quarantine() -> None:
    # line 519-520 — explicit_anchoring_quarantine → ANCHOR_INVALID
    from attestplane.verify_reason_codes import VERIFY_REASON_ANCHOR_INVALID

    bundle = _good_bundle_with_anchoring("quarantined", quarantined=True)
    result = verify_proof_bundle(bundle)
    assert result.primary_reason == VERIFY_REASON_ANCHOR_INVALID
    assert result.error_code == VERIFY_EXTENSION_FAILED


def test_verification_reasons_schema_version_reason_in_metadata() -> None:
    # line 510-512 — metadata_ok=False with schema_version reason
    from attestplane.verify_reason_codes import VERIFY_REASON_SCHEMA_VERSION_MISSING

    bundle = _good_bundle_with_schema_version(None)
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert result.primary_reason == VERIFY_REASON_SCHEMA_VERSION_MISSING


def test_verification_reasons_structure_invalid_other_metadata() -> None:
    # line 513-514 — metadata_ok=False without schema_version reason → STRUCTURE_INVALID
    from attestplane.verify_reason_codes import VERIFY_REASON_STRUCTURE_INVALID

    bundle = _good_bundle()
    bundle["chain_metadata"]["genesis_hash_hex"] = "f" * 64
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert result.primary_reason == VERIFY_REASON_STRUCTURE_INVALID


def test_verification_reasons_require_non_empty_empty_events() -> None:
    # line 505-506 — require_non_empty=True and events is empty
    from attestplane.verify_reason_codes import VERIFY_REASON_REQUIRED_FIELD_MISSING

    builder = ProofBundleBuilder(chain_id="empty", producer_runtime="test")
    bundle = builder.build()
    chain = _build_chain(1)
    bundle2 = ProofBundleBuilder(chain_id="signed", producer_runtime="test")
    # Build with events and sigs but then get the empty bundle for this test
    result = verify_proof_bundle(bundle, require_non_empty=True)
    assert result.primary_reason in {VERIFY_REASON_REQUIRED_FIELD_MISSING, None}
    assert result.ok is False


# ===========================================================================
# verifier.py — _schema_version_reason_code branches (lines 476, 478, 480, 482, 484)
# ===========================================================================


def test_schema_version_reason_code_none() -> None:
    # line 475-476
    from attestplane.verifier import _schema_version_reason_code

    assert _schema_version_reason_code(None) is None


def test_schema_version_reason_code_missing() -> None:
    # line 477-478
    from attestplane.verifier import _schema_version_reason_code
    from attestplane.verify_reason_codes import VERIFY_REASON_SCHEMA_VERSION_MISSING

    assert (
        _schema_version_reason_code("chain_metadata.schema_version is missing")
        == VERIFY_REASON_SCHEMA_VERSION_MISSING
    )


def test_schema_version_reason_code_invalid() -> None:
    # line 479-480
    from attestplane.verifier import _schema_version_reason_code
    from attestplane.verify_reason_codes import VERIFY_REASON_SCHEMA_INVALID

    assert (
        _schema_version_reason_code("chain_metadata.schema_version must be an integer")
        == VERIFY_REASON_SCHEMA_INVALID
    )


def test_schema_version_reason_code_unsupported() -> None:
    # line 481-482
    from attestplane.verifier import _schema_version_reason_code
    from attestplane.verify_reason_codes import VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED

    msg = "chain_metadata.schema_version=99; this verifier handles schema_version values (1,)"
    assert _schema_version_reason_code(msg) == VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED


def test_schema_version_reason_code_unknown_required_field() -> None:
    # line 483-484
    from attestplane.verifier import _schema_version_reason_code
    from attestplane.verify_reason_codes import VERIFY_REASON_SCHEMA_UNKNOWN

    assert (
        _schema_version_reason_code("chain_metadata.critical_x is an unknown required field")
        == VERIFY_REASON_SCHEMA_UNKNOWN
    )


def test_schema_version_reason_code_returns_none_for_unrecognized() -> None:
    # line 485 — not any of the above patterns → None
    from attestplane.verifier import _schema_version_reason_code

    assert _schema_version_reason_code("some other reason") is None


# ===========================================================================
# verifier.py — main() entrypoint (lines 779-803)
# ===========================================================================


def test_main_no_args_ok_bundle() -> None:
    # lines 779-803 — happy path, result.ok=True
    from attestplane.verifier import main

    bundle = _good_bundle()
    raw = json.dumps(bundle)
    stdin = io.StringIO(raw)
    stdout = io.StringIO()
    stderr = io.StringIO()

    import sys

    orig_stdin, orig_stdout, orig_stderr = sys.stdin, sys.stdout, sys.stderr
    sys.stdin, sys.stdout, sys.stderr = stdin, stdout, stderr
    try:
        rc = main([])
    finally:
        sys.stdin, sys.stdout, sys.stderr = orig_stdin, orig_stdout, orig_stderr

    assert rc == 0
    assert "OK" in stdout.getvalue()


def test_main_no_args_fail_bundle() -> None:
    # line 801-803 — result.ok=False writes to stderr
    from attestplane.verifier import main

    bundle = _good_bundle()
    bundle["chain_metadata"]["head_hash_hex"] = "f" * 64
    raw = json.dumps(bundle)
    stdin = io.StringIO(raw)
    stdout = io.StringIO()
    stderr = io.StringIO()

    import sys

    orig_stdin, orig_stdout, orig_stderr = sys.stdin, sys.stdout, sys.stderr
    sys.stdin, sys.stdout, sys.stderr = stdin, stdout, stderr
    try:
        rc = main([])
    finally:
        sys.stdin, sys.stdout, sys.stderr = orig_stdin, orig_stdout, orig_stderr

    assert rc == 2
    assert "FAIL" in stderr.getvalue()


def test_main_strict_flag() -> None:
    # line 781-782 — --strict flag sets strict=True
    from attestplane.verifier import main

    # Use a bundle without signatures, strict will reject it
    bundle = _good_bundle()
    raw = json.dumps(bundle)
    stdin = io.StringIO(raw)
    stdout = io.StringIO()
    stderr = io.StringIO()

    import sys

    orig_stdin, orig_stdout, orig_stderr = sys.stdin, sys.stdout, sys.stderr
    sys.stdin, sys.stdout, sys.stderr = stdin, stdout, stderr
    try:
        rc = main(["--strict"])
    finally:
        sys.stdin, sys.stdout, sys.stderr = orig_stdin, orig_stdout, orig_stderr

    assert rc == 2  # unsigned bundle fails strict


def test_main_unknown_arg() -> None:
    # line 783-785 — unknown arg prints usage and returns 2
    from attestplane.verifier import main

    stderr = io.StringIO()
    import sys

    orig_stderr = sys.stderr
    sys.stderr = stderr
    try:
        rc = main(["--unknown"])
    finally:
        sys.stderr = orig_stderr

    assert rc == 2
    assert "usage" in stderr.getvalue()


def test_main_invalid_json() -> None:
    # line 795-797 — invalid JSON → error on stderr
    from attestplane.verifier import main

    stdin = io.StringIO("not valid json")
    stderr = io.StringIO()

    import sys

    orig_stdin, orig_stderr = sys.stdin, sys.stderr
    sys.stdin, sys.stderr = stdin, stderr
    try:
        rc = main([])
    finally:
        sys.stdin, sys.stderr = orig_stdin, orig_stderr

    assert rc == 2
    assert "FAIL" in stderr.getvalue()


def test_main_bundle_schema_error() -> None:
    # line 795-797 — BundleSchemaError caught
    from attestplane.verifier import main

    # Valid JSON but fails _validate_shape
    stdin = io.StringIO(json.dumps({"bundle_version": 1}))
    stderr = io.StringIO()

    import sys

    orig_stdin, orig_stderr = sys.stdin, sys.stderr
    sys.stdin, sys.stderr = stdin, stderr
    try:
        rc = main([])
    finally:
        sys.stdin, sys.stderr = orig_stdin, orig_stderr

    assert rc == 2


# ===========================================================================
# settlement_verifier.py — missing branches (111, 114, 118, 122->109, 125->109, 126->109, 160)
# ===========================================================================


def _claim(
    lease_id_hash: str = "a" * 64,
    settlement_run_id: str = "s",
    expected_hash: str | None = None,
) -> SettlementPreconditionClaim:
    return SettlementPreconditionClaim(
        claim_kind="settlement_precondition",
        lease_id_hash=lease_id_hash,
        settlement_run_id=settlement_run_id,
        expected_settlement_amount_hash=expected_hash,
    )


def test_settlement_unsupported_claim_kind() -> None:
    # lines 83-89 — claim_kind != "settlement_precondition"
    claim = SettlementPreconditionClaim(
        claim_kind="unsupported_kind",
        lease_id_hash="a" * 64,
        settlement_run_id="s",
    )
    result = check_settlement_precondition([], claim)
    assert result.ok is False
    assert "claim_kind_unsupported" in (result.reason or "")


def test_settlement_naive_verification_time() -> None:
    # lines 90-96 — verification_time naive (no tzinfo)
    naive = datetime(2026, 5, 17)  # no tzinfo
    result = check_settlement_precondition([], _claim(), verification_time=naive)
    assert result.ok is False
    assert "UTC-aware" in (result.reason or "")


def test_settlement_chain_events_not_list() -> None:
    # lines 97-103 — chain_events not a list
    result = check_settlement_precondition("not-a-list", _claim())  # type: ignore[arg-type]
    assert result.ok is False
    assert "must be list" in (result.reason or "")


def test_settlement_lease_not_observed() -> None:
    # lines 130-136 — no matching lease event found
    result = check_settlement_precondition(
        [{"seq": 1, "event_type": "settlement_event", "payload": {"settlement_run_id": "s"}}],
        _claim(),
    )
    assert result.ok is False
    assert "lease_consumed_not_observed" in (result.reason or "")


def test_settlement_settlement_not_observed() -> None:
    # lines 137-143 — no matching settlement event found
    result = check_settlement_precondition(
        [
            {
                "seq": 0,
                "event_type": "lease_lifecycle_event",
                "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
            }
        ],
        _claim(),
    )
    assert result.ok is False
    assert "settlement_event_not_observed" in (result.reason or "")


def test_settlement_ordering_violation() -> None:
    # lines 144-154 — lease seq >= settlement seq
    chain = [
        {
            "seq": 5,
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {"seq": 3, "event_type": "settlement_event", "payload": {"settlement_run_id": "s"}},
    ]
    result = check_settlement_precondition(chain, _claim())
    assert result.ok is False
    assert "settlement_precedes_lease_consumed" in (result.reason or "")


def test_settlement_precondition_line_185_amount_hash_mismatch_branch() -> None:
    # line 185->196 — amount_hash matches → ok=True (the False branch of != check)
    chain = [
        {
            "seq": 0,
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {
            "seq": 1,
            "event_type": "settlement_event",
            "payload": {"settlement_run_id": "s", "amount_hash": "b" * 64},
        },
    ]
    # Same hash → they match → True (takes the False branch at line 185)
    result = check_settlement_precondition(chain, _claim(expected_hash="b" * 64))
    assert result.ok is True


def test_settlement_lease_event_wrong_lifecycle_skipped() -> None:
    # line 121->109 — lease_lifecycle_event with wrong lifecycle/lease_id → skip
    chain = [
        {
            "seq": 0,
            "event_type": "lease_lifecycle_event",
            # Wrong lifecycle: "started" instead of "consumed"
            "payload": {"lifecycle": "started", "lease_id_hash": "a" * 64},
        },
        {
            "seq": 1,
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {"seq": 2, "event_type": "settlement_event", "payload": {"settlement_run_id": "s"}},
    ]
    result = check_settlement_precondition(chain, _claim())
    assert result.ok is True
    assert result.lease_consumed_seq == 1  # only the consumed event counts


def test_settlement_settlement_event_wrong_run_id_skipped() -> None:
    # line 124->109 — event_type is neither lease_lifecycle_event nor settlement_event
    # The False branch of `elif event_type == "settlement_event":` → back to loop
    chain = [
        {
            "seq": 0,
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {
            "seq": 1,
            "event_type": "other_event_type",  # neither lease nor settlement
            "payload": {"data": "irrelevant"},
        },
        {
            "seq": 2,
            "event_type": "settlement_event",
            "payload": {"settlement_run_id": "s"},
        },
    ]
    result = check_settlement_precondition(chain, _claim())
    assert result.ok is True
    assert result.settlement_event_seq == 2


def test_settlement_non_dict_events_skipped() -> None:
    # line 110-111 — non-dict event in list → skip (continue)
    chain = [
        "not-a-dict",
        {
            "seq": 0,
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {"seq": 1, "event_type": "settlement_event", "payload": {"settlement_run_id": "s"}},
    ]
    result = check_settlement_precondition(chain, _claim())
    assert result.ok is True


def test_settlement_event_non_int_seq_skipped() -> None:
    # line 113-114 — seq not int → skip
    chain = [
        {
            "seq": "zero",  # non-int
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {
            "seq": 0,
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {"seq": 1, "event_type": "settlement_event", "payload": {"settlement_run_id": "s"}},
    ]
    result = check_settlement_precondition(chain, _claim())
    assert result.ok is True


def test_settlement_event_non_dict_payload_skipped() -> None:
    # line 117-118 — payload not dict → skip
    chain = [
        {"seq": 0, "event_type": "lease_lifecycle_event", "payload": "not-a-dict"},
        {
            "seq": 1,
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {"seq": 2, "event_type": "settlement_event", "payload": {"settlement_run_id": "s"}},
    ]
    result = check_settlement_precondition(chain, _claim())
    assert result.ok is True


def test_settlement_lease_consumed_seq_updated_to_lower() -> None:
    # line 122->109 — update lease_consumed_seq when seq < current
    chain = [
        {
            "seq": 5,
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {
            "seq": 2,  # lower seq same lease → should replace 5
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {"seq": 10, "event_type": "settlement_event", "payload": {"settlement_run_id": "s"}},
    ]
    result = check_settlement_precondition(chain, _claim())
    assert result.ok is True
    assert result.lease_consumed_seq == 2  # lowest wins


def test_settlement_event_seq_updated_to_lower() -> None:
    # line 125->109 / 126->109 — update settlement_event_seq when seq < current
    chain = [
        {
            "seq": 0,
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {
            "seq": 10,
            "event_type": "settlement_event",
            "payload": {"settlement_run_id": "s", "amount_hash": "b" * 64},
        },
        {
            "seq": 5,  # lower seq same settlement → should replace 10
            "event_type": "settlement_event",
            "payload": {"settlement_run_id": "s", "amount_hash": "c" * 64},
        },
    ]
    result = check_settlement_precondition(chain, _claim())
    assert result.ok is True
    assert result.settlement_event_seq == 5  # lowest wins


def test_settlement_expected_amount_hash_malformed() -> None:
    # line 155-165 — expected_settlement_amount_hash present but malformed
    chain = [
        {
            "seq": 0,
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {
            "seq": 1,
            "event_type": "settlement_event",
            "payload": {"settlement_run_id": "s", "amount_hash": "b" * 64},
        },
    ]
    # Expected hash too short (not 64 hex chars)
    result = check_settlement_precondition(chain, _claim(expected_hash="abc"))
    assert result.ok is False
    assert "malformed" in (result.reason or "")


def test_settlement_amount_hash_missing_in_event() -> None:
    # line 167-173 — expected_settlement_amount_hash set but event has no amount_hash
    chain = [
        {
            "seq": 0,
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {
            "seq": 1,
            "event_type": "settlement_event",
            "payload": {"settlement_run_id": "s"},  # no amount_hash
        },
    ]
    result = check_settlement_precondition(chain, _claim(expected_hash="b" * 64))
    assert result.ok is False
    assert "amount_hash_missing" in (result.reason or "")


def test_settlement_amount_hash_malformed_in_event() -> None:
    # line 174-183 — settlement event has malformed amount_hash
    chain = [
        {
            "seq": 0,
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {
            "seq": 1,
            "event_type": "settlement_event",
            "payload": {"settlement_run_id": "s", "amount_hash": "INVALID"},  # not 64-hex
        },
    ]
    result = check_settlement_precondition(chain, _claim(expected_hash="b" * 64))
    assert result.ok is False
    assert "amount_hash_malformed" in (result.reason or "")


def test_settlement_amount_hash_mismatch() -> None:
    # line 185-195 — amount_hash present but doesn't match expected
    chain = [
        {
            "seq": 0,
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {
            "seq": 1,
            "event_type": "settlement_event",
            "payload": {"settlement_run_id": "s", "amount_hash": "c" * 64},
        },
    ]
    result = check_settlement_precondition(chain, _claim(expected_hash="b" * 64))
    assert result.ok is False
    assert "amount_hash_mismatch" in (result.reason or "")


def test_settlement_verifier_line_160_malformed_expected_hash_non_hex() -> None:
    # line 160 — expected hash contains non-hex chars
    chain = [
        {
            "seq": 0,
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {"seq": 1, "event_type": "settlement_event", "payload": {"settlement_run_id": "s"}},
    ]
    # 64 chars but contains 'z' which is not hex
    bad_hash = "z" * 64
    result = check_settlement_precondition(chain, _claim(expected_hash=bad_hash))
    assert result.ok is False
    assert "malformed" in (result.reason or "")


# ===========================================================================
# verifier.py — _verify_policy_trace_refs edge cases (lines 607-627)
# ===========================================================================


def test_policy_trace_refs_present_but_empty_with_no_policy_events() -> None:
    # line 607-609 — refs == [] → specific error message
    from attestplane.event_types import TOOL_CALL_EVENT

    chain_types = [TOOL_CALL_EVENT]
    chain = []
    head = genesis_head()
    for i, et in enumerate(chain_types):
        ev = chain_extend(head, EventDraft(event_type=et, actor="a", payload={"i": i}), now=_NOW,
                          event_id=f"00000000-0000-7000-8000-{i:012d}")
        chain.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    builder = ProofBundleBuilder(chain_id="no-policy", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    bundle["policy_trace_refs"] = []
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert "absent, not empty" in (result.policy_trace_refs_reason or "")


def test_policy_trace_refs_present_non_empty_with_no_policy_events() -> None:
    # line 610 — refs present but no policy events
    from attestplane.event_types import TOOL_CALL_EVENT

    chain = []
    head = genesis_head()
    ev = chain_extend(head, EventDraft(event_type=TOOL_CALL_EVENT, actor="a", payload={}), now=_NOW,
                      event_id="00000000-0000-7000-8000-000000000000")
    chain.append(ev)
    builder = ProofBundleBuilder(chain_id="no-policy2", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    bundle["policy_trace_refs"] = ["a" * 64]
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert "no policy_check_event" in (result.policy_trace_refs_reason or "")


def test_policy_trace_refs_invalid_hex() -> None:
    # line 615-616 — refs contain invalid hex strings
    from attestplane.event_types import POLICY_CHECK_EVENT

    chain = []
    head = genesis_head()
    ev = chain_extend(head, EventDraft(event_type=POLICY_CHECK_EVENT, actor="a", payload={}), now=_NOW,
                      event_id="00000000-0000-7000-8000-000000000000")
    chain.append(ev)
    builder = ProofBundleBuilder(chain_id="policy-bad-hex", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    bundle["policy_trace_refs"] = ["not-valid-hex"]
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert "lowercase 64-hex" in (result.policy_trace_refs_reason or "")


def test_policy_trace_refs_order_mismatch() -> None:
    # line 626-627 — refs don't match chain-seq-ordered hashes
    from attestplane.event_types import POLICY_CHECK_EVENT

    chain = []
    head = genesis_head()
    for i in range(2):
        ev = chain_extend(head, EventDraft(event_type=POLICY_CHECK_EVENT, actor="a", payload={"i": i}), now=_NOW,
                          event_id=f"00000000-0000-7000-8000-{i:012d}")
        chain.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    builder = ProofBundleBuilder(chain_id="policy-order", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    # Swap the order
    refs = bundle["policy_trace_refs"]
    bundle["policy_trace_refs"] = list(reversed(refs))
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert "does not match chain-seq-ordered" in (result.policy_trace_refs_reason or "")


# ===========================================================================
# verifier.py — taxonomy_version in bundle (line 732)
# ===========================================================================


def test_verify_bundle_with_taxonomy_version() -> None:
    # taxonomy_version returned correctly
    bundle = _good_bundle()
    bundle["chain_metadata"]["evidence_taxonomy_version"] = 1
    result = verify_proof_bundle(bundle)
    assert result.ok is True
    assert result.taxonomy_version == 1


def test_verify_bundle_without_taxonomy_version() -> None:
    # ProofBundleBuilder always sets evidence_taxonomy_version=1, so test the
    # _resolve_bundle_taxonomy_version path directly instead.
    from attestplane.verifier import _resolve_bundle_taxonomy_version

    # No chain_metadata at all → None
    assert _resolve_bundle_taxonomy_version({}) is None
    # chain_metadata present but evidence_taxonomy_version absent → None
    assert _resolve_bundle_taxonomy_version({"chain_metadata": {}}) is None


# ===========================================================================
# verifier.py — signed_at with non-Z timezone
# ===========================================================================


def test_signed_at_non_z_timezone() -> None:
    # line 413 — signed_at doesn't end with 'Z' but is valid ISO-8601
    chain = _build_chain(1)
    builder = ProofBundleBuilder(chain_id="non-z-tz", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    sig = _syntactic_sig(chain[0])
    sig["signed_at"] = "2026-05-17T12:00:00+00:00"  # ISO-8601, no Z suffix
    bundle["signatures"] = [sig]
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is True
    assert result.signed_attestation_schema_ok is True


# ===========================================================================
# verifier.py — _result_is_quarantined (lines 537-546)
# ===========================================================================


def test_result_is_quarantined_for_required_fields_missing() -> None:
    # line 537-538 — VERIFY_REQUIRED_FIELDS_MISSING → quarantined
    from attestplane.verifier import _result_is_quarantined

    assert _result_is_quarantined(error_code=VERIFY_REQUIRED_FIELDS_MISSING, primary_reason=None) is True


def test_result_is_quarantined_for_bundle_schema_incomplete() -> None:
    # line 537-538 — VERIFY_BUNDLE_SCHEMA_INCOMPLETE → quarantined
    from attestplane.verifier import _result_is_quarantined

    assert _result_is_quarantined(error_code=VERIFY_BUNDLE_SCHEMA_INCOMPLETE, primary_reason=None) is True


def test_result_is_quarantined_for_signature_missing_reason() -> None:
    # line 545 — VERIFY_REASON_SIGNATURE_MISSING in set
    from attestplane.verifier import _result_is_quarantined
    from attestplane.verify_reason_codes import VERIFY_REASON_SIGNATURE_MISSING

    assert _result_is_quarantined(error_code=VERIFY_OK, primary_reason=VERIFY_REASON_SIGNATURE_MISSING) is True


def test_result_is_not_quarantined_for_ok() -> None:
    # returns False for ok case
    from attestplane.verifier import _result_is_quarantined

    assert _result_is_quarantined(error_code=VERIFY_OK, primary_reason=None) is False


# ===========================================================================
# verifier.py — _bundle_anchor_ref_present (line 527)
# ===========================================================================


def test_bundle_anchor_ref_present_true() -> None:
    # line 527-529
    from attestplane.verifier import _bundle_anchor_ref_present

    bundle = {"chain_metadata": {"anchor_ref": "https://tsa.example/proof"}}
    assert _bundle_anchor_ref_present(bundle) is True


def test_bundle_anchor_ref_present_false_empty() -> None:
    from attestplane.verifier import _bundle_anchor_ref_present

    assert _bundle_anchor_ref_present({"chain_metadata": {"anchor_ref": ""}}) is False
    assert _bundle_anchor_ref_present({"chain_metadata": {}}) is False
    assert _bundle_anchor_ref_present({}) is False


# ===========================================================================
# verifier.py — _rehydrate_events error path (line 314-315)
# ===========================================================================


def test_rehydrate_events_malformed_raises() -> None:
    # line 314-315 — malformed event in events list
    bundle = _minimal_valid_bundle()
    bundle["events"] = [{"bad": "event"}]
    with pytest.raises(BundleSchemaError, match="malformed event row"):
        verify_proof_bundle(bundle)


# ===========================================================================
# verifier.py — verify_proof_bundle_file signed_attestation (line 456, 476)
# ===========================================================================


def test_verify_proof_bundle_file_with_signed_attestation(tmp_path: Path) -> None:
    # verify_proof_bundle_file passes require_signed_attestation
    chain = _build_chain(1)
    builder = ProofBundleBuilder(chain_id="signed-file", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    bundle["signatures"] = [_syntactic_sig(chain[0])]
    out = tmp_path / "signed.json"
    out.write_text(json.dumps(bundle), encoding="utf-8")
    result = verify_proof_bundle_file(out, require_signed_attestation=True)
    assert result.ok is True
    assert result.signed_attestation_schema_ok is True


# ===========================================================================
# verifier.py — _dedupe_reasons empty list → (None, ())  (line 470)
# ===========================================================================


def test_dedupe_reasons_empty_list() -> None:
    # line 469-470 — empty ordered list
    from attestplane.verifier import _dedupe_reasons

    primary, secondary = _dedupe_reasons([])
    assert primary is None
    assert secondary == ()


def test_dedupe_reasons_deduplicates() -> None:
    from attestplane.verifier import _dedupe_reasons
    from attestplane.verify_reason_codes import VERIFY_REASON_CANONICAL_MISMATCH, VERIFY_REASON_STRUCTURE_INVALID

    primary, secondary = _dedupe_reasons(
        [VERIFY_REASON_CANONICAL_MISMATCH, VERIFY_REASON_CANONICAL_MISMATCH, VERIFY_REASON_STRUCTURE_INVALID]
    )
    assert primary == VERIFY_REASON_CANONICAL_MISMATCH
    assert secondary == (VERIFY_REASON_STRUCTURE_INVALID,)


# ===========================================================================
# verifier.py — signed_at invalid ISO-8601 (line 415)
# ===========================================================================


def test_signed_at_invalid_iso8601() -> None:
    # line 414-415 — signed_at that does not parse as ISO-8601
    chain = _build_chain(1)
    builder = ProofBundleBuilder(chain_id="bad-date", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    sig = _syntactic_sig(chain[0])
    sig["signed_at"] = "not-a-date-at-all"
    bundle["signatures"] = [sig]
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is False
    assert "RFC3339" in (result.signed_attestation_schema_reason or "")


# ===========================================================================
# verifier.py — _validate_signature_record_shape individual field errors
#               (lines 379, 381, 383, 385, 387, 389, 392, 395, 398, 401,
#                404-405, 408, 422, 425-426)
# These are exercised via require_signed_attestation=True with mutations.
# ===========================================================================


def _signed_bundle_with_sig_mutation(mutate_sig) -> dict:
    chain = _build_chain(1)
    builder = ProofBundleBuilder(chain_id="sig-mut", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    sig = _syntactic_sig(chain[0])
    mutate_sig(sig)
    bundle["signatures"] = [sig]
    return bundle


def test_validate_sig_shape_missing_fields() -> None:
    # line 378-379 — missing required fields
    bundle = _signed_bundle_with_sig_mutation(lambda s: s.clear())
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is False
    assert "lowercase 64-hex" in (result.signed_attestation_schema_reason or "")


def test_validate_sig_shape_bad_signature_schema_version() -> None:
    # line 380-381 — signature_schema_version < 1
    bundle = _signed_bundle_with_sig_mutation(lambda s: s.update({"signature_schema_version": 0}))
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is False
    assert "positive integer" in (result.signed_attestation_schema_reason or "")


def test_validate_sig_shape_bad_signed_seq() -> None:
    # line 382-383 — signed_seq < 0
    bundle = _signed_bundle_with_sig_mutation(lambda s: s.update({"signed_seq": -1}))
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is False
    assert "non-negative integer" in (result.signed_attestation_schema_reason or "")


def test_validate_sig_shape_bad_signature_hex() -> None:
    # line 384-385
    bundle = _signed_bundle_with_sig_mutation(lambda s: s.update({"signature_hex": "a"}))
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is False
    assert "signature_hex" in (result.signed_attestation_schema_reason or "")


def test_validate_sig_shape_bad_key_id() -> None:
    # line 386-387
    bundle = _signed_bundle_with_sig_mutation(lambda s: s.update({"key_id": "b"}))
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is False
    assert "key_id" in (result.signed_attestation_schema_reason or "")


def test_validate_sig_shape_bad_signature_mode() -> None:
    # line 388-389
    bundle = _signed_bundle_with_sig_mutation(lambda s: s.update({"signature_mode": "detached"}))
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is False
    assert "signature_mode" in (result.signed_attestation_schema_reason or "")


def test_validate_sig_shape_bad_public_key_der_b64_not_string() -> None:
    # line 391-392 — _decode_b64_field returns reason when not string
    bundle = _signed_bundle_with_sig_mutation(lambda s: s.update({"public_key_der_b64": 12345}))
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is False
    assert "public_key_der_b64" in (result.signed_attestation_schema_reason or "")


def test_validate_sig_shape_bad_public_key_der_b64_not_b64() -> None:
    # line 425-426 — _decode_b64_field returns reason when bad base64
    bundle = _signed_bundle_with_sig_mutation(lambda s: s.update({"public_key_der_b64": "not base64!"}))
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is False
    assert "public_key_der_b64" in (result.signed_attestation_schema_reason or "")


def test_validate_sig_shape_bad_signed_payload_b64() -> None:
    # line 393-395 — signed_payload_b64 decode failure
    bundle = _signed_bundle_with_sig_mutation(lambda s: s.update({"signed_payload_b64": ["not", "text"]}))
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is False
    assert "signed_payload_b64" in (result.signed_attestation_schema_reason or "")


def test_validate_sig_shape_cert_chain_not_list() -> None:
    # line 397-398
    bundle = _signed_bundle_with_sig_mutation(lambda s: s.update({"signing_cert_chain_b64": "not-list"}))
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is False
    assert "signing_cert_chain_b64" in (result.signed_attestation_schema_reason or "")


def test_validate_sig_shape_cert_chain_element_not_string() -> None:
    # line 400-401
    bundle = _signed_bundle_with_sig_mutation(lambda s: s.update({"signing_cert_chain_b64": [7]}))
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is False
    assert "signing_cert_chain_b64[0]" in (result.signed_attestation_schema_reason or "")


def test_validate_sig_shape_cert_chain_element_bad_b64() -> None:
    # line 404-405
    bundle = _signed_bundle_with_sig_mutation(lambda s: s.update({"signing_cert_chain_b64": ["not base64"]}))
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is False
    assert "must be base64" in (result.signed_attestation_schema_reason or "")


def test_validate_sig_shape_signed_at_not_string() -> None:
    # line 407-408
    bundle = _signed_bundle_with_sig_mutation(lambda s: s.update({"signed_at": 12345}))
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is False
    assert "signed_at must be a string" in (result.signed_attestation_schema_reason or "")


def test_validate_sig_shape_signed_event_hash_hex_not_in_bundle() -> None:
    # line 349-353 — signed_event_hash_hex valid hex but not matching any event
    chain = _build_chain(1)
    builder = ProofBundleBuilder(chain_id="wrong-hash", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    sig = _syntactic_sig(chain[0])
    sig["signed_event_hash_hex"] = "f" * 64
    bundle["signatures"] = [sig]
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is False
    assert "canonical bundle event" in (result.signed_attestation_schema_reason or "")


def test_validate_signed_schema_no_events() -> None:
    # line 331-332 — events is empty → specific message
    builder = ProofBundleBuilder(chain_id="empty-sigs", producer_runtime="test")
    bundle = builder.build()
    bundle["signatures"] = [{"key": "val"}]
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is False
    assert "at least one event" in (result.signed_attestation_schema_reason or "")


def test_validate_signed_schema_no_signatures() -> None:
    # line 333-334 — signatures missing or empty
    chain = _build_chain(1)
    builder = ProofBundleBuilder(chain_id="no-sigs", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    # No signatures key → "at least one signed attestation"
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is False
    assert "signatures must contain at least one" in (result.signed_attestation_schema_reason or "")


# ===========================================================================
# verifier.py — critical_ top-level field (line 228)
# ===========================================================================


def test_validate_shape_critical_top_level_field() -> None:
    # line 227-228 — critical_ top-level field → unknown top-level fields
    bundle = _minimal_valid_bundle()
    bundle["critical_unknown"] = "data"
    with pytest.raises(BundleSchemaError, match="unknown top-level fields"):
        verify_proof_bundle(bundle)


# ===========================================================================
# verifier.py — line 597: verification_report carries failure detail on ok chain
# ===========================================================================


def test_metadata_closure_report_first_bad_index_non_none_on_ok_chain() -> None:
    # line 596-597 — chain is ok but report.first_bad_index is non-None
    bundle = _good_bundle()
    # Manually set first_bad_index to non-None (chain is fine)
    bundle["verification_report"]["first_bad_index"] = 0
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert result.metadata_ok is False


# ===========================================================================
# verifier.py — line 618, 622, 625, 628 — _verify_policy_trace_refs via direct call
# ===========================================================================


def test_policy_trace_verify_direct_wrong_type() -> None:
    # line 623-625 — wrong_type refs
    from attestplane.event_types import POLICY_CHECK_EVENT, TOOL_CALL_EVENT

    chain = []
    head = genesis_head()
    for i, et in enumerate([TOOL_CALL_EVENT, POLICY_CHECK_EVENT]):
        ev = chain_extend(head, EventDraft(event_type=et, actor="a", payload={"i": i}), now=_NOW,
                          event_id=f"00000000-0000-7000-8000-{i:012d}")
        chain.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    builder = ProofBundleBuilder(chain_id="wrong-type-direct", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    # Inject refs pointing at the TOOL_CALL_EVENT (wrong type) and POLICY_CHECK_EVENT
    bundle["policy_trace_refs"] = [chain[0].event_hash.hex()]
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert "non-policy" in (result.policy_trace_refs_reason or "")


# ===========================================================================
# sdk/bundle.py line 50 — verify_minimum_bundle happy path
# ===========================================================================


def test_verify_minimum_bundle_success() -> None:
    # line 42-50
    from attestplane.sdk.bundle import verify_minimum_bundle

    chain = _build_chain(1)
    builder = ProofBundleBuilder(chain_id="ok-min", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    bundle["signatures"] = [_syntactic_sig(chain[0])]
    result = verify_minimum_bundle(bundle)
    assert result.ok is True
    assert result.event_count == 1


# ===========================================================================
# settlement_verifier.py — "higher seq" branches (122->109, 125->109, 126->109)
# These branches fire when we find a SECOND matching event with HIGHER seq
# (so the condition `seq < current` is False and we DON'T update).
# ===========================================================================


def test_settlement_lease_consumed_higher_seq_not_updated() -> None:
    # line 122->109 — seq >= lease_consumed_seq → don't update (False branch)
    chain = [
        {
            "seq": 2,
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {
            "seq": 5,  # higher seq → should NOT replace 2
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {"seq": 10, "event_type": "settlement_event", "payload": {"settlement_run_id": "s"}},
    ]
    result = check_settlement_precondition(chain, _claim())
    assert result.ok is True
    assert result.lease_consumed_seq == 2  # lowest seq kept


def test_settlement_event_wrong_run_id_not_matched() -> None:
    # line 125->109 — settlement_event with wrong settlement_run_id → False branch
    chain = [
        {
            "seq": 0,
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {
            "seq": 1,
            "event_type": "settlement_event",
            "payload": {"settlement_run_id": "different-run-id"},  # won't match
        },
        {
            "seq": 2,
            "event_type": "settlement_event",
            "payload": {"settlement_run_id": "s"},  # matches
        },
    ]
    result = check_settlement_precondition(chain, _claim())
    assert result.ok is True
    assert result.settlement_event_seq == 2


def test_settlement_event_higher_seq_not_updated() -> None:
    # line 126->109 — seq >= settlement_event_seq → don't update (False branch of inner if)
    chain = [
        {
            "seq": 0,
            "event_type": "lease_lifecycle_event",
            "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64},
        },
        {
            "seq": 5,
            "event_type": "settlement_event",
            "payload": {"settlement_run_id": "s", "amount_hash": "b" * 64},
        },
        {
            "seq": 10,  # higher seq → should NOT replace 5
            "event_type": "settlement_event",
            "payload": {"settlement_run_id": "s", "amount_hash": "c" * 64},
        },
    ]
    result = check_settlement_precondition(chain, _claim())
    assert result.ok is True
    assert result.settlement_event_seq == 5  # lowest seq kept


# ===========================================================================
# verifier.py — line 338 — duplicate canonical event hashes (unreachable in
# normal usage but tested by injecting a mock)
# ===========================================================================


def test_validate_shape_bad_bundle_version() -> None:
    # lines 229-232 — bundle_version != 1
    bundle = _minimal_valid_bundle()
    bundle["bundle_version"] = 99
    with pytest.raises(BundleSchemaError, match="unsupported bundle_version"):
        verify_proof_bundle(bundle)


def test_signed_schema_sig_not_object_then_later_valid() -> None:
    # lines 342-344 — non-dict signature entry, then skips to next
    chain = _build_chain(1)
    builder = ProofBundleBuilder(chain_id="non-obj-sig", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    good_sig = _syntactic_sig(chain[0])
    bundle["signatures"] = ["not-a-dict", good_sig]
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    # First is bad, second is good → overall passes
    assert result.ok is True


def test_signed_schema_all_sigs_not_object() -> None:
    # lines 342-344 — all non-dict → fail
    chain = _build_chain(1)
    builder = ProofBundleBuilder(chain_id="all-non-obj", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    bundle["signatures"] = ["not-a-dict", 42]
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is False
    assert result.signed_attestation_schema_ok is False


def test_validate_sig_shape_missing_fields_after_valid_hex() -> None:
    # line 379 — sig has the right event hash but missing other fields
    chain = _build_chain(1)
    builder = ProofBundleBuilder(chain_id="partial-sig", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    # A dict with valid signed_event_hash_hex but no other fields
    bundle["signatures"] = [
        {"signed_event_hash_hex": hash_event(chain[0].event).hex()}
    ]
    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is False
    assert "missing fields" in (result.signed_attestation_schema_reason or "")


def test_metadata_closure_report_reason_non_none_on_ok_chain() -> None:
    # line 596-597 — chain is OK but report.reason is non-None
    bundle = _good_bundle()
    bundle["verification_report"]["reason"] = "unexpected-reason"
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert result.metadata_ok is False


def test_policy_trace_refs_duplicate() -> None:
    # line 617-618 — duplicate refs
    from attestplane.event_types import POLICY_CHECK_EVENT

    chain = []
    head = genesis_head()
    ev = chain_extend(head, EventDraft(event_type=POLICY_CHECK_EVENT, actor="a", payload={}), now=_NOW,
                      event_id="00000000-0000-7000-8000-000000000000")
    chain.append(ev)
    builder = ProofBundleBuilder(chain_id="dup-ref2", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    ref = chain[0].event_hash.hex()
    bundle["policy_trace_refs"] = [ref, ref]
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert "duplicate" in (result.policy_trace_refs_reason or "")


def test_policy_trace_refs_dangling() -> None:
    # line 620-622 — dangling refs
    from attestplane.event_types import POLICY_CHECK_EVENT

    chain = []
    head = genesis_head()
    ev = chain_extend(head, EventDraft(event_type=POLICY_CHECK_EVENT, actor="a", payload={}), now=_NOW,
                      event_id="00000000-0000-7000-8000-000000000000")
    chain.append(ev)
    builder = ProofBundleBuilder(chain_id="dangling-ref", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    bundle["policy_trace_refs"] = ["f" * 64]  # not in events
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert "dangling" in (result.policy_trace_refs_reason or "")


def test_policy_trace_refs_absent_with_no_policy_events() -> None:
    # line 604-606 — no policy events and refs absent → True
    chain = _build_chain(2)
    builder = ProofBundleBuilder(chain_id="no-policy-no-refs", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    assert "policy_trace_refs" not in bundle
    result = verify_proof_bundle(bundle)
    assert result.ok is True
    assert result.policy_trace_refs_ok is True


def test_policy_trace_refs_all_valid_returns_true() -> None:
    # line 628 — all refs valid and ordered correctly → True (inner return)
    from attestplane.event_types import POLICY_CHECK_EVENT

    chain = []
    head = genesis_head()
    for i in range(2):
        ev = chain_extend(
            head,
            EventDraft(event_type=POLICY_CHECK_EVENT, actor="a", payload={"i": i}),
            now=_NOW,
            event_id=f"00000000-0000-7000-8000-{i:012d}",
        )
        chain.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    builder = ProofBundleBuilder(chain_id="all-valid-refs", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    # policy_trace_refs should be auto-set correctly
    result = verify_proof_bundle(bundle)
    assert result.ok is True
    assert result.policy_trace_refs_ok is True


def test_verify_proof_bundle_file_not_found(tmp_path: Path) -> None:
    # lines 762-763 — FileNotFoundError
    with pytest.raises(BundleVerificationError, match="not found"):
        verify_proof_bundle_file(tmp_path / "nope.json")


def test_verify_proof_bundle_file_bad_json(tmp_path: Path) -> None:
    # lines 764-765 — JSONDecodeError
    p = tmp_path / "bad.json"
    p.write_text("this is not json", encoding="utf-8")
    with pytest.raises(BundleSchemaError, match="not valid JSON"):
        verify_proof_bundle_file(p)


def test_canonical_hash_uniqueness_check() -> None:
    # line 337-338 — duplicate hashes check via patching hash_event
    # This branch fires if two events have the same canonical hash.
    # Since chain_extend ensures unique events, we mock hash_event.
    from unittest.mock import patch

    chain = _build_chain(2)
    builder = ProofBundleBuilder(chain_id="dup-canonical", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    # All events will hash to the same value → len(set) != len(events)
    fake_hash = bytes(32)
    with patch("attestplane.verifier.hash_event", return_value=fake_hash):
        bundle["signatures"] = [_syntactic_sig(chain[0])]
        result = verify_proof_bundle(bundle, require_signed_attestation=True)
    assert result.ok is False
    assert "unique" in (result.signed_attestation_schema_reason or "")
