# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""SDK-facing proof-bundle helpers.

This module keeps the lower-level verifier's result-returning API intact while
offering strict SDK helpers that raise typed exceptions for the minimum-valid
proof-bundle contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from attestplane.proof_bundle import (
    EmptyProofBundleError,
    IncompleteProofBundleError,
    ProofBundleBuilder,
    ProofBundleError,
)
from attestplane.verifier import BundleVerificationResult, verify_proof_bundle, verify_proof_bundle_file
from attestplane.verify_errors import VERIFY_BUNDLE_SCHEMA_INCOMPLETE, VERIFY_REQUIRED_FIELDS_MISSING


def raise_for_minimum_bundle_result(result: BundleVerificationResult) -> None:
    """Raise a typed SDK exception when strict minimum-bundle verification failed."""
    if result.ok:
        return
    if result.error_code == VERIFY_REQUIRED_FIELDS_MISSING:
        raise EmptyProofBundleError(
            result.metadata_reason or "proof bundle must contain at least one event",
            error_code=result.error_code,
        )
    if result.error_code == VERIFY_BUNDLE_SCHEMA_INCOMPLETE:
        raise IncompleteProofBundleError(
            result.signed_attestation_schema_reason or "proof bundle lacks the minimum signed-attestation schema",
            error_code=result.error_code,
        )
    raise IncompleteProofBundleError(result.short_summary(), error_code=result.error_code)


def verify_minimum_bundle(bundle: dict[str, Any]) -> BundleVerificationResult:
    """Verify ``bundle`` as a minimum-valid strict proof bundle or raise a typed error."""
    result = verify_proof_bundle(
        bundle,
        require_non_empty=True,
        require_signed_attestation=True,
    )
    raise_for_minimum_bundle_result(result)
    return result


def verify_minimum_bundle_file(path: str | Path) -> BundleVerificationResult:
    """Load and verify a minimum-valid strict proof bundle or raise a typed error."""
    result = verify_proof_bundle_file(
        path,
        require_non_empty=True,
        require_signed_attestation=True,
    )
    raise_for_minimum_bundle_result(result)
    return result


def verify(path: str | Path) -> BundleVerificationResult:
    """Verify a proof bundle file and return the SDK result object."""
    return verify_proof_bundle_file(path)


__all__ = [
    "EmptyProofBundleError",
    "IncompleteProofBundleError",
    "ProofBundleBuilder",
    "ProofBundleError",
    "raise_for_minimum_bundle_result",
    "verify",
    "verify_minimum_bundle",
    "verify_minimum_bundle_file",
]
