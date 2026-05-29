# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Vectors for the verifier taxonomy-version pin conformance checks."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALID_BUNDLE = ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"

VECTORS: tuple[dict[str, object], ...] = (
    {
        "case_id": "taxonomy-version-pin-1-passes",
        "bundle_path": VALID_BUNDLE,
        "require_taxonomy_version": 1,
        "expected_exit_code": 0,
        "expected_reason_code": None,
    },
    {
        "case_id": "taxonomy-version-pin-2-mismatch-fails",
        "bundle_path": VALID_BUNDLE,
        "require_taxonomy_version": 2,
        "expected_exit_code": 2,
        "expected_reason_code": "att.verify.schema_version_unsupported",
    },
)
