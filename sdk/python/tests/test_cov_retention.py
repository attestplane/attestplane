# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coverage-completion tests for attestplane.retention (target ≥98%)."""

from __future__ import annotations

from typing import Any

import pytest

from attestplane.retention import (
    build_deletion_proof,
    build_retention_marker,
    validate_retention_proof,
    verify_retention_proofs,
)

_HEX64 = "a" * 64
_HEX64B = "b" * 64
_HEX64C = "c" * 64


# ── build_retention_marker (lines 61-70) ──────────────────────────────────────

def test_build_retention_marker_returns_valid_dict() -> None:
    m = build_retention_marker(
        proof_id="pid-1",
        target_event_hash_hex=_HEX64,
        commit_event_hash_hex=_HEX64B,
        reason="annual_review",
    )
    assert m["action"] == "retention_marker"
    assert m["proof_id"] == "pid-1"
    assert m["reason"] == "annual_review"
    assert m["target_event_hash_hex"] == _HEX64
    assert m["commit_event_hash_hex"] == _HEX64B
    assert m["retention_proof_schema_version"] == 1


def test_build_retention_marker_raises_on_bad_hash() -> None:
    with pytest.raises(ValueError):
        build_retention_marker(
            proof_id="pid-x",
            target_event_hash_hex="not-hex",
            commit_event_hash_hex=_HEX64B,
            reason="r",
        )


# ── validate_retention_proof error branches ───────────────────────────────────

def _base_proof(**overrides: object) -> dict[str, Any]:
    p: dict[str, Any] = {
        "retention_proof_schema_version": 1,
        "proof_id": "p1",
        "action": "retention_marker",
        "target_event_hash_hex": _HEX64,
        "commit_event_hash_hex": _HEX64B,
        "reason": "r",
    }
    p.update(overrides)
    return p


def test_validate_missing_fields_raises() -> None:
    # line 88: missing required fields
    with pytest.raises(ValueError, match="missing required fields"):
        validate_retention_proof({})


def test_validate_wrong_schema_version() -> None:
    # line 90: schema version != 1
    with pytest.raises(ValueError, match="retention_proof_schema_version must be 1"):
        validate_retention_proof(_base_proof(retention_proof_schema_version=2))


def test_validate_empty_proof_id() -> None:
    # line 92: proof_id empty string
    with pytest.raises(ValueError, match="proof_id must be a non-empty string"):
        validate_retention_proof(_base_proof(proof_id=""))


def test_validate_non_string_proof_id() -> None:
    # line 92: proof_id not a string
    with pytest.raises(ValueError, match="proof_id must be a non-empty string"):
        validate_retention_proof(_base_proof(proof_id=42))


def test_validate_invalid_action() -> None:
    # line 94: action not in _ACTIONS
    with pytest.raises(ValueError, match="action must be retention_marker or deletion_marker"):
        validate_retention_proof(_base_proof(action="bad_action"))


def test_validate_empty_reason() -> None:
    # line 96: reason empty
    with pytest.raises(ValueError, match="reason must be a non-empty string"):
        validate_retention_proof(_base_proof(reason=""))


def test_validate_non_string_reason() -> None:
    # line 96: reason not a string
    with pytest.raises(ValueError, match="reason must be a non-empty string"):
        validate_retention_proof(_base_proof(reason=None))


def test_validate_bad_target_hash() -> None:
    # line 99: target_event_hash_hex not 64-hex
    with pytest.raises(ValueError, match="target_event_hash_hex must be lowercase 64-hex"):
        validate_retention_proof(_base_proof(target_event_hash_hex="ZZZZ"))


def test_validate_bad_commit_hash() -> None:
    # line 99: commit_event_hash_hex not 64-hex
    with pytest.raises(ValueError, match="commit_event_hash_hex must be lowercase 64-hex"):
        validate_retention_proof(_base_proof(commit_event_hash_hex="short"))


def test_validate_deletion_marker_missing_redacted() -> None:
    # lines 103-104: deletion_marker requires redacted_event_hash_hex
    with pytest.raises(ValueError, match="redacted_event_hash_hex must be lowercase 64-hex for deletion_marker"):
        validate_retention_proof(
            _base_proof(action="deletion_marker")
            # no redacted_event_hash_hex key → raw.get() returns None
        )


