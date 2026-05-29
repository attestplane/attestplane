# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Negative canonicalization vector coverage for the Python SDK CI gate."""

from __future__ import annotations

import pytest

from attestplane.conformance.negative_vectors import (
    assert_negative_vector,
    classify_negative_vector,
    load_negative_canonicalization_vectors,
    materialize_negative_canonicalization_candidate,
    set_json_path,
)
from attestplane.conformance.run import main as run_conformance
from attestplane.verify_reason_codes import is_known_verify_reason_code

NEGATIVE_VECTORS = load_negative_canonicalization_vectors()


def test_negative_canonicalization_vector_set_is_versioned() -> None:
    assert {vector["surface"] for vector in NEGATIVE_VECTORS} == {"json", "text"}


def test_negative_canonicalization_vector_set_is_complete() -> None:
    assert {vector["case_id"] for vector in NEGATIVE_VECTORS} == {
        "canonicalization-negative-duplicate-json-keys-v1",
        "canonicalization-negative-embedded-nul-string-v1",
        "canonicalization-negative-invalid-surrogate-pair-string-v1",
        "canonicalization-negative-leading-zero-number-v1",
        "canonicalization-negative-non-minimal-number-v1",
        "canonicalization-negative-non-nfc-string-v1",
        "canonicalization-negative-non-sorted-object-keys-v1",
        "canonicalization-negative-schema-version-mismatch-v1",
        "canonicalization-negative-trailing-whitespace-v1",
    }


def test_negative_canonicalization_vector_reason_codes_are_known() -> None:
    assert all(is_known_verify_reason_code(vector["expected"]["reason_code"]) for vector in NEGATIVE_VECTORS)


@pytest.mark.parametrize("vector", NEGATIVE_VECTORS, ids=lambda vector: vector["case_id"])
def test_negative_canonicalization_vectors_pin_reason_and_pointer(
    vector: dict[str, object],
) -> None:
    assert_negative_vector(vector)
    result = classify_negative_vector(vector)
    assert result.detail


def test_negative_conformance_runner_requires_mode(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_conformance([]) == 2
    assert "--negative" in capsys.readouterr().err


def test_negative_conformance_runner_prints_vector_summary(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_conformance(["--negative"]) == 0
    out = capsys.readouterr().out
    assert "canonicalization-negative-duplicate-json-keys-v1" in out
    assert "att.verify.structure_invalid" in out


def test_negative_vector_classifier_surfaces_unexpected_canonical_json() -> None:
    vector = {
        "case_id": "synthetic-canonical-json",
        "expected": {"pointer": "/", "reason_code": "att.verify.canonical_mismatch"},
        "raw_json": {"a": 1},
        "surface": "json",
    }

    assert materialize_negative_canonicalization_candidate(vector) == {"a": 1}
    result = classify_negative_vector(vector)

    assert result.ok is False
    assert result.reason_code == "att.verify.canonical_mismatch"
    assert result.detail == "vector unexpectedly classified as canonical"


def test_negative_vector_json_path_helper_updates_nested_values() -> None:
    root = {"outer": [{"value": "old"}]}

    set_json_path(root, ["outer", 0, "value"], "new")

    assert root == {"outer": [{"value": "new"}]}
