#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Validate storage compatibility manifests and fixtures."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "storage_compatibility_manifest.v1"
REQUIRED_NO_GO = {
    "production storage",
    "ACID",
    "database-grade durability",
    "multi-writer correctness",
    "automatic destructive repair",
}
ALLOWED_FIXTURE_SUFFIXES = {".jsonl", ".json"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def implementation_issue_codes(source_path: Path) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    codes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "kind" and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                codes.add(node.value.value)
    return codes


def validate_manifest(manifest: dict[str, Any], path: Path, repo_root: Path) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{path}: schema_version must be {SCHEMA_VERSION!r}")
    if not manifest.get("baseline_release"):
        errors.append(f"{path}: baseline_release is required")

    backends = manifest.get("storage_backends")
    if not isinstance(backends, list) or not backends:
        errors.append(f"{path}: storage_backends must be a non-empty array")
        backends = []
    for backend in backends:
        if not isinstance(backend, dict):
            errors.append(f"{path}: backend entries must be objects")
            continue
        for field in ("name", "status", "record_format", "compatibility_policy"):
            if not isinstance(backend.get(field), str) or not backend[field]:
                errors.append(f"{path}: backend {backend.get('name')!r} missing {field}")
        if backend.get("name") == "jsonl" and backend.get("multi_writer_safe") is True:
            errors.append(f"{path}: jsonl backend must not claim multi_writer_safe=true")
        if backend.get("destructive_repair") not in {"not_implemented", "explicit_operator_only"}:
            errors.append(f"{path}: backend {backend.get('name')!r} has unsafe destructive_repair")

    no_go = set(manifest.get("no_go_claims", []))
    missing_no_go = sorted(REQUIRED_NO_GO - no_go)
    if missing_no_go:
        errors.append(f"{path}: missing no_go_claims: {', '.join(missing_no_go)}")

    migration = manifest.get("migration_policy")
    if not isinstance(migration, dict):
        errors.append(f"{path}: migration_policy must be an object")
        migration = {}
    if migration.get("unknown_record_version") != "fail_closed":
        errors.append(f"{path}: unknown_record_version policy must be fail_closed")
    if migration.get("default") != "no_destructive_migration":
        errors.append(f"{path}: default migration policy must be no_destructive_migration")
    if migration.get("destructive_repair") == "enabled_by_default":
        errors.append(f"{path}: destructive repair must not be enabled by default")

    formats = manifest.get("formats")
    if not isinstance(formats, list) or not formats:
        errors.append(f"{path}: formats must be a non-empty array")
        formats = []
    issue_format = next((item for item in formats if isinstance(item, dict) and item.get("name") == "storage_scan_issue.v1"), None)
    if not isinstance(issue_format, dict):
        errors.append(f"{path}: storage_scan_issue.v1 format is required")
        known_codes: set[str] = set()
    else:
        known_codes = set(issue_format.get("known_codes", []))
        required_fields = set(issue_format.get("required_fields", []))
        if required_fields != {"kind", "line_no", "byte_offset", "detail"}:
            errors.append(f"{path}: storage_scan_issue.v1 required_fields must match implementation")
    implementation_codes = implementation_issue_codes(repo_root / "sdk/python/src/attestplane/storage/jsonl.py")
    if known_codes != implementation_codes:
        errors.append(
            f"{path}: known issue codes {sorted(known_codes)} do not match implementation {sorted(implementation_codes)}"
        )

    fixtures = manifest.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        errors.append(f"{path}: fixtures must be a non-empty array")
        fixtures = []
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            errors.append(f"{path}: fixture entries must be objects")
            continue
        fixture_path_raw = fixture.get("path")
        if not isinstance(fixture_path_raw, str) or not fixture_path_raw:
            errors.append(f"{path}: fixture entry missing path")
            continue
        fixture_path = repo_root / fixture_path_raw
        if fixture_path.suffix not in ALLOWED_FIXTURE_SUFFIXES:
            errors.append(f"{path}: fixture {fixture_path_raw} has unsupported suffix")
        if not fixture_path.is_file():
            errors.append(f"{path}: fixture {fixture_path_raw} is missing")
        if not isinstance(fixture.get("negative"), bool):
            errors.append(f"{path}: fixture {fixture_path_raw} missing boolean negative")
        expected = fixture.get("expected_issue_code")
        if fixture.get("negative") is True and expected not in known_codes:
            errors.append(f"{path}: negative fixture {fixture_path_raw} has unknown expected_issue_code {expected!r}")
        if fixture.get("negative") is False and expected is not None:
            errors.append(f"{path}: positive fixture {fixture_path_raw} must not set expected_issue_code")

    expected = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if path.read_text(encoding="utf-8") != expected:
        errors.append(f"{path}: JSON is not deterministic; sort keys with two-space indentation")
    return errors


def run(args: argparse.Namespace) -> int:
    errors = validate_manifest(load_json(args.manifest), args.manifest, args.repo_root)
    if errors:
        print("Storage compatibility check FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Storage compatibility check PASS: {args.manifest}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
