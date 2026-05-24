# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Coverage matrix for the landed canonicalization negative edge cases."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NEGATIVE_DIR = (
    ROOT / "tests" / "conformance" / "vectors" / "canonicalization" / "negative"
)

EDGE_MATRIX = (
    (
        "nfc",
        NEGATIVE_DIR / "v1" / "non-nfc-string.json",
        "expected.reason_code",
        "att.verify.canonical_mismatch",
    ),
    (
        "nfd",
        NEGATIVE_DIR / "nfd-payload-string.json",
        "expected_error_code",
        "canonicalization.nfc",
    ),
    (
        "bom",
        NEGATIVE_DIR / "bom-trailing-bytes-raw.json",
        "expected_error_code",
        "json.non_canonical_envelope",
    ),
    (
        "surrogate",
        NEGATIVE_DIR / "v1" / "invalid-surrogate-pair-string.json",
        "expected.reason_code",
        "att.verify.schema_invalid",
    ),
    (
        "int-canon",
        NEGATIVE_DIR / "v1" / "non-minimal-number.json",
        "expected.reason_code",
        "att.verify.canonical_mismatch",
    ),
    (
        "key-order",
        NEGATIVE_DIR / "v1" / "non-sorted-object-keys.json",
        "expected.reason_code",
        "att.verify.canonical_mismatch",
    ),
    (
        "dup-keys",
        NEGATIVE_DIR / "v1" / "duplicate-json-keys.json",
        "expected.reason_code",
        "att.verify.structure_invalid",
    ),
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _field(vector: dict[str, object], dotted_path: str) -> object:
    value: object = vector
    for part in dotted_path.split("."):
        assert isinstance(value, dict)
        value = value[part]
    return value


def test_canonicalization_negative_edge_matrix_is_complete() -> None:
    seen_edges = set()

    for edge, path, reason_path, expected_reason in EDGE_MATRIX:
        vector = _load(path)
        seen_edges.add(edge)
        assert path.exists(), path
        assert _field(vector, reason_path) == expected_reason

    assert seen_edges == {edge for edge, *_ in EDGE_MATRIX}
