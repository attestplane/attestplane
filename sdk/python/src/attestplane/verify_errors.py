# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Stable verifier error taxonomy for machine-readable CLI output.

This module is intentionally separate from ADR-0010 ``ReasonCodeV1``.  The
reason-code enum is frozen for chain/event verification semantics; these
``VERIFY_*`` strings classify verifier and CLI outcomes without widening the
frozen enum.
"""

from __future__ import annotations

from typing import Final, Literal

VERIFY_ERROR_SCHEMA_VERSION: Final[int] = 1

VerifyErrorCode = Literal[
    "VERIFY_OK",
    "VERIFY_IO_ERROR",
    "VERIFY_SCHEMA_ERROR",
    "bundle.schema.incomplete",
    "VERIFY_CHAIN_RECOMPUTE_FAILED",
    "VERIFY_METADATA_CLOSURE_FAILED",
    "VERIFY_POLICY_TRACE_REFS_FAILED",
    "VERIFY_RETENTION_PROOF_FAILED",
    "VERIFY_ARTIFACT_HASH_FAILED",
    "VERIFY_REQUIRED_FIELDS_MISSING",
    "VERIFY_EXTENSION_INVALID_INPUT",
    "VERIFY_EXTENSION_UNSUPPORTED",
    "VERIFY_EXTENSION_FAILED",
]

VERIFY_OK: Final[VerifyErrorCode] = "VERIFY_OK"
VERIFY_IO_ERROR: Final[VerifyErrorCode] = "VERIFY_IO_ERROR"
VERIFY_SCHEMA_ERROR: Final[VerifyErrorCode] = "VERIFY_SCHEMA_ERROR"
VERIFY_BUNDLE_SCHEMA_INCOMPLETE: Final[VerifyErrorCode] = "bundle.schema.incomplete"
VERIFY_CHAIN_RECOMPUTE_FAILED: Final[VerifyErrorCode] = "VERIFY_CHAIN_RECOMPUTE_FAILED"
VERIFY_METADATA_CLOSURE_FAILED: Final[VerifyErrorCode] = "VERIFY_METADATA_CLOSURE_FAILED"
VERIFY_POLICY_TRACE_REFS_FAILED: Final[VerifyErrorCode] = "VERIFY_POLICY_TRACE_REFS_FAILED"
VERIFY_RETENTION_PROOF_FAILED: Final[VerifyErrorCode] = "VERIFY_RETENTION_PROOF_FAILED"
VERIFY_ARTIFACT_HASH_FAILED: Final[VerifyErrorCode] = "VERIFY_ARTIFACT_HASH_FAILED"
VERIFY_REQUIRED_FIELDS_MISSING: Final[VerifyErrorCode] = "VERIFY_REQUIRED_FIELDS_MISSING"
VERIFY_EXTENSION_INVALID_INPUT: Final[VerifyErrorCode] = "VERIFY_EXTENSION_INVALID_INPUT"
VERIFY_EXTENSION_UNSUPPORTED: Final[VerifyErrorCode] = "VERIFY_EXTENSION_UNSUPPORTED"
VERIFY_EXTENSION_FAILED: Final[VerifyErrorCode] = "VERIFY_EXTENSION_FAILED"

ALL_VERIFY_ERROR_CODES_V1: Final[tuple[VerifyErrorCode, ...]] = (
    VERIFY_OK,
    VERIFY_IO_ERROR,
    VERIFY_SCHEMA_ERROR,
    VERIFY_BUNDLE_SCHEMA_INCOMPLETE,
    VERIFY_CHAIN_RECOMPUTE_FAILED,
    VERIFY_METADATA_CLOSURE_FAILED,
    VERIFY_POLICY_TRACE_REFS_FAILED,
    VERIFY_RETENTION_PROOF_FAILED,
    VERIFY_ARTIFACT_HASH_FAILED,
    VERIFY_REQUIRED_FIELDS_MISSING,
    VERIFY_EXTENSION_INVALID_INPUT,
    VERIFY_EXTENSION_UNSUPPORTED,
    VERIFY_EXTENSION_FAILED,
)

VERIFY_ERROR_DESCRIPTIONS: Final[dict[VerifyErrorCode, str]] = {
    VERIFY_OK: "Verification completed without a verifier-detected failure.",
    VERIFY_IO_ERROR: "The verifier could not read the requested input.",
    VERIFY_SCHEMA_ERROR: "The input shape is unsupported or malformed.",
    VERIFY_BUNDLE_SCHEMA_INCOMPLETE: (
        "The proof bundle lacks the minimum signed-attestation schema required by strict verification."
    ),
    VERIFY_CHAIN_RECOMPUTE_FAILED: "Recomputed hash-chain verification failed.",
    VERIFY_METADATA_CLOSURE_FAILED: "Bundle metadata disagrees with recomputed chain state.",
    VERIFY_POLICY_TRACE_REFS_FAILED: "Policy trace references are missing, dangling, duplicated, or out of order.",
    VERIFY_RETENTION_PROOF_FAILED: (
        "Retention/deletion proof references are malformed or do not point at bundle events."
    ),
    VERIFY_ARTIFACT_HASH_FAILED: "The envelope artifact hash does not match the embedded proof bundle.",
    VERIFY_REQUIRED_FIELDS_MISSING: "A required verifier-envelope field is missing.",
    VERIFY_EXTENSION_INVALID_INPUT: "Requested signature or anchor extension input is malformed.",
    VERIFY_EXTENSION_UNSUPPORTED: "Requested signature or anchor extension input uses an unsupported mode.",
    VERIFY_EXTENSION_FAILED: "Requested signature or anchor extension verification failed.",
}


def is_known_verify_error_code(value: str) -> bool:
    """Return True when ``value`` is a v1 verifier error-code string."""
    return value in ALL_VERIFY_ERROR_CODES_V1


__all__ = [
    "ALL_VERIFY_ERROR_CODES_V1",
    "VERIFY_ARTIFACT_HASH_FAILED",
    "VERIFY_BUNDLE_SCHEMA_INCOMPLETE",
    "VERIFY_CHAIN_RECOMPUTE_FAILED",
    "VERIFY_ERROR_DESCRIPTIONS",
    "VERIFY_ERROR_SCHEMA_VERSION",
    "VERIFY_EXTENSION_FAILED",
    "VERIFY_EXTENSION_INVALID_INPUT",
    "VERIFY_EXTENSION_UNSUPPORTED",
    "VERIFY_IO_ERROR",
    "VERIFY_METADATA_CLOSURE_FAILED",
    "VERIFY_OK",
    "VERIFY_POLICY_TRACE_REFS_FAILED",
    "VERIFY_REQUIRED_FIELDS_MISSING",
    "VERIFY_RETENTION_PROOF_FAILED",
    "VERIFY_SCHEMA_ERROR",
    "VerifyErrorCode",
    "is_known_verify_error_code",
]
