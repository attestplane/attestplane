# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Shared canonicalization negative coverage matrix helpers."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
NEGATIVE_ROOT = ROOT / "tests" / "conformance" / "vectors" / "canonicalization" / "negative"
MATRIX_PATH = ROOT / "tests" / "conformance" / "canonicalization_negative_matrix.md"


@dataclass(frozen=True, slots=True)
class VectorSpec:
    label: str
    path: Path
    case_id: str
    expected_reason_code: str


@dataclass(frozen=True, slots=True)
class EdgeRow:
    edge_id: str
    description: str
    covered_labels: tuple[str, ...]


VECTOR_SPECS: tuple[VectorSpec, ...] = (
    VectorSpec(
        label="bom-trailing-bytes-raw.json",
        path=NEGATIVE_ROOT / "bom-trailing-bytes-raw.json",
        case_id="canonicalization-negative-bom-trailing-bytes-raw",
        expected_reason_code="json.non_canonical_envelope",
    ),
    VectorSpec(
        label="duplicate-json-keys-raw.json",
        path=NEGATIVE_ROOT / "duplicate-json-keys-raw.json",
        case_id="canonicalization-negative-duplicate-json-keys-raw",
        expected_reason_code="json.duplicate_key",
    ),
    VectorSpec(
        label="int64-overflow-timestamp-payload.json",
        path=NEGATIVE_ROOT / "int64-overflow-timestamp-payload.json",
        case_id="canonicalization-negative-int64-overflow-timestamp-payload",
        expected_reason_code="canonicalization.int64",
    ),
    VectorSpec(
        label="nfd-payload-string.json",
        path=NEGATIVE_ROOT / "nfd-payload-string.json",
        case_id="canonicalization-negative-nfd-payload-string",
        expected_reason_code="canonicalization.nfc",
    ),
    VectorSpec(
        label="v1/duplicate-json-keys.json",
        path=NEGATIVE_ROOT / "v1" / "duplicate-json-keys.json",
        case_id="canonicalization-negative-duplicate-json-keys-v1",
        expected_reason_code="att.verify.structure_invalid",
    ),
    VectorSpec(
        label="v1/embedded-nul-string.json",
        path=NEGATIVE_ROOT / "v1" / "embedded-nul-string.json",
        case_id="canonicalization-negative-embedded-nul-string-v1",
        expected_reason_code="att.verify.schema_invalid",
    ),
    VectorSpec(
        label="v1/invalid-surrogate-pair-string.json",
        path=NEGATIVE_ROOT / "v1" / "invalid-surrogate-pair-string.json",
        case_id="canonicalization-negative-invalid-surrogate-pair-string-v1",
        expected_reason_code="att.verify.schema_invalid",
    ),
    VectorSpec(
        label="v1/leading-zero-number.json",
        path=NEGATIVE_ROOT / "v1" / "leading-zero-number.json",
        case_id="canonicalization-negative-leading-zero-number-v1",
        expected_reason_code="att.verify.schema_invalid",
    ),
    VectorSpec(
        label="v1/non-minimal-number.json",
        path=NEGATIVE_ROOT / "v1" / "non-minimal-number.json",
        case_id="canonicalization-negative-non-minimal-number-v1",
        expected_reason_code="att.verify.canonical_mismatch",
    ),
    VectorSpec(
        label="v1/non-nfc-string.json",
        path=NEGATIVE_ROOT / "v1" / "non-nfc-string.json",
        case_id="canonicalization-negative-non-nfc-string-v1",
        expected_reason_code="att.verify.canonical_mismatch",
    ),
    VectorSpec(
        label="v1/non-sorted-object-keys.json",
        path=NEGATIVE_ROOT / "v1" / "non-sorted-object-keys.json",
        case_id="canonicalization-negative-non-sorted-object-keys-v1",
        expected_reason_code="att.verify.canonical_mismatch",
    ),
    VectorSpec(
        label="v1/schema-version-mismatch.json",
        path=NEGATIVE_ROOT / "v1" / "schema-version-mismatch.json",
        case_id="canonicalization-negative-schema-version-mismatch-v1",
        expected_reason_code="att.verify.schema_version_unsupported",
    ),
    VectorSpec(
        label="v1/trailing-whitespace.json",
        path=NEGATIVE_ROOT / "v1" / "trailing-whitespace.json",
        case_id="canonicalization-negative-trailing-whitespace-v1",
        expected_reason_code="att.verify.canonical_mismatch",
    ),
)


