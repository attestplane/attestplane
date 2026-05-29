# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Frozen canonicalization golden fixture for cross-SDK byte stability."""

from __future__ import annotations

from pathlib import Path
from typing import Final

GENERATED_UNDER: Final[dict[str, int]] = {
    # Bundle schema version under which this fixture was generated.
    "schema_version": 1,
    # Verifier taxonomy version under which this fixture was generated.
    "taxonomy_version": 1,
}

SOURCE_POSITIVE_CASE: Final[str] = "canonicalization-positive-nfc-payload-string"
CANONICAL_BYTES_PATH: Final[Path] = Path(__file__).with_name(
    "canonicalization_golden_fixture.canonical.json"
)
CANONICAL_BYTES_SHA256_HEX: Final[str] = "fb51a4a6564c3bf9adec1b9059cda41fa0724aca6f09f580b216e7eeacd52e3d"

GOLDEN_FIXTURE: Final[dict[str, object]] = {
    "generated_under": GENERATED_UNDER,
    "source_positive_case": SOURCE_POSITIVE_CASE,
    "canonical_bytes_path": CANONICAL_BYTES_PATH,
    "canonical_bytes_sha256_hex": CANONICAL_BYTES_SHA256_HEX,
}

__all__ = [
    "CANONICAL_BYTES_PATH",
    "CANONICAL_BYTES_SHA256_HEX",
    "GENERATED_UNDER",
    "GOLDEN_FIXTURE",
    "SOURCE_POSITIVE_CASE",
]
