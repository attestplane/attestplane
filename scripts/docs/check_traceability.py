#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Validate bidirectional links for the compliance traceability matrix."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX = REPO_ROOT / "docs" / "spec" / "compliance-traceability-matrix.md"
SOURCE_DOCS = [
    REPO_ROOT / "docs" / "spec" / "nist-ai-rmf-1.0-mapping.md",
    REPO_ROOT / "docs" / "spec" / "gdpr-articles-5-22-30-mapping.md",
    REPO_ROOT / "docs" / "spec" / "iso-iec-42001-aims-mapping.md",
    REPO_ROOT / "docs" / "security" / "threat-model-v1.md",
]
MATRIX_LINK_TARGETS = {
    REPO_ROOT
    / "docs"
    / "spec"
    / "nist-ai-rmf-1.0-mapping.md": "compliance-traceability-matrix.md",
    REPO_ROOT
    / "docs"
    / "spec"
    / "gdpr-articles-5-22-30-mapping.md": "compliance-traceability-matrix.md",
    REPO_ROOT
    / "docs"
    / "spec"
    / "iso-iec-42001-aims-mapping.md": "compliance-traceability-matrix.md",
    REPO_ROOT
    / "docs"
    / "security"
    / "threat-model-v1.md": "../spec/compliance-traceability-matrix.md",
}
MATRIX_SOURCE_TARGETS = {
    REPO_ROOT
    / "docs"
    / "spec"
    / "nist-ai-rmf-1.0-mapping.md": "./nist-ai-rmf-1.0-mapping.md",
    REPO_ROOT
    / "docs"
    / "spec"
    / "gdpr-articles-5-22-30-mapping.md": "./gdpr-articles-5-22-30-mapping.md",
    REPO_ROOT
    / "docs"
    / "spec"
    / "iso-iec-42001-aims-mapping.md": "./iso-iec-42001-aims-mapping.md",
    REPO_ROOT
    / "docs"
    / "security"
    / "threat-model-v1.md": "../security/threat-model-v1.md",
}
DISCLAIMER = (
    "Alpha — evidence-supporting alignment mapping, NOT compliance certification."
)
SOURCE_ISSUE = "https://github.com/attestplane/attestplane/issues/61"


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def find_link(text: str, target: str) -> bool:
    pattern = re.compile(r"\[[^\]]+\]\(" + re.escape(target) + r"(?:#[^)]+)?\)")
    return bool(pattern.search(text))


def count_gap_rows(text: str) -> int:
    return sum(
        1 for line in text.splitlines() if line.startswith("|") and "gap:" in line
    )


def report(errors: list[str]) -> int:
    for error in errors:
        print(f"::error::{error}")
    return 1


def validate(strict: bool) -> int:
    errors: list[str] = []

    if not MATRIX.exists():
        return report([f"missing matrix file: {MATRIX}"])

    matrix_text = load_text(MATRIX)
    if DISCLAIMER not in matrix_text:
        errors.append("matrix is missing the shared disclaimer")
    if SOURCE_ISSUE not in matrix_text:
        errors.append("matrix is missing the source planning issue link")
    for source_doc in SOURCE_DOCS:
        matrix_target = MATRIX_SOURCE_TARGETS[source_doc]
        if not find_link(matrix_text, matrix_target):
            errors.append(f"matrix is missing link to {matrix_target}")

    gap_rows = count_gap_rows(matrix_text)
    if strict and gap_rows == 0:
        errors.append("matrix does not contain any explicit gap rows")

    for source_doc in SOURCE_DOCS:
        if not source_doc.exists():
            errors.append(f"missing source doc: {source_doc}")
            continue
        text = load_text(source_doc)
        rel = source_doc.relative_to(REPO_ROOT).as_posix()
        matrix_target = MATRIX_LINK_TARGETS[source_doc]
        if DISCLAIMER not in text:
            errors.append(f"{rel} is missing the shared disclaimer")
        if SOURCE_ISSUE not in text:
            errors.append(f"{rel} is missing the source planning issue link")
        if not find_link(text, matrix_target):
            errors.append(f"{rel} is missing a link to {matrix_target}")

    if errors:
        return report(errors)

    print("Traceability matrix links and metadata validated")
    if strict:
        print(f"Explicit gap rows: {gap_rows}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail if the matrix has no explicit gap rows",
    )
    args = parser.parse_args()
    return validate(args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
