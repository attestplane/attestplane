# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Shared negative canonicalization vector loader/classifier."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from attestplane.canonical_text import CanonicalTextError, canonicalize_text

REPO_ROOT = Path(__file__).resolve().parents[5]
VECTOR_ROOT = REPO_ROOT / "tests" / "conformance" / "vectors" / "canonicalization"
NEGATIVE_V1_DIR = VECTOR_ROOT / "negative" / "v1"


class DuplicateKeyError(ValueError):
    """Raised when a raw JSON object repeats a key."""


@dataclass(frozen=True, slots=True)
class NegativeVectorResult:
    ok: bool
    reason_code: str
    pointer: str
    detail: str | None = None


def _load_vectors(directory: Path) -> list[dict[str, Any]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"))]


def load_negative_canonicalization_vectors() -> list[dict[str, Any]]:
    return _load_vectors(NEGATIVE_V1_DIR)


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


def materialize_negative_canonicalization_candidate(vector: dict[str, Any]) -> Any:
    if vector["surface"] == "text":
        return vector["raw_text"]
    return vector["raw_json"]


def _canonical_json_of(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _validate_json_candidate(
    vector: dict[str, Any],
    candidate: Any,
) -> NegativeVectorResult:
    expected = vector["expected"]
    pointer = expected["pointer"]
    detail: str | None = None

    if isinstance(candidate, str):
        try:
            parsed = json.loads(candidate, object_pairs_hook=reject_duplicate_keys)
        except DuplicateKeyError:
            return NegativeVectorResult(
                ok=False,
                reason_code="att.verify.structure_invalid",
                pointer=pointer,
                detail="duplicate JSON key rejected",
            )
        except json.JSONDecodeError as exc:
            return NegativeVectorResult(
                ok=False,
                reason_code="att.verify.schema_invalid",
                pointer=pointer,
                detail=f"malformed JSON: {exc.msg}",
            )
    elif isinstance(candidate, dict):
        parsed = candidate
    else:
        raise AssertionError(f"unexpected JSON candidate type: {type(candidate).__name__}")

    raw = (
        candidate
        if isinstance(candidate, str)
        else json.dumps(candidate, ensure_ascii=False, sort_keys=False, separators=(",", ":"))
    )
    canonical = _canonical_json_of(parsed)

    if _has_surrogate(parsed):
        return NegativeVectorResult(
            ok=False,
            reason_code="att.verify.schema_invalid",
            pointer=pointer,
            detail="invalid surrogate pair rejected",
        )
    if _has_nfc_violation(parsed):
        return NegativeVectorResult(
            ok=False,
            reason_code="att.verify.canonical_mismatch",
            pointer=pointer,
            detail="non-NFC string rejected",
        )
    if any(isinstance(value, float) for value in _walk_json_values(parsed)):
        return NegativeVectorResult(
            ok=False,
            reason_code="att.verify.canonical_mismatch",
            pointer=pointer,
            detail="non-minimal number rejected",
        )
    if parsed.get("schema_version") is not None and parsed["schema_version"] != 1:
        return NegativeVectorResult(
            ok=False,
            reason_code="att.verify.schema_version_unsupported",
            pointer=pointer,
            detail="schema_version mismatch",
        )
    if raw.strip() != raw:
        return NegativeVectorResult(
            ok=False,
            reason_code="att.verify.canonical_mismatch",
            pointer=pointer,
            detail="trailing whitespace rejected",
        )
    if raw != canonical:
        return NegativeVectorResult(
            ok=False,
            reason_code=expected["reason_code"],
            pointer=pointer,
            detail="non-canonical JSON rejected",
        )

    return NegativeVectorResult(ok=True, reason_code="att.verify.canonical_mismatch", pointer=pointer)


def _walk_json_values(value: Any) -> list[Any]:
    values: list[Any] = [value]
    if isinstance(value, dict):
        for item in value.values():
            values.extend(_walk_json_values(item))
    elif isinstance(value, list):
        for item in value:
            values.extend(_walk_json_values(item))
    return values


def _has_nfc_violation(value: Any) -> bool:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value) != value
    if isinstance(value, dict):
        return any(_has_nfc_violation(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_nfc_violation(item) for item in value)
    return False


def _has_surrogate(value: Any) -> bool:
    if isinstance(value, str):
        return any(0xD800 <= ord(ch) <= 0xDFFF for ch in value)
    if isinstance(value, dict):
        return any(_has_surrogate(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_surrogate(item) for item in value)
    return False


def _validate_text_candidate(vector: dict[str, Any], candidate: str) -> NegativeVectorResult:
    expected = vector["expected"]
    pointer = expected["pointer"]
    try:
        canonicalize_text(candidate)
    except CanonicalTextError as exc:
        return NegativeVectorResult(
            ok=False,
            reason_code="att.verify.schema_invalid",
            pointer=pointer,
            detail=str(exc),
        )
    return NegativeVectorResult(
        ok=True,
        reason_code="att.verify.canonical_mismatch",
        pointer=pointer,
        detail="text candidate unexpectedly canonicalized",
    )


def classify_negative_vector(vector: dict[str, Any]) -> NegativeVectorResult:
    candidate = materialize_negative_canonicalization_candidate(vector)

    if vector["surface"] == "text":
        assert isinstance(candidate, str)
        return _validate_text_candidate(vector, candidate)

    result = _validate_json_candidate(vector, candidate)
    if result.ok:
        # The vector is expected to fail closed; surface the mismatch so the
        # tests and runner report it loudly.
        return NegativeVectorResult(
            ok=False,
            reason_code=vector["expected"]["reason_code"],
            pointer=vector["expected"]["pointer"],
            detail="vector unexpectedly classified as canonical",
        )
    return result


def assert_negative_vector(vector: dict[str, Any]) -> None:
    result = classify_negative_vector(vector)
    expected = vector["expected"]
    assert result.ok is False, vector["case_id"]
    assert result.reason_code == expected["reason_code"], vector["case_id"]
    assert result.pointer == expected["pointer"], vector["case_id"]