EDGE_ROWS: tuple[EdgeRow, ...] = (
    EdgeRow(
        edge_id="dup-keys",
        description="Duplicate JSON keys must fail closed before a dict collapse hides the duplicate.",
        covered_labels=("duplicate-json-keys-raw.json", "v1/duplicate-json-keys.json"),
    ),
    EdgeRow(
        edge_id="embedded-nul",
        description="A raw text input containing U+0000 must fail the text canonicalizer.",
        covered_labels=("v1/embedded-nul-string.json",),
    ),
    EdgeRow(
        edge_id="surrogate",
        description="A raw text input containing an unpaired surrogate must fail the text canonicalizer.",
        covered_labels=("v1/invalid-surrogate-pair-string.json",),
    ),
    EdgeRow(
        edge_id="int-canon",
        description="Integer and number edge cases must reject non-canonical encodings.",
        covered_labels=(
            "int64-overflow-timestamp-payload.json",
            "v1/leading-zero-number.json",
            "v1/non-minimal-number.json",
        ),
    ),
    EdgeRow(
        edge_id="nfc",
        description="A decomposed Unicode string must fail canonicalization.",
        covered_labels=("v1/non-nfc-string.json",),
    ),
    EdgeRow(
        edge_id="nfd",
        description="A helper-emitted NFC payload rewritten as NFD must fail canonicalization.",
        covered_labels=("nfd-payload-string.json",),
    ),
    EdgeRow(
        edge_id="bom",
        description="A raw JSON envelope with a UTF-8 BOM prefix and trailing bytes must fail.",
        covered_labels=("bom-trailing-bytes-raw.json",),
    ),
    EdgeRow(
        edge_id="key-order",
        description="Object keys must remain in canonical sorted order.",
        covered_labels=("v1/non-sorted-object-keys.json",),
    ),
    EdgeRow(
        edge_id="schema-version",
        description="A bundle-like object declaring the wrong schema_version must be rejected.",
        covered_labels=("v1/schema-version-mismatch.json",),
    ),
    EdgeRow(
        edge_id="trailing-whitespace",
        description="Trailing whitespace after a JSON value is not part of the canonical bytes.",
        covered_labels=("v1/trailing-whitespace.json",),
    ),
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_sha256(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8", "surrogatepass")).hexdigest()


def _field(value: dict[str, Any], path: tuple[str, ...]) -> Any:
    cursor: Any = value
    for part in path:
        assert isinstance(cursor, dict)
        cursor = cursor[part]
    return cursor


def load_vector_inventory() -> list[dict[str, Any]]:
    actual_paths = {
        path.relative_to(ROOT).as_posix()
        for path in NEGATIVE_ROOT.rglob("*.json")
    }
    expected_paths = {spec.path.relative_to(ROOT).as_posix() for spec in VECTOR_SPECS}
    assert actual_paths == expected_paths, {
        "expected_paths": sorted(expected_paths),
        "actual_paths": sorted(actual_paths),
    }

    inventory: list[dict[str, Any]] = []
    for spec in VECTOR_SPECS:
        vector = _load_json(spec.path)
        expected_reason_code = vector.get("expected_reason_code")
        if expected_reason_code is None:
            expected_reason_code = (
                _field(vector, ("expected", "reason_code"))
                if "expected" in vector
                else vector["expected_error_code"]
            )
        assert vector["case_id"] == spec.case_id, spec.path
        assert expected_reason_code == spec.expected_reason_code, spec.path
        inventory.append(
            {
                "label": spec.label,
                "path": spec.path.relative_to(ROOT).as_posix(),
                "case_id": vector["case_id"],
                "surface": vector.get("surface", "json"),
                "expected_reason_code": expected_reason_code,
                "source_positive_case": vector["source_positive_case"],
                "sha256": _canonical_sha256(vector),
            }
        )
    return inventory


def render_negative_coverage_matrix() -> str:
    inventory = load_vector_inventory()
    labels = [entry["label"] for entry in inventory]
    label_set = set(labels)

    lines = [
        "# Canonicalization Negative Coverage Matrix",
        "",
        "This matrix is additive and frozen.",
        "Y means the landed vector covers the edge case; - means it does not.",
        "",
        "## Edge coverage",
        "",
    ]

    header = ["Edge case", "Description", *labels]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
    for row in EDGE_ROWS:
        covered = set(row.covered_labels)
        assert covered <= label_set, row.edge_id
        cells = ["Y" if label in covered else "-" for label in labels]
        lines.append(
            "| "
            + " | ".join([row.edge_id, row.description, *cells])
            + " |"
        )

    uncovered_labels = [
        label for label in labels if not any(label in row.covered_labels for row in EDGE_ROWS)
    ]
    assert not uncovered_labels, uncovered_labels

    lines.extend(
        [
            "",
            "## Vector inventory",
            "",
            "| Path | Case ID | Surface | Expected reason code | Source positive case | Canonical fixture SHA-256 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for entry in inventory:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{entry['path']}`",
                    f"`{entry['case_id']}`",
                    f"`{entry['surface']}`",
                    f"`{entry['expected_reason_code']}`",
                    f"`{entry['source_positive_case']}`",
                    f"`{entry['sha256']}`",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- The matrix rows are the #173 edge classes audited against the landed negative vectors.",
            "- The inventory hashes are canonical-JSON SHA-256 values pinned by `sdk/python/tests/conformance/FIXTURE_HASHES.lock`.",
            "- No edge class is intentionally left uncovered; if a future audit finds one, add a new negative vector and update the matrix in the same change.",
        ]
    )
    return "\n".join(lines) + "\n"


def assert_negative_coverage_matrix_matches_disk() -> None:
    expected = render_negative_coverage_matrix()
    actual = MATRIX_PATH.read_text(encoding="utf-8")
    assert actual == expected, MATRIX_PATH
