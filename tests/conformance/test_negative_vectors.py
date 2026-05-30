# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Focused negative canonicalization vector coverage."""

from __future__ import annotations

import pytest

from attestplane.conformance.negative_vectors import (
    assert_negative_vector,
    load_negative_canonicalization_vectors,
)


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
        "canonicalization-negative-nested-array-order-v1",
        "canonicalization-negative-deep-nfc-string-v1",
        "canonicalization-negative-nested-float-prohibition-v1",
    }


@pytest.mark.parametrize(
    "vector", NEGATIVE_VECTORS, ids=lambda vector: vector["case_id"]
)
def test_negative_canonicalization_vectors_pin_reason_and_pointer(
    vector: dict[str, object],
) -> None:
    assert_negative_vector(vector)
