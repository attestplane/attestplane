# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Canonicalization conformance vectors for SDK minimum bundles."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any
import unicodedata

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk" / "python" / "src"))

from attestplane.canonical import CanonicalizationError  # noqa: E402
from attestplane.proof_bundle import ProofBundleBuilder  # noqa: E402
from attestplane.signing import InMemoryKeyProvider, Signer  # noqa: E402
from attestplane.verifier import verify_proof_bundle  # noqa: E402
from attestplane.verify_errors import VERIFY_OK  # noqa: E402

VECTOR_ROOT = ROOT / "tests" / "conformance" / "vectors" / "canonicalization"
POSITIVE_DIR = VECTOR_ROOT / "positive"
NEGATIVE_DIR = VECTOR_ROOT / "negative"


class DuplicateKeyError(ValueError):
    """Raised when a raw JSON object repeats a key."""


def _load_vectors(directory: Path) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]


POSITIVE_VECTORS = _load_vectors(POSITIVE_DIR)
NEGATIVE_VECTORS = _load_vectors(NEGATIVE_DIR)
POSITIVE_BY_CASE = {vector["case_id"]: vector for vector in POSITIVE_VECTORS}


def _parse_utc(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)


def _signer(vector: dict[str, Any]) -> Signer:
    now = _parse_utc(vector["now"])
    return Signer(
        chain_id=vector["case_id"],
        key_provider=InMemoryKeyProvider(seed=bytes.fromhex(vector["seed_hex"])),
        now=lambda: now,
    )


def _emit_positive_bundle(vector: dict[str, Any]) -> dict[str, Any]:
    assert vector["helper"] == "ProofBundleBuilder.minimal"
    return ProofBundleBuilder.minimal(
        vector["subject_digest"],
        _signer(vector),
        extra_payload=vector.get("extra_payload"),
        now=_parse_utc(vector["now"]),
        event_id=vector["event_id"],
    )


def _canonical_json(bundle: dict[str, Any]) -> str:
    return json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        seen.add(key)
        out[key] = value
    return out


def _assert_recursive_unique_keys(raw: str) -> None:
    json.loads(raw, object_pairs_hook=_reject_duplicate_keys)


def _set_path(root: dict[str, Any], path: list[Any], value: Any) -> None:
    cursor: Any = root
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = value


def _handcrafted_negative(vector: dict[str, Any]) -> dict[str, Any] | str:
    source = _emit_positive_bundle(POSITIVE_BY_CASE[vector["source_positive_case"]])
    mutation = vector["mutation"]
    if mutation["kind"] == "replace_path":
        mutated = deepcopy(source)
        _set_path(mutated, mutation["path"], mutation["value"])
        return mutated
    if mutation["kind"] == "duplicate_payload_key":
        raw = _canonical_json(source)
        subject_digest = POSITIVE_BY_CASE[vector["source_positive_case"]]["subject_digest"]
        needle = f'"payload":{{"duplicate_key_control":"unique","subject_digest":"{subject_digest}"}}'
        replacement = (
            f'"payload":{{"duplicate_key_control":"unique",'
            f'"subject_digest":"{subject_digest}","subject_digest":"{subject_digest}"}}'
        )
        assert needle in raw
        return raw.replace(needle, replacement, 1)
    if mutation["kind"] == "wrap_raw_json":
        return f'{mutation["prefix"]}{_canonical_json(source)}{mutation["suffix"]}'
    raise AssertionError(f"unknown mutation kind: {mutation['kind']}")


@pytest.mark.parametrize("vector", POSITIVE_VECTORS, ids=lambda vector: vector["case_id"])
def test_canonicalization_positive_minimum_bundle_vectors(vector: dict[str, Any]) -> None:
    bundle = _emit_positive_bundle(vector)
    result = verify_proof_bundle(bundle, **vector["verify_options"])
    raw = _canonical_json(bundle)

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
    candidate = _handcrafted_negative(vector)

    if vector["expected_error_code"] == "json.duplicate_key":
        assert isinstance(candidate, str)
        with pytest.raises(DuplicateKeyError):
            json.loads(candidate, object_pairs_hook=_reject_duplicate_keys)
        return

    if vector["expected_error_code"] == "json.non_canonical_envelope":
        assert isinstance(candidate, str)
        with pytest.raises(json.JSONDecodeError):
            json.loads(candidate, object_pairs_hook=_reject_duplicate_keys)
        return

    assert isinstance(candidate, dict)
    with pytest.raises(CanonicalizationError):
        verify_proof_bundle(candidate, **vector["verify_options"])
