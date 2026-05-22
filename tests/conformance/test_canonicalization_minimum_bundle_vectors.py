# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Canonicalization conformance vectors for SDK minimum bundles."""

from __future__ import annotations

import json
from typing import Any
import unicodedata

import pytest

from attestplane.canonical import CanonicalizationError  # noqa: E402
from attestplane.verifier import verify_proof_bundle  # noqa: E402
from attestplane.verify_errors import VERIFY_OK  # noqa: E402
from tests.conformance.canonicalization_vectors import (  # noqa: E402
    DuplicateKeyError,
    canonical_json_text,
    emit_positive_canonicalization_bundle,
    load_negative_canonicalization_vectors,
    load_positive_canonicalization_vectors,
    materialize_negative_canonicalization_candidate,
    reject_duplicate_keys,
)


POSITIVE_VECTORS = load_positive_canonicalization_vectors()
NEGATIVE_VECTORS = load_negative_canonicalization_vectors()


def _assert_recursive_unique_keys(raw: str) -> None:
    json.loads(raw, object_pairs_hook=reject_duplicate_keys)


@pytest.mark.parametrize("vector", POSITIVE_VECTORS, ids=lambda vector: vector["case_id"])
def test_canonicalization_positive_minimum_bundle_vectors(vector: dict[str, Any]) -> None:
    bundle = emit_positive_canonicalization_bundle(vector)
    result = verify_proof_bundle(bundle, **vector["verify_options"])
    raw = canonical_json_text(bundle)

    assert result.ok is vector["expected_ok"]
    assert result.error_code == VERIFY_OK
    for assertion in vector["assertions"]:
        if assertion == "recursive_unique_keys":
            _assert_recursive_unique_keys(raw)
        elif assertion == "payload_strings_are_nfc":
            payload_text = bundle["events"][0]["event"]["payload"]["payload_text"]
            assert unicodedata.normalize("NFC", payload_text) == payload_text
        elif assertion == "canonical_json_has_no_bom_or_trailing_bytes":
            assert not raw.startswith("\ufeff")
            assert raw == raw.strip()
        elif assertion == "int64_boundary_payload_is_accepted":
            value = bundle["events"][0]["event"]["payload"]["boundary_timestamp_us"]
            assert value == 9223372036854775807
        else:
            raise AssertionError(f"unknown assertion: {assertion}")


@pytest.mark.parametrize("vector", NEGATIVE_VECTORS, ids=lambda vector: vector["case_id"])
def test_canonicalization_minimum_bundle_negative_vectors(vector: dict[str, Any]) -> None:
    candidate = materialize_negative_canonicalization_candidate(vector)

    if vector["expected_error_code"] == "json.duplicate_key":
        assert isinstance(candidate, str)
        with pytest.raises(DuplicateKeyError):
            json.loads(candidate, object_pairs_hook=reject_duplicate_keys)
        return

    if vector["expected_error_code"] == "json.non_canonical_envelope":
        assert isinstance(candidate, str)
        with pytest.raises(json.JSONDecodeError):
            json.loads(candidate, object_pairs_hook=reject_duplicate_keys)
        return

    assert isinstance(candidate, dict)
    with pytest.raises(CanonicalizationError):
        verify_proof_bundle(candidate, **vector["verify_options"])
