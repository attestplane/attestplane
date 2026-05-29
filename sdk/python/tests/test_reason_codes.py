# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Unit + conformance tests for reason_codes.py (ADR-0010)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.reason_codes import (
    ALL_REASON_CODES_V1,
    REASON_CODE_DESCRIPTIONS,
    REASON_CODE_SCHEMA_VERSION,
    is_known_reason_code,
    reason_code_matches_format,
)

_VECTORS_PATH = Path(__file__).resolve().parent / "conformance" / "reason_codes_vectors.json"


def _load_vectors() -> dict:
    return json.loads(_VECTORS_PATH.read_text(encoding="utf-8"))


def test_schema_version_locked_at_1() -> None:
    assert REASON_CODE_SCHEMA_VERSION == 1


def test_vectors_file_loads() -> None:
    v = _load_vectors()
    assert v["$schema_version"] == 1
    assert v["reason_code_schema_version"] == 1
    assert v["expected_count"] == 25


def test_python_enum_matches_conformance_vector() -> None:
    """Python ALL_REASON_CODES_V1 must equal the frozen vector set."""
    v = _load_vectors()
    expected = set(v["all_reason_codes_v1"])
    assert frozenset(expected) == ALL_REASON_CODES_V1
    assert len(ALL_REASON_CODES_V1) == v["expected_count"]


def test_all_codes_have_descriptions() -> None:
    """Every enum value must have a single-sentence description."""
    for code in ALL_REASON_CODES_V1:
        assert code in REASON_CODE_DESCRIPTIONS, f"missing description for {code}"
        desc = REASON_CODE_DESCRIPTIONS[code]
        assert isinstance(desc, str) and len(desc) > 0


def test_descriptions_match_codes_exactly() -> None:
    """No description for an unknown code; no missing code."""
    assert set(REASON_CODE_DESCRIPTIONS.keys()) == ALL_REASON_CODES_V1


def test_is_known_reason_code() -> None:
    for code in ALL_REASON_CODES_V1:
        assert is_known_reason_code(code)
    assert not is_known_reason_code("NOT_A_REAL_CODE")
    assert not is_known_reason_code("")
    assert not is_known_reason_code("chain_ok")  # lowercase


def test_format_validation_positive() -> None:
    v = _load_vectors()
    for code in v["format_check_examples"]["valid"]:
        assert reason_code_matches_format(code), f"{code!r} should match"


def test_format_validation_negative() -> None:
    v = _load_vectors()
    for code in v["format_check_examples"]["invalid"]:
        assert not reason_code_matches_format(code), f"{code!r} should not match"


def test_code_groups_partition_enum_exactly() -> None:
    """Group flattening must equal ALL_REASON_CODES_V1 (no leaks, no duplicates)."""
    v = _load_vectors()
    flat: set[str] = set()
    for group_name, group in v["code_groups"].items():
        for code in group:
            assert code not in flat, f"duplicate {code!r} in group {group_name!r}"
            flat.add(code)
    assert flat == ALL_REASON_CODES_V1


def test_all_codes_match_regex() -> None:
    for code in ALL_REASON_CODES_V1:
        assert reason_code_matches_format(code), f"v1 code {code!r} fails own regex"


@pytest.mark.parametrize(
    "prefix,group",
    [
        ("CHAIN_", {"CHAIN_OK", "CHAIN_SEQ_MISMATCH", "CHAIN_PREV_HASH_MISMATCH", "CHAIN_EVENT_HASH_MISMATCH"}),
        (
            "SIGNATURE_",
            {
                "SIGNATURE_OK",
                "SIGNATURE_INVALID",
                "SIGNATURE_UNKNOWN_KEY",
                "SIGNATURE_EXPIRED_KEY",
                "SIGNATURE_SCHEMA_MISMATCH",
                "SIGNATURE_PAYLOAD_MISMATCH",
            },
        ),
        (
            "ANCHOR_",
            {
                "ANCHOR_OK",
                "ANCHOR_INVALID",
                "ANCHOR_CERT_EXPIRED",
                "ANCHOR_OCSP_FAILED",
                "ANCHOR_MISSING_LTV_ARTIFACTS",
            },
        ),
        (
            "PAYLOAD_",
            {
                "PAYLOAD_OK",
                "PAYLOAD_MISSING_REQUIRED_FIELD",
                "PAYLOAD_FIELD_TYPE_MISMATCH",
                "PAYLOAD_FIELD_VALUE_OUT_OF_RANGE",
                "PAYLOAD_FORBIDDEN_FIELD_PRESENT",
                "PAYLOAD_SCHEMA_VERSION_MISMATCH",
            },
        ),
    ],
)
def test_prefix_namespacing(prefix: str, group: set[str]) -> None:
    """Each verifier-path prefix groups its codes correctly."""
    actual = {c for c in ALL_REASON_CODES_V1 if c.startswith(prefix)}
    assert actual == group
