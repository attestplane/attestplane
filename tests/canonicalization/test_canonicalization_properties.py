# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Property coverage for restricted-JCS canonicalization invariants."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
from itertools import permutations
from pathlib import Path
import string
import sys
from typing import Any
import unicodedata

import pytest

from attestplane.canonical import (
    CanonicalizationError,
    INT64_MAX,
    INT64_MIN,
    canonicalize,
)
from attestplane.conformance.negative_vectors import (
    assert_negative_vector,
    load_negative_canonicalization_vectors,
)
from attestplane.types import SubjectRef

ROOT = Path(__file__).resolve().parents[2]
CANONICALIZATION_VECTOR_HELPER = (
    ROOT / "tests" / "conformance" / "canonicalization_vectors.py"
)


def _load_vector_manifest() -> Any:
    module_name = "attestplane_canonicalization_vectors"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(
        module_name, CANONICALIZATION_VECTOR_HELPER
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"could not load canonicalization vector helper from {CANONICALIZATION_VECTOR_HELPER}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


vector_manifest = _load_vector_manifest()
POSITIVE_VECTORS = vector_manifest.load_positive_canonicalization_vectors()
NEGATIVE_VECTORS = load_negative_canonicalization_vectors()

SAFE_ALPHABET = string.ascii_letters + string.digits + "-_.@/: " + "\u00e9\u03a9"
Stage = Callable[[Any], Any]


def _generated_values() -> tuple[Any, ...]:
    texts = ("", "plain", "line\nbreak", "\u00e9", "\u03a9", SAFE_ALPHABET[:12])
    primitives: tuple[Any, ...] = (
        None,
        True,
        False,
        0,
        -1,
        1,
        INT64_MIN,
        INT64_MAX,
        *texts,
    )
    nested: tuple[Any, ...] = (
        [primitives[0], primitives[3], primitives[8]],
        [INT64_MAX, {"inner": "\u00e9"}],
        {"b": 2, "a": 1},
        {"z": [False, {"m": INT64_MIN}], "a": "\u03a9"},
        ({"tuple": True}, "value"),
        b"",
        b"\x00\x01\xfe",
        datetime(2000, 1, 1, tzinfo=UTC),
        datetime(2030, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),
    )
    return primitives + nested


def _generated_restricted_json_values() -> tuple[Any, ...]:
    return tuple(
        value
        for value in _generated_values()
        if not isinstance(value, (bytes, datetime, tuple))
    )


def _assert_canonical_reparse_idempotent(value: Any) -> None:
    first = canonicalize(value)
    reparsed = json.loads(first.decode("utf-8"))
    assert canonicalize(reparsed) == first


def _sort_object_keys(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        value = {field.name: getattr(value, field.name) for field in fields(value)}
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise CanonicalizationError(
                    f"object keys must be strings (got {type(key).__name__!r})"
                )
        return {key: _sort_object_keys(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_sort_object_keys(item) for item in value]
    if isinstance(value, tuple):
        return [_sort_object_keys(item) for item in value]
    return value


def _validate_unicode_nfc(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        value = {field.name: getattr(value, field.name) for field in fields(value)}
    if isinstance(value, str):
        if unicodedata.normalize("NFC", value) != value:
            raise CanonicalizationError("string is not Unicode-NFC normalized")
        return value
    if isinstance(value, dict):
        return {
            _validate_unicode_nfc(key): _validate_unicode_nfc(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_validate_unicode_nfc(item) for item in value]
    if isinstance(value, tuple):
        return [_validate_unicode_nfc(item) for item in value]
    return value


def _validate_number_profile(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        value = {field.name: getattr(value, field.name) for field in fields(value)}
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        if not (INT64_MIN <= value <= INT64_MAX):
            raise CanonicalizationError("integer outside signed 64-bit range")
        return value
    if isinstance(value, float):
        raise CanonicalizationError("float values are forbidden in canonical payloads")
    if isinstance(value, dict):
        return {key: _validate_number_profile(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_validate_number_profile(item) for item in value]
    if isinstance(value, tuple):
        return [_validate_number_profile(item) for item in value]
    return value


def _apply_stages(value: Any, stages: tuple[Stage, ...]) -> Any:
    normalized = value
    for stage in stages:
        normalized = stage(normalized)
    return normalized


TABLE_VALUES: tuple[Any, ...] = (
    None,
    True,
    False,
    INT64_MIN,
    INT64_MAX,
    'line\\break\tand escaped quote "',
    b"\x00attestplane\xff",
    datetime(2026, 5, 22, 10, 11, 12, 123456, tzinfo=UTC),
    ["\u00e9", 0, {"z": b"payload", "a": None}],
    ("tuple", {"nested": [1, 2, 3]}),
    SubjectRef(scheme="opaque", value="subject-123"),
    {
        "z": {"omega": "\u03a9", "min": INT64_MIN},
        "a": [{"text": "\u00e9"}, {"max": INT64_MAX}],
    },
)


@pytest.mark.parametrize(
    "vector", POSITIVE_VECTORS, ids=lambda vector: vector["case_id"]
)
def test_canonicalization_property_positive_vectors_are_reparse_idempotent(
    vector: dict[str, Any],
) -> None:
    bundle = vector_manifest.emit_positive_canonicalization_bundle(vector)
    _assert_canonical_reparse_idempotent(bundle)


@pytest.mark.parametrize(
    "vector", NEGATIVE_VECTORS, ids=lambda vector: vector["case_id"]
)
def test_canonicalization_property_negative_vectors_are_named_and_classified(
    vector: dict[str, Any],
) -> None:
    assert_negative_vector(vector)


@pytest.mark.parametrize("value", TABLE_VALUES)
def test_canonicalization_property_table_values_are_reparse_idempotent(
    value: Any,
) -> None:
    _assert_canonical_reparse_idempotent(value)


@pytest.mark.parametrize("value", _generated_values())
def test_canonicalization_property_generated_values_are_reparse_idempotent(
    value: Any,
) -> None:
    _assert_canonical_reparse_idempotent(value)


@pytest.mark.parametrize("value", TABLE_VALUES)
def test_canonicalization_property_normalization_stage_order_is_commutative(
    value: Any,
) -> None:
    expected = canonicalize(value)
    stages = (_sort_object_keys, _validate_unicode_nfc, _validate_number_profile)

    for ordered_stages in permutations(stages):
        staged = _apply_stages(value, ordered_stages)
        assert canonicalize(staged) == expected


@pytest.mark.parametrize("value", _generated_restricted_json_values())
def test_canonicalization_property_generated_stage_order_is_commutative(
    value: Any,
) -> None:
    expected = canonicalize(value)
    stages = (_sort_object_keys, _validate_unicode_nfc, _validate_number_profile)

    for ordered_stages in permutations(stages):
        staged = _apply_stages(value, ordered_stages)
        assert canonicalize(staged) == expected


@pytest.mark.parametrize(
    "value",
    (
        "e\u0301",
        {"valid": ["nested", {"bad": "e\u0301"}]},
        {"too_large": INT64_MAX + 1},
        {"float": 1.5},
    ),
)
def test_canonicalization_property_invalid_inputs_still_reject(value: Any) -> None:
    with pytest.raises(CanonicalizationError):
        canonicalize(value)


def test_canonicalization_golden_fixture_reproduces_exact_bytes_and_digest() -> None:
    fixture = vector_manifest.load_canonicalization_golden_fixture()
    vector = vector_manifest.positive_canonicalization_vectors_by_case()[
        fixture["source_positive_case"]
    ]
    bundle = vector_manifest.emit_positive_canonicalization_bundle(vector)
    canonical_bytes = canonicalize(bundle)
    expected_bytes = fixture["canonical_bytes_path"].read_bytes()

    assert canonical_bytes == expected_bytes
    assert (
        hashlib.sha256(canonical_bytes).hexdigest()
        == fixture["canonical_bytes_sha256_hex"]
    )
    assert (
        fixture["generated_under"]["schema_version"]
        == bundle["chain_metadata"]["schema_version"]
    )
    assert (
        fixture["generated_under"]["taxonomy_version"]
        == bundle["chain_metadata"]["evidence_taxonomy_version"]
    )
