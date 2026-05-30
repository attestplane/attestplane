# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Shared canonicalization vector manifest and minimum-bundle emitter."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

from attestplane.proof_bundle import ProofBundleBuilder
from attestplane.signing import InMemoryKeyProvider, Signer

ROOT = Path(__file__).resolve().parents[2]
VECTOR_ROOT = ROOT / "tests" / "conformance" / "vectors" / "canonicalization"
POSITIVE_DIR = VECTOR_ROOT / "positive"
NEGATIVE_DIR = VECTOR_ROOT / "negative"
GOLDEN_FIXTURE_HELPER = (
    ROOT / "tests" / "conformance" / "canonicalization_golden_fixture.py"
)


class DuplicateKeyError(ValueError):
    """Raised when a raw JSON object repeats a key."""


def _load_vectors(directory: Path) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]


def load_positive_canonicalization_vectors() -> list[dict[str, Any]]:
    return _load_vectors(POSITIVE_DIR)


def load_positive_vectors() -> list[dict[str, Any]]:
    return load_positive_canonicalization_vectors()


def load_negative_canonicalization_vectors() -> list[dict[str, Any]]:
    return _load_vectors(NEGATIVE_DIR)


def load_negative_vectors() -> list[dict[str, Any]]:
    return load_negative_canonicalization_vectors()


def load_canonicalization_golden_fixture() -> dict[str, Any]:
    module_name = "attestplane_canonicalization_golden_fixture"
    if module_name in sys.modules:
        return sys.modules[module_name].GOLDEN_FIXTURE
    spec = importlib.util.spec_from_file_location(module_name, GOLDEN_FIXTURE_HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"could not load canonicalization golden fixture helper from {GOLDEN_FIXTURE_HELPER}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.GOLDEN_FIXTURE


def positive_canonicalization_vectors_by_case() -> dict[str, dict[str, Any]]:
    return {
        vector["case_id"]: vector for vector in load_positive_canonicalization_vectors()
    }


def parse_vector_utc(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)


def signer_for_canonicalization_vector(vector: dict[str, Any]) -> Signer:
    now = parse_vector_utc(vector["now"])
    return Signer(
        chain_id=vector["case_id"],
        key_provider=InMemoryKeyProvider(seed=bytes.fromhex(vector["seed_hex"])),
        now=lambda: now,
    )


def emit_positive_canonicalization_bundle(vector: dict[str, Any]) -> dict[str, Any]:
    assert vector["helper"] == "ProofBundleBuilder.minimal"
    return ProofBundleBuilder.minimal(
        vector["subject_digest"],
        signer_for_canonicalization_vector(vector),
        extra_payload=vector.get("extra_payload"),
        extra_chain_metadata=vector.get("extra_chain_metadata"),
        now=parse_vector_utc(vector["now"]),
        event_id=vector["event_id"],
    )


def emit_positive_bundle(vector: dict[str, Any]) -> dict[str, Any]:
    return emit_positive_canonicalization_bundle(vector)


def canonical_json_text(bundle: dict[str, Any]) -> str:
    return json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        seen.add(key)
        out[key] = value
    return out


def set_json_path(root: dict[str, Any], path: list[Any], value: Any) -> None:
    cursor: Any = root
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = value


def materialize_negative_canonicalization_candidate(
    vector: dict[str, Any],
) -> dict[str, Any] | str:
    positives_by_case = positive_canonicalization_vectors_by_case()
    source_vector = positives_by_case[vector["source_positive_case"]]
    source = emit_positive_canonicalization_bundle(source_vector)
    mutation = vector["mutation"]
    if mutation["kind"] == "replace_path":
        mutated = deepcopy(source)
        set_json_path(mutated, mutation["path"], mutation["value"])
        return mutated
    if mutation["kind"] == "duplicate_payload_key":
        raw = canonical_json_text(source)
        subject_digest = source_vector["subject_digest"]
        needle = (
            f'"payload":{{"duplicate_key_control":"unique",'
            f'"subject_digest":"{subject_digest}"}}'
        )
        replacement = (
            f'"payload":{{"duplicate_key_control":"unique",'
            f'"subject_digest":"{subject_digest}","subject_digest":"{subject_digest}"}}'
        )
        assert needle in raw
        return raw.replace(needle, replacement, 1)
    if mutation["kind"] == "wrap_raw_json":
        return f"{mutation['prefix']}{canonical_json_text(source)}{mutation['suffix']}"
    raise AssertionError(f"unknown mutation kind: {mutation['kind']}")


def materialize_negative_candidate(vector: dict[str, Any]) -> dict[str, Any] | str:
    return materialize_negative_canonicalization_candidate(vector)
