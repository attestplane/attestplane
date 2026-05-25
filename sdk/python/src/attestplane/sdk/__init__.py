# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Public SDK convenience namespace for Attestplane."""

from attestplane.hashchain import SUPPORTED_SCHEMA_VERSIONS
from attestplane.sdk.bundle import (
    EmptyProofBundleError,
    IncompleteProofBundleError,
    ProofBundleBuilder,
    ProofBundleError,
    raise_for_minimum_bundle_result,
    verify_minimum_bundle,
    verify_minimum_bundle_file,
)

__all__ = [
    "EmptyProofBundleError",
    "IncompleteProofBundleError",
    "ProofBundleBuilder",
    "ProofBundleError",
    "SUPPORTED_SCHEMA_VERSIONS",
    "raise_for_minimum_bundle_result",
    "verify_minimum_bundle",
    "verify_minimum_bundle_file",
]
