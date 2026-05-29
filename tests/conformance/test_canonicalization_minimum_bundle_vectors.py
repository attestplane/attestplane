# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Canonicalization conformance vectors for SDK minimum bundles."""

from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import sys
from typing import Any
import unicodedata

import pytest

from attestplane.canonical import CanonicalizationError  # noqa: E402
from attestplane.verifier import verify_proof_bundle  # noqa: E402
from attestplane.verify_errors import VERIFY_OK  # noqa: E402


def _load_vector_manifest() -> Any:
    module_name = "attestplane_canonicalization_vectors"
    if module_name in sys.modules:
        return sys.modules[module_name]
    helper_path = Path(__file__).with_name("canonicalization_vectors.py")
    spec = importlib.util.spec_from_file_location(module_name, helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load canonicalization vector helper from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


vector_manifest = _load_vector_manifest()
DuplicateKeyError = vector_manifest.DuplicateKeyError


POSITIVE_VECTORS = vector_manifest.load_positive_canonicalization_vectors()
NEGATIVE_VECTORS = vector_manifest.load_negative_canonicalization_vectors()


def _assert_recursive_unique_keys(raw: str) -> None:
    json.loads(raw, object_pairs_hook=vector_manifest.reject_duplicate_keys)


def _classify_negative_reason_code(vector: dict[str, Any], candidate: Any) -> str:
    expected_reason_code = vector["expected_reason_code"]
    if expected_reason_code == "json.duplicate_key":
        assert isinstance(candidate, str)
        with pytest.raises(vector_manifest.DuplicateKeyError) as excinfo:
            json.loads(candidate, object_pairs_hook=vector_manifest.reject_duplicate_keys)
        assert "duplicate JSON key" in str(excinfo.value)
        return expected_reason_code

    if expected_reason_code == "json.non_canonical_envelope":
        assert isinstance(candidate, str)
        with pytest.raises(json.JSONDecodeError) as excinfo:
            json.loads(candidate, object_pairs_hook=vector_manifest.reject_duplicate_keys)
        assert excinfo.value.msg
        return expected_reason_code

    assert isinstance(candidate, dict)
    with pytest.raises(CanonicalizationError) as excinfo:
        verify_proof_bundle(candidate, **vector.get("verify_options", {}))
    assert str(excinfo.value)
    return expected_reason_code


@pytest.mark.parametrize("vector", POSITIVE_VECTORS, ids=lambda vector: vector["case_id"])
def test_canonicalization_positive_minimum_bundle_vectors(vector: dict[str, Any]) -> None:
    bundle = vector_manifest.emit_positive_canonicalization_bundle(vector)
    result = verify_proof_bundle(bundle, **vector["verify_options"])
    raw = vector_manifest.canonical_json_text(bundle)

    assert result.ok is vector["expected_ok"]
    assert result.error_code == VERIFY_OK
    if "expected_canonical_sha256" in vector:
        assert hashlib.sha256(raw.encode("utf-8")).hexdigest() == vector["expected_canonical_sha256"]
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
        elif assertion == "future_bundle_field_is_preserved":
            assert bundle["future_bundle_field"] == {"preserved": True}
        else:
            raise AssertionError(f"unknown assertion: {assertion}")


@pytest.mark.parametrize("vector", NEGATIVE_VECTORS, ids=lambda vector: vector["case_id"])
def test_canonicalization_minimum_bundle_negative_vectors(vector: dict[str, Any]) -> None:
    candidate = vector_manifest.materialize_negative_canonicalization_candidate(vector)
    reason_code = _classify_negative_reason_code(vector, candidate)
    assert reason_code == vector["expected_reason_code"], vector["case_id"]
