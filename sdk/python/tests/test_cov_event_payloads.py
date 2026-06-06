# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coverage-gap tests for attestplane.event_payloads.

Missing lines: 66, 70-71, 330, 341, 370, 376, 469-525.
"""

from __future__ import annotations

import pytest

from attestplane.event_payloads import (
    validate_lease_lifecycle_event_payload,
    validate_policy_check_event_payload,
    validate_replay_event_payload,
)

_VALID_HEX64 = "a" * 64
_VALID_TS = "2026-05-17T12:00:00.000000Z"

# ---------------------------------------------------------------------------
# _require_iso_utc branches (lines 66, 70-71)
# These fire through any validator that calls _require_iso_utc.
# ---------------------------------------------------------------------------


def test_iso_utc_rejects_non_string() -> None:
    """Line 66: value is not a string."""
    payload = {
        "lease_event_schema_version": 1,
        "lease_id_hash": _VALID_HEX64,
        "lifecycle": "granted",
        "observed_at": 12345,  # not a string
    }
    with pytest.raises(ValueError, match="must be ISO-8601 string"):
        validate_lease_lifecycle_event_payload(payload)


def test_iso_utc_rejects_invalid_format() -> None:
    """Lines 70-71: datetime.fromisoformat raises ValueError."""
    payload = {
        "lease_event_schema_version": 1,
        "lease_id_hash": _VALID_HEX64,
        "lifecycle": "granted",
        "observed_at": "not-a-date",
    }
    with pytest.raises(ValueError, match="not valid ISO-8601"):
        validate_lease_lifecycle_event_payload(payload)


def test_iso_utc_rejects_naive_datetime() -> None:
    """Line 73: datetime is naive (no tzinfo)."""
    payload = {
        "lease_event_schema_version": 1,
        "lease_id_hash": _VALID_HEX64,
        "lifecycle": "granted",
        "observed_at": "2026-05-17T12:00:00",  # no timezone
    }
    with pytest.raises(ValueError, match="UTC-aware"):
        validate_lease_lifecycle_event_payload(payload)


# ---------------------------------------------------------------------------
# validate_policy_check_event_payload missing branches
# ---------------------------------------------------------------------------


def test_policy_payload_not_dict() -> None:
    """Line 330: payload is not a dict."""
    with pytest.raises(ValueError, match="must be dict"):
        validate_policy_check_event_payload("not-a-dict")  # type: ignore[arg-type]


def test_policy_payload_version_not_one() -> None:
    """Line 341: policy_event_schema_version != 1."""
    payload = {
        "policy_event_schema_version": 2,
        "policy_id": "pol-1",
        "rule_id": "rule-1",
        "decision": "allow",
        "observed_at": _VALID_TS,
    }
    with pytest.raises(ValueError, match="policy_event_schema_version must be 1"):
        validate_policy_check_event_payload(payload)


def test_policy_payload_empty_policy_id() -> None:
    """policy_id must be non-empty string."""
    payload = {
        "policy_event_schema_version": 1,
        "policy_id": "",
        "rule_id": "rule-1",
        "decision": "allow",
        "observed_at": _VALID_TS,
    }
    with pytest.raises(ValueError, match="policy_id"):
        validate_policy_check_event_payload(payload)


def test_policy_payload_evidence_refs_not_list() -> None:
    """Line 370: evidence_refs present but not a list."""
    payload = {
        "policy_event_schema_version": 1,
        "policy_id": "pol-1",
        "rule_id": "rule-1",
        "decision": "allow",
        "observed_at": _VALID_TS,
        "evidence_refs": "not-a-list",
    }
    with pytest.raises(ValueError, match="must be list"):
        validate_policy_check_event_payload(payload)


def test_policy_payload_evidence_refs_duplicate() -> None:
    """Line 376-380: duplicate entry in evidence_refs."""
    ref = _VALID_HEX64
    payload = {
        "policy_event_schema_version": 1,
        "policy_id": "pol-1",
        "rule_id": "rule-1",
        "decision": "allow",
        "observed_at": _VALID_TS,
        "evidence_refs": [ref, ref],
    }
    with pytest.raises(ValueError, match="duplicate entry"):
        validate_policy_check_event_payload(payload)


def test_policy_payload_evidence_refs_bad_hex() -> None:
    """evidence_refs[i] is not a 64-hex string."""
    payload = {
        "policy_event_schema_version": 1,
        "policy_id": "pol-1",
        "rule_id": "rule-1",
        "decision": "allow",
        "observed_at": _VALID_TS,
        "evidence_refs": ["not-hex"],
    }
    with pytest.raises(ValueError, match="64-hex"):
        validate_policy_check_event_payload(payload)


def test_policy_payload_evidence_refs_too_many() -> None:
    """evidence_refs > 256 entries."""
    payload = {
        "policy_event_schema_version": 1,
        "policy_id": "pol-1",
        "rule_id": "rule-1",
        "decision": "allow",
        "observed_at": _VALID_TS,
        "evidence_refs": [format(i, "064x") for i in range(257)],
    }
    with pytest.raises(ValueError, match="max 256"):
        validate_policy_check_event_payload(payload)


def test_policy_payload_effect_invalid() -> None:
    """effect must be one of INFO/WARN/BLOCK."""
    payload = {
        "policy_event_schema_version": 1,
        "policy_id": "pol-1",
        "rule_id": "rule-1",
        "decision": "allow",
        "observed_at": _VALID_TS,
        "effect": "FATAL",
    }
    with pytest.raises(ValueError, match="effect"):
        validate_policy_check_event_payload(payload)


def test_policy_payload_policy_version_zero() -> None:
    """policy_version must be >= 1."""
    payload = {
        "policy_event_schema_version": 1,
        "policy_id": "pol-1",
        "rule_id": "rule-1",
        "decision": "allow",
        "observed_at": _VALID_TS,
        "policy_version": 0,
    }
    with pytest.raises(ValueError, match="policy_version"):
        validate_policy_check_event_payload(payload)


def test_policy_payload_policy_version_bool_rejected() -> None:
    """bool subclasses int; policy_version must reject bool."""
    payload = {
        "policy_event_schema_version": 1,
        "policy_id": "pol-1",
        "rule_id": "rule-1",
        "decision": "allow",
        "observed_at": _VALID_TS,
        "policy_version": True,
    }
    with pytest.raises(ValueError, match="policy_version"):
        validate_policy_check_event_payload(payload)


def test_policy_payload_expression_hash_bad() -> None:
    """expression_hash must be 64-hex."""
    payload = {
        "policy_event_schema_version": 1,
        "policy_id": "pol-1",
        "rule_id": "rule-1",
        "decision": "allow",
        "observed_at": _VALID_TS,
        "expression_hash": "short",
    }
    with pytest.raises(ValueError, match="expression_hash"):
        validate_policy_check_event_payload(payload)


def test_policy_payload_valid_full() -> None:
    """Happy path with all optional fields."""
    payload = {
        "policy_event_schema_version": 1,
        "policy_id": "pol-1",
        "rule_id": "rule-1",
        "decision": "deny",
        "observed_at": _VALID_TS,
        "policy_version": 2,
        "kind": "rate_limit",
        "effect": "BLOCK",
        "expression_hash": _VALID_HEX64,
        "evidence_refs": [_VALID_HEX64],
        "reason_code": "RATE_EXCEEDED",
        "reason_text": "Too many requests",
    }
    validate_policy_check_event_payload(payload)  # must not raise


# ---------------------------------------------------------------------------
# validate_replay_event_payload — lines 469-525
# ---------------------------------------------------------------------------


def _valid_replay_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "replay_event_schema_version": 1,
        "replay_run_id": "rr-1",
        "original_run_id": "or-1",
        "input_hash_match": True,
        "artifact_hash_match": True,
        "audit_chain_match": True,
        "deterministic_result": True,
        "observed_at": _VALID_TS,
    }
    base.update(overrides)
    return base


def test_replay_payload_not_dict() -> None:
    """Line 469-470: payload is not a dict."""
    with pytest.raises(ValueError, match="must be dict"):
        validate_replay_event_payload("bad")  # type: ignore[arg-type]


def test_replay_payload_missing_required_fields() -> None:
    """Line 477-479: missing required keys."""
    with pytest.raises(ValueError, match="missing required fields"):
        validate_replay_event_payload({})


def test_replay_payload_schema_version_not_one() -> None:
    """Line 480-483: replay_event_schema_version != 1."""
    payload = _valid_replay_payload(replay_event_schema_version=2)
    with pytest.raises(ValueError, match="replay_event_schema_version must be 1"):
        validate_replay_event_payload(payload)


def test_replay_payload_empty_replay_run_id() -> None:
    """Line 484-487: replay_run_id empty string."""
    payload = _valid_replay_payload(replay_run_id="")
    with pytest.raises(ValueError, match="replay_run_id"):
        validate_replay_event_payload(payload)


def test_replay_payload_empty_original_run_id() -> None:
    """original_run_id empty string."""
    payload = _valid_replay_payload(original_run_id="")
    with pytest.raises(ValueError, match="original_run_id"):
        validate_replay_event_payload(payload)


def test_replay_payload_non_bool_field() -> None:
    """Line 498-502: one of the bool fields is an int."""
    payload = _valid_replay_payload(input_hash_match=1)
    with pytest.raises(ValueError, match="must be boolean"):
        validate_replay_event_payload(payload)


def test_replay_payload_deterministic_and_cross_check_false() -> None:
    """Line 505-511: all three true but deterministic_result=False."""
    payload = _valid_replay_payload(deterministic_result=False)
    with pytest.raises(ValueError, match="deterministic_result"):
        validate_replay_event_payload(payload)


def test_replay_payload_deterministic_and_cross_check_mismatch() -> None:
    """Partial match: input_hash_match=False so AND is False; det=True → mismatch."""
    payload = _valid_replay_payload(
        input_hash_match=False,
        artifact_hash_match=True,
        audit_chain_match=True,
        deterministic_result=True,
    )
    with pytest.raises(ValueError, match="deterministic_result"):
        validate_replay_event_payload(payload)


def test_replay_payload_snapshot_id_ref_empty() -> None:
    """Line 516-518: snapshot_id_ref is empty string."""
    payload = _valid_replay_payload(snapshot_id_ref="")
    with pytest.raises(ValueError, match="snapshot_id_ref"):
        validate_replay_event_payload(payload)


def test_replay_payload_diff_summary_hash_bad() -> None:
    """Line 521-522: diff_summary_hash is not 64-hex."""
    payload = _valid_replay_payload(diff_summary_hash="short")
    with pytest.raises(ValueError, match="diff_summary_hash"):
        validate_replay_event_payload(payload)


def test_replay_payload_forbidden_field() -> None:
    """_reject_forbidden_fields fires for replay_event."""
    payload = _valid_replay_payload(secret="my-secret")  # noqa: S106
    with pytest.raises(ValueError, match="forbidden field"):
        validate_replay_event_payload(payload)


def test_replay_payload_unknown_field() -> None:
    """_reject_unknown_fields fires for replay_event."""
    payload = _valid_replay_payload(unknown_field="x")
    with pytest.raises(ValueError, match="unknown field"):
        validate_replay_event_payload(payload)


def test_replay_payload_valid_minimal() -> None:
    """Happy path: minimal valid payload should not raise."""
    validate_replay_event_payload(_valid_replay_payload())


def test_replay_payload_valid_all_false() -> None:
    """deterministic_result=False when all three are False is valid."""
    payload = _valid_replay_payload(
        input_hash_match=False,
        artifact_hash_match=False,
        audit_chain_match=False,
        deterministic_result=False,
    )
    validate_replay_event_payload(payload)


def test_replay_payload_valid_with_optional_fields() -> None:
    """Happy path with all optional fields."""
    payload = _valid_replay_payload(
        snapshot_id_ref="snap-123",
        diff_summary_hash=_VALID_HEX64,
        reason_code="REPLAY_OK",
        reason_text="all matched",
    )
    validate_replay_event_payload(payload)


# ---------------------------------------------------------------------------
# Additional lease_lifecycle_event branches (lines 195, 204, 206, 212, 217, 222-236)
# ---------------------------------------------------------------------------


def test_lease_payload_not_dict() -> None:
    """Line 195: payload is not a dict."""
    with pytest.raises(ValueError, match="must be dict"):
        validate_lease_lifecycle_event_payload("bad")  # type: ignore[arg-type]


def test_lease_payload_missing_required_fields() -> None:
    """Line 204: missing required keys."""
    with pytest.raises(ValueError, match="missing required fields"):
        validate_lease_lifecycle_event_payload({})


def test_lease_payload_schema_version_not_one() -> None:
    """Lines 205-209: lease_event_schema_version != 1."""
    payload = {
        "lease_event_schema_version": 99,
        "lease_id_hash": _VALID_HEX64,
        "lifecycle": "granted",
        "observed_at": _VALID_TS,
    }
    with pytest.raises(ValueError, match="lease_event_schema_version must be 1"):
        validate_lease_lifecycle_event_payload(payload)


def test_lease_payload_invalid_lease_id_hash() -> None:
    """Line 212: lease_id_hash not 64-hex."""
    payload = {
        "lease_event_schema_version": 1,
        "lease_id_hash": "not-hex",
        "lifecycle": "granted",
        "observed_at": _VALID_TS,
    }
    with pytest.raises(ValueError, match="lease_id_hash must be 64-hex"):
        validate_lease_lifecycle_event_payload(payload)


def test_lease_payload_invalid_lifecycle() -> None:
    """Line 217: lifecycle not in enum."""
    payload = {
        "lease_event_schema_version": 1,
        "lease_id_hash": _VALID_HEX64,
        "lifecycle": "unknown_lifecycle",
        "observed_at": _VALID_TS,
    }
    with pytest.raises(ValueError, match="lifecycle must be one of"):
        validate_lease_lifecycle_event_payload(payload)


def test_lease_payload_artifact_hash_ref_bad() -> None:
    """Lines 222-226: artifact_hash_ref present but not 64-hex."""
    payload = {
        "lease_event_schema_version": 1,
        "lease_id_hash": _VALID_HEX64,
        "lifecycle": "granted",
        "observed_at": _VALID_TS,
        "artifact_hash_ref": "bad",
    }
    with pytest.raises(ValueError, match="artifact_hash_ref"):
        validate_lease_lifecycle_event_payload(payload)


def test_lease_payload_optional_string_non_string() -> None:
    """Lines 228-235: optional string field is not a string → _require_optional_string raises."""
    payload = {
        "lease_event_schema_version": 1,
        "lease_id_hash": _VALID_HEX64,
        "lifecycle": "granted",
        "observed_at": _VALID_TS,
        "grantor_runtime_id": 42,  # must be string
    }
    with pytest.raises(ValueError, match="grantor_runtime_id"):
        validate_lease_lifecycle_event_payload(payload)


def test_lease_payload_reason_code_bad_format() -> None:
    """Line 108: _require_optional_reason_code with bad format."""
    payload = {
        "lease_event_schema_version": 1,
        "lease_id_hash": _VALID_HEX64,
        "lifecycle": "granted",
        "observed_at": _VALID_TS,
        "reason_code": "lowercase_code",  # must match ^[A-Z][A-Z0-9_]{1,63}$
    }
    with pytest.raises(ValueError, match="must match"):
        validate_lease_lifecycle_event_payload(payload)


def test_lease_payload_optional_fields_full() -> None:
    """Happy path with all optional fields including artifact_hash_ref."""
    payload = {
        "lease_event_schema_version": 1,
        "lease_id_hash": _VALID_HEX64,
        "lifecycle": "revoked",
        "observed_at": _VALID_TS,
        "grantor_runtime_id": "runtime-1",
        "tenant_id_ref": "tenant-1",
        "step_id_ref": "step-1",
        "run_id_ref": "run-1",
        "artifact_hash_ref": _VALID_HEX64,
        "reason_code": "REVOKED_BY_ADMIN",
        "reason_text": "admin revoked",
    }
    validate_lease_lifecycle_event_payload(payload)  # must not raise


# ---------------------------------------------------------------------------
# validate_policy_check_event_payload: missing required fields, rule_id check
# ---------------------------------------------------------------------------


def test_policy_payload_missing_required() -> None:
    """Line 339: missing required fields."""
    with pytest.raises(ValueError, match="missing required fields"):
        validate_policy_check_event_payload({})


def test_policy_payload_empty_rule_id() -> None:
    """Line 350: rule_id must be non-empty string."""
    payload = {
        "policy_event_schema_version": 1,
        "policy_id": "pol-1",
        "rule_id": "",
        "decision": "allow",
        "observed_at": _VALID_TS,
    }
    with pytest.raises(ValueError, match="rule_id"):
        validate_policy_check_event_payload(payload)


def test_policy_payload_evidence_refs_present_zero_items() -> None:
    """Line 368+: evidence_refs is empty list (valid — no cross-check failure)."""
    payload = {
        "policy_event_schema_version": 1,
        "policy_id": "pol-1",
        "rule_id": "rule-1",
        "decision": "abstain",
        "observed_at": _VALID_TS,
        "evidence_refs": [],
    }
    validate_policy_check_event_payload(payload)  # must not raise


def test_policy_payload_invalid_decision() -> None:
    """Line 349-352: decision not in allowed set."""
    payload = {
        "policy_event_schema_version": 1,
        "policy_id": "pol-1",
        "rule_id": "rule-1",
        "decision": "maybe",
        "observed_at": _VALID_TS,
    }
    with pytest.raises(ValueError, match="decision must be one of"):
        validate_policy_check_event_payload(payload)


def test_policy_payload_require_optional_reason_code_bad() -> None:
    """reason_code in policy payload with bad format."""
    payload = {
        "policy_event_schema_version": 1,
        "policy_id": "pol-1",
        "rule_id": "rule-1",
        "decision": "allow",
        "observed_at": _VALID_TS,
        "reason_code": "bad format!",
    }
    with pytest.raises(ValueError, match="must match"):
        validate_policy_check_event_payload(payload)
