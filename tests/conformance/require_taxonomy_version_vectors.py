# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Conformance vectors for ``attestplane verify --require-taxonomy-version``."""

from __future__ import annotations

from pathlib import Path

from attestplane.verify_reason_codes import VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED

ROOT = Path(__file__).resolve().parents[2]
MATCHING_BUNDLE = ROOT / "tests" / "conformance" / "schema_version" / "additive_minor_ok" / "bundle.json"

REQUIRE_TAXONOMY_VERSION_VECTORS = (
    {
        "case_id": "require_taxonomy_version_mismatch",
        "bundle_path": MATCHING_BUNDLE,
        "require_taxonomy_version": 2,
        "expected_exit_code": 2,
        "expected_reason_code": VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
    },
)

