# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Unit + conformance tests for event_payloads.py (ADR-0009 P0.1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.event_payloads import (
    FORBIDDEN_PAYLOAD_FIELDS,
    LeaseLifecycleEventPayload,
    PolicyCheckEventPayload,
    validate_lease_lifecycle_event_payload,
    validate_policy_check_event_payload,
)

_VECTORS_PATH = (
    Path(__file__).resolve().parent / "conformance" / "lease_lifecycle_event_vectors.json"
)
_POLICY_VECTORS_PATH = (
    Path(__file__).resolve().parent / "conformance" / "policy_check_event_vectors.json"
)


def _load_vectors() -> dict:
    return json.loads(_VECTORS_PATH.read_text(encoding="utf-8"))


def _load_policy_vectors() -> dict:
    return json.loads(_POLICY_VECTORS_PATH.read_text(encoding="utf-8"))


def test_vectors_file_loads() -> None:
    vectors = _load_vectors()
    assert vectors["$schema_version"] == 1
    assert len(vectors["positive_vectors"]) == 4
    assert len(vectors["negative_vectors"]) == 11


@pytest.mark.parametrize(
    "vec",
    _load_vectors()["positive_vectors"],
    ids=lambda v: v["name"],
)
def test_positive_vectors_validate(vec: dict) -> None:
    """Every positive vector must validate without raising."""
    validate_lease_lifecycle_event_payload(vec["payload"])


@pytest.mark.parametrize(
    "vec",
    _load_vectors()["negative_vectors"],
    ids=lambda v: v["name"],
)
def test_negative_vectors_rejected(vec: dict) -> None:
    """Every negative vector must raise ValueError with expected substring."""
    with pytest.raises(ValueError) as excinfo:
        validate_lease_lifecycle_event_payload(vec["payload"])
    assert vec["expected_error_contains"] in str(excinfo.value), (
        f"vector {vec['name']!r}: expected reason containing "
        f"{vec['expected_error_contains']!r}, got {excinfo.value!s}"
    )


def test_forbidden_field_list_complete() -> None:
    """Sanity: forbidden list covers the documented AIOS authority signal set."""
    expected_min = {
        "signature", "private_key", "secret", "token",
        "capability", "capability_required", "budget", "budget_cap",
        "expression", "hmac",
    }
    assert expected_min <= FORBIDDEN_PAYLOAD_FIELDS


def test_typed_dict_accepts_minimal() -> None:
    """TypedDict shape sanity check (compile-time + runtime construction)."""
    p: LeaseLifecycleEventPayload = {
        "lease_event_schema_version": 1,
        "lease_id_hash": "0" * 64,
        "lifecycle": "granted",
        "observed_at": "2026-05-17T12:00:00.000000Z",
    }
    validate_lease_lifecycle_event_payload(p)  # round-trip


def test_non_dict_input_rejected() -> None:
    with pytest.raises(ValueError, match="must be dict"):
        validate_lease_lifecycle_event_payload("not a dict")  # type: ignore[arg-type]


def test_artifact_hash_ref_format_enforced() -> None:
    with pytest.raises(ValueError, match="artifact_hash_ref"):
        validate_lease_lifecycle_event_payload({
            "lease_event_schema_version": 1,
            "lease_id_hash": "0" * 64,
            "lifecycle": "consumed",
            "observed_at": "2026-05-17T12:00:00.000000Z",
            "artifact_hash_ref": "too-short",
        })


def test_optional_string_field_must_be_string() -> None:
    with pytest.raises(ValueError, match="grantor_runtime_id"):
        validate_lease_lifecycle_event_payload({
            "lease_event_schema_version": 1,
            "lease_id_hash": "0" * 64,
            "lifecycle": "granted",
            "observed_at": "2026-05-17T12:00:00.000000Z",
            "grantor_runtime_id": 12345,
        })


# --- policy_check_event vectors -------------------------------------------


def test_policy_vectors_file_loads() -> None:
    vectors = _load_policy_vectors()
    assert vectors["$schema_version"] == 1
    assert len(vectors["positive_vectors"]) == 4
    assert len(vectors["negative_vectors"]) == 12


@pytest.mark.parametrize(
    "vec",
    _load_policy_vectors()["positive_vectors"],
    ids=lambda v: v["name"],
)
def test_policy_positive_vectors_validate(vec: dict) -> None:
    validate_policy_check_event_payload(vec["payload"])


@pytest.mark.parametrize(
    "vec",
    _load_policy_vectors()["negative_vectors"],
    ids=lambda v: v["name"],
)
def test_policy_negative_vectors_rejected(vec: dict) -> None:
    with pytest.raises(ValueError) as excinfo:
        validate_policy_check_event_payload(vec["payload"])
    assert vec["expected_error_contains"] in str(excinfo.value), (
        f"vector {vec['name']!r}: expected reason containing "
        f"{vec['expected_error_contains']!r}, got {excinfo.value!s}"
    )


def test_policy_typed_dict_minimal() -> None:
    p: PolicyCheckEventPayload = {
        "policy_event_schema_version": 1,
        "policy_id": "p",
        "rule_id": "r",
        "decision": "allow",
        "observed_at": "2026-05-17T12:00:00.000000Z",
    }
    validate_policy_check_event_payload(p)


def test_policy_expression_body_forbidden_explicitly() -> None:
    """ADR-0004 § 2 case #10 — expression body must be redacted to hash."""
    with pytest.raises(ValueError, match="forbidden field"):
        validate_policy_check_event_payload({
            "policy_event_schema_version": 1,
            "policy_id": "p",
            "rule_id": "r",
            "decision": "deny",
            "observed_at": "2026-05-17T12:00:00.000000Z",
            "expression": "amount > 10000",
        })


def test_policy_evidence_refs_max_256() -> None:
    refs = [f"{i:064d}" for i in range(257)]
    with pytest.raises(ValueError, match="max 256 entries"):
        validate_policy_check_event_payload({
            "policy_event_schema_version": 1,
            "policy_id": "p",
            "rule_id": "r",
            "decision": "allow",
            "observed_at": "2026-05-17T12:00:00.000000Z",
            "evidence_refs": refs,
        })