def test_validate_deletion_marker_bad_redacted() -> None:
    # lines 103-104: deletion_marker with invalid redacted hash
    with pytest.raises(ValueError, match="redacted_event_hash_hex must be lowercase 64-hex for deletion_marker"):
        validate_retention_proof(
            _base_proof(action="deletion_marker", redacted_event_hash_hex="not-hex")
        )


def test_validate_retention_marker_with_bad_optional_redacted() -> None:
    # line 105: retention_marker with invalid optional redacted_event_hash_hex
    with pytest.raises(ValueError, match="redacted_event_hash_hex must be lowercase 64-hex when present"):
        validate_retention_proof(
            _base_proof(action="retention_marker", redacted_event_hash_hex="bad")
        )


def test_validate_retention_marker_with_valid_optional_redacted() -> None:
    # retention_marker with valid optional redacted (no error)
    validate_retention_proof(
        _base_proof(action="retention_marker", redacted_event_hash_hex=_HEX64C)
    )


# ── verify_retention_proofs branches ─────────────────────────────────────────

def test_verify_none_proofs_ok() -> None:
    # line 114: proofs is None → ok
    r = verify_retention_proofs(None, set())
    assert r.ok is True
    assert r.checked_count == 0


def test_verify_non_list_proofs_fails() -> None:
    # lines 116-121: proofs not a list
    r = verify_retention_proofs("not_a_list", set())
    assert r.ok is False
    assert r.reason == "retention_proofs must be an array"
    assert r.failed_index == 0


def test_verify_non_dict_item_fails() -> None:
    # lines 125-130: item is not a dict
    r = verify_retention_proofs(["not_a_dict"], set())
    assert r.ok is False
    assert "must be an object" in (r.reason or "")
    assert r.failed_index == 0


def test_verify_invalid_proof_fails() -> None:
    # lines 133-139: validate_retention_proof raises ValueError
    r = verify_retention_proofs([{"action": "bad"}], set())
    assert r.ok is False
    assert r.failed_index == 0


def test_verify_duplicate_proof_id_fails() -> None:
    # lines 142-147: duplicate proof_id
    proof = _base_proof()
    r = verify_retention_proofs([proof, proof], {_HEX64, _HEX64B})
    assert r.ok is False
    assert "duplicate proof_id" in (r.reason or "")
    assert r.failed_index == 1


def test_verify_dangling_refs_with_redacted_fails() -> None:
    # lines 150-152: redacted hash appended; lines 153-159: dangling refs
    proof = _base_proof(action="deletion_marker", redacted_event_hash_hex=_HEX64C)
    # Only provide two of the three hashes → _HEX64C is missing
    r = verify_retention_proofs([proof], {_HEX64, _HEX64B})
    assert r.ok is False
    assert "dangling event refs" in (r.reason or "")


def test_verify_all_refs_present_with_redacted_ok() -> None:
    # lines 150-152 covered + success path
    proof = _base_proof(action="deletion_marker", redacted_event_hash_hex=_HEX64C)
    r = verify_retention_proofs([proof], {_HEX64, _HEX64B, _HEX64C})
    assert r.ok is True
    assert r.checked_count == 1


def test_verify_empty_list_ok() -> None:
    r = verify_retention_proofs([], set())
    assert r.ok is True
    assert r.checked_count == 0


def test_verify_dangling_target_ref_fails() -> None:
    proof = _base_proof()
    # target hash not in event_hashes
    r = verify_retention_proofs([proof], {_HEX64B})
    assert r.ok is False
    assert "dangling event refs" in (r.reason or "")


# ── build_deletion_proof (lines 40-50) ───────────────────────────────────────

def test_build_deletion_proof_returns_valid_dict() -> None:
    d = build_deletion_proof(
        proof_id="dpid-1",
        target_event_hash_hex=_HEX64,
        commit_event_hash_hex=_HEX64B,
        redacted_event_hash_hex=_HEX64C,
        reason="gdpr_erasure",
    )
    assert d["action"] == "deletion_marker"
    assert d["proof_id"] == "dpid-1"
    assert d["redacted_event_hash_hex"] == _HEX64C
    assert d["retention_proof_schema_version"] == 1


def test_build_deletion_proof_raises_on_bad_redacted() -> None:
    with pytest.raises(ValueError):
        build_deletion_proof(
            proof_id="dpid-2",
            target_event_hash_hex=_HEX64,
            commit_event_hash_hex=_HEX64B,
            redacted_event_hash_hex="not-hex",
            reason="r",
        )
