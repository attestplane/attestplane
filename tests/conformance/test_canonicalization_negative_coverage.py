# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Coverage matrix for canonicalization negative edge classes."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NEGATIVE_DIRS = (
    ROOT / "tests" / "conformance" / "vectors" / "canonicalization" / "negative",
    ROOT
    / "tests"
    / "conformance"
    / "vectors"
    / "canonicalization"
    / "negative"
    / "v1",
)

EDGE_TO_CASE_IDS = {
    "nfc": {"canonicalization-negative-non-nfc-string-v1"},
    "nfd": {"canonicalization-negative-nfd-payload-string"},
    "bom": {"canonicalization-negative-bom-trailing-bytes-raw"},
    "surrogate": {"canonicalization-negative-invalid-surrogate-pair-string-v1"},
    "int-canon": {
        "canonicalization-negative-leading-zero-number-v1",
        "canonicalization-negative-non-minimal-number-v1",
        "canonicalization-negative-int64-overflow-timestamp-payload",
    },
    "key-order": {"canonicalization-negative-non-sorted-object-keys-v1"},
    "dup-keys": {
        "canonicalization-negative-duplicate-json-keys-v1",
        "canonicalization-negative-duplicate-json-keys-raw",
    },
}


def _negative_case_ids() -> set[str]:
    return {
        json.loads(path.read_text(encoding="utf-8"))["case_id"]
        for directory in NEGATIVE_DIRS
        for path in directory.glob("*.json")
    }


def test_canonicalization_negative_edge_coverage() -> None:
    case_ids = _negative_case_ids()
    missing = {
        edge: sorted(expected - case_ids)
        for edge, expected in EDGE_TO_CASE_IDS.items()
        if not (case_ids & expected)
    }

    assert not missing, missing
