# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Commit-then-redact retention/deletion proof helpers.

The profile is deliberately narrow: it proves that a bundle contains a
well-formed evidence marker referencing existing chain events.  It does not
claim GDPR compliance, legal sufficiency, or deletion from external systems.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Final, Literal

RETENTION_PROOF_SCHEMA_VERSION: Final[int] = 1
RetentionAction = Literal["retention_marker", "deletion_marker"]

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ACTIONS = {"retention_marker", "deletion_marker"}


@dataclass(frozen=True, slots=True)
class RetentionProofVerificationResult:
    ok: bool
    reason: str | None
    checked_count: int
    failed_index: int | None


def build_deletion_proof(
    *,
    proof_id: str,
    target_event_hash_hex: str,
    commit_event_hash_hex: str,
    redacted_event_hash_hex: str,
    reason: str,
) -> dict[str, Any]:
    """Build a deterministic deletion proof marker."""
    proof = {
        "action": "deletion_marker",
        "commit_event_hash_hex": commit_event_hash_hex,
        "proof_id": proof_id,
        "reason": reason,
        "redacted_event_hash_hex": redacted_event_hash_hex,
        "retention_proof_schema_version": RETENTION_PROOF_SCHEMA_VERSION,
        "target_event_hash_hex": target_event_hash_hex,
    }
    validate_retention_proof(proof)
    return proof


def build_retention_marker(
    *,
    proof_id: str,
    target_event_hash_hex: str,
    commit_event_hash_hex: str,
    reason: str,
) -> dict[str, Any]:
    """Build a deterministic retention marker without claiming deletion."""
    proof = {
        "action": "retention_marker",
        "commit_event_hash_hex": commit_event_hash_hex,
        "proof_id": proof_id,
        "reason": reason,
        "retention_proof_schema_version": RETENTION_PROOF_SCHEMA_VERSION,
        "target_event_hash_hex": target_event_hash_hex,
    }
    validate_retention_proof(proof)
    return proof


def validate_retention_proof(raw: dict[str, Any]) -> None:
    """Validate one retention proof marker.

    Raises ``ValueError`` with deterministic messages on malformed input.
    """
    required = {
        "retention_proof_schema_version",
        "proof_id",
        "action",
        "target_event_hash_hex",
        "commit_event_hash_hex",
        "reason",
    }
    missing = sorted(required - set(raw))
    if missing:
        raise ValueError(f"retention proof missing required fields: {missing}")
    if raw["retention_proof_schema_version"] != RETENTION_PROOF_SCHEMA_VERSION:
        raise ValueError("retention_proof_schema_version must be 1")
    if not isinstance(raw["proof_id"], str) or not raw["proof_id"]:
        raise ValueError("proof_id must be a non-empty string")
    if raw["action"] not in _ACTIONS:
        raise ValueError("action must be retention_marker or deletion_marker")
    if not isinstance(raw["reason"], str) or not raw["reason"]:
        raise ValueError("reason must be a non-empty string")
    for key in ("target_event_hash_hex", "commit_event_hash_hex"):
        if not isinstance(raw[key], str) or _HEX64.fullmatch(raw[key]) is None:
            raise ValueError(f"{key} must be lowercase 64-hex")
    redacted = raw.get("redacted_event_hash_hex")
    if raw["action"] == "deletion_marker":
        if not isinstance(redacted, str) or _HEX64.fullmatch(redacted) is None:
            raise ValueError("redacted_event_hash_hex must be lowercase 64-hex for deletion_marker")
    elif redacted is not None and (not isinstance(redacted, str) or _HEX64.fullmatch(redacted) is None):
        raise ValueError("redacted_event_hash_hex must be lowercase 64-hex when present")


def verify_retention_proofs(
    proofs: Any,
    event_hashes: set[str],
) -> RetentionProofVerificationResult:
    """Verify all proof markers reference existing bundle event hashes."""
    if proofs is None:
        return RetentionProofVerificationResult(ok=True, reason=None, checked_count=0, failed_index=None)
    if not isinstance(proofs, list):
        return RetentionProofVerificationResult(
            ok=False,
            reason="retention_proofs must be an array",
            checked_count=0,
            failed_index=0,
        )
    seen: set[str] = set()
    for idx, proof in enumerate(proofs):
        if not isinstance(proof, dict):
            return RetentionProofVerificationResult(
                ok=False,
                reason=f"retention_proofs[{idx}] must be an object",
                checked_count=idx,
                failed_index=idx,
            )
        try:
            validate_retention_proof(proof)
        except ValueError as exc:
            return RetentionProofVerificationResult(
                ok=False,
                reason=f"retention_proofs[{idx}]: {exc}",
                checked_count=idx,
                failed_index=idx,
            )
        proof_id = proof["proof_id"]
        if proof_id in seen:
            return RetentionProofVerificationResult(
                ok=False,
                reason=f"retention_proofs[{idx}] duplicate proof_id",
                checked_count=idx,
                failed_index=idx,
            )
        seen.add(proof_id)
        refs = [proof["target_event_hash_hex"], proof["commit_event_hash_hex"]]
        if proof.get("redacted_event_hash_hex") is not None:
            refs.append(proof["redacted_event_hash_hex"])
        missing = [ref for ref in refs if ref not in event_hashes]
        if missing:
            return RetentionProofVerificationResult(
                ok=False,
                reason=f"retention_proofs[{idx}] contains dangling event refs: {missing}",
                checked_count=idx,
                failed_index=idx,
            )
    return RetentionProofVerificationResult(ok=True, reason=None, checked_count=len(proofs), failed_index=None)


__all__ = [
    "RETENTION_PROOF_SCHEMA_VERSION",
    "RetentionAction",
    "RetentionProofVerificationResult",
    "build_deletion_proof",
    "build_retention_marker",
    "validate_retention_proof",
    "verify_retention_proofs",
]
