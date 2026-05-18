#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Validate the deterministic fault-injection coverage matrix.

This is intentionally lightweight: it does not run a mutation engine. It
checks that every active fail-closed fault has at least one concrete test
reference and that roadmap items carry review metadata.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ALLOWED_STATUSES = {"active", "roadmap", "language_specific"}
TEST_REF_RE = re.compile(
    r"^(?P<path>[^:]+)::(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?:\[(?P<param>[^\]]+)\])?$"
)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise SystemExit(f"{path}: matrix must be a JSON object")
    return obj


def _validate_test_ref(repo_root: Path, ref: str) -> str | None:
    match = TEST_REF_RE.match(ref)
    if match is None:
        return f"test reference {ref!r} must look like path::test_name or path::test_name[param]"
    path = repo_root / match.group("path")
    if not path.exists():
        return f"test reference {ref!r} points to missing file {path}"
    text = path.read_text(encoding="utf-8")
    name = match.group("name")
    if name not in text:
        return f"test reference {ref!r} names {name!r}, but that name is not in {path}"
    param = match.group("param")
    if param is not None and param not in text:
        return f"test reference {ref!r} uses param id {param!r}, but that id is not in {path}"
    return None


def validate_matrix(path: Path, repo_root: Path) -> tuple[int, int, int]:
    matrix = _load_json(path)
    if matrix.get("schema_version") != "fault_matrix.v1":
        raise SystemExit("fault matrix schema_version must be fault_matrix.v1")
    faults = matrix.get("faults")
    if not isinstance(faults, list):
        raise SystemExit("fault matrix must contain a faults array")

    seen: set[str] = set()
    active = 0
    covered = 0
    roadmap = 0
    violations: list[str] = []

    for idx, fault in enumerate(faults):
        if not isinstance(fault, dict):
            violations.append(f"faults[{idx}] must be an object")
            continue
        fault_id = fault.get("id")
        if not isinstance(fault_id, str) or not fault_id:
            violations.append(f"faults[{idx}] has missing id")
            continue
        if fault_id in seen:
            violations.append(f"duplicate fault id {fault_id!r}")
        seen.add(fault_id)

        status = fault.get("status", "active")
        if status not in ALLOWED_STATUSES:
            violations.append(f"{fault_id}: status {status!r} is not allowed")
            continue
        tests = fault.get("tests")
        if status == "active":
            active += 1
            if not isinstance(tests, list) or not tests:
                violations.append(f"{fault_id}: active fault must have tests")
                continue
            fault_covered = True
            for test_ref in tests:
                if not isinstance(test_ref, str) or not test_ref:
                    violations.append(f"{fault_id}: test reference must be a non-empty string")
                    fault_covered = False
                    continue
                error = _validate_test_ref(repo_root, test_ref)
                if error is not None:
                    violations.append(f"{fault_id}: {error}")
                    fault_covered = False
            if fault_covered:
                covered += 1
        else:
            roadmap += 1
            if not isinstance(fault.get("reason"), str) or not fault["reason"]:
                violations.append(f"{fault_id}: {status} fault must include reason")
            if not isinstance(fault.get("review_by"), str) or not fault["review_by"]:
                violations.append(f"{fault_id}: {status} fault must include review_by")

    if violations:
        for violation in violations:
            print(f"FAULT MATRIX ERROR: {violation}", file=sys.stderr)
        raise SystemExit(1)
    print(
        f"Fault matrix check PASS: active={active}, covered={covered}, "
        f"roadmap_or_language_specific={roadmap}"
    )
    return active, covered, roadmap


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--matrix",
        default="tests/fault_injection/fault_matrix_v1.json",
        help="Path to fault matrix JSON",
    )
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    validate_matrix(repo_root / args.matrix, repo_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
