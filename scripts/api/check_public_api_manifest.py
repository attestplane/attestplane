#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Check current public API extracts against frozen alpha manifests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "public_api_manifest.v1"
ALLOWLIST_SCHEMA = "public_api_allowlist.v1"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("language") == "python":
        return list(manifest.get("symbols", []))
    return list(manifest.get("exports", []))


def name_set(manifest: dict[str, Any]) -> set[str]:
    return {str(item["name"]) for item in entries(manifest)}


def alpha_names(manifest: dict[str, Any]) -> set[str]:
    return {str(item["name"]) for item in entries(manifest) if item.get("stability") == "alpha_public"}


def documented_names(manifest: dict[str, Any]) -> set[str]:
    return {str(item["name"]) for item in entries(manifest) if item.get("documented") is True}


def require_schema(manifest: dict[str, Any], expected: str, path: Path, errors: list[str]) -> None:
    if manifest.get("schema_version") != expected:
        errors.append(f"{path}: expected schema_version {expected!r}, got {manifest.get('schema_version')!r}")


def validate_manifest_shape(manifest: dict[str, Any], path: Path, errors: list[str]) -> None:
    require_schema(manifest, MANIFEST_SCHEMA, path, errors)
    if manifest.get("language") not in {"python", "typescript"}:
        errors.append(f"{path}: language must be python or typescript")
    for item in entries(manifest):
        name = item.get("name")
        if not isinstance(name, str) or not name:
            errors.append(f"{path}: manifest entry missing non-empty name")
        if item.get("stability") not in {"alpha_public", "experimental", "internal_exported"}:
            errors.append(f"{path}: {name}: invalid stability {item.get('stability')!r}")
        if item.get("kind") not in {"function", "class", "constant", "module", "type", "interface"}:
            errors.append(f"{path}: {name}: invalid kind {item.get('kind')!r}")
        if "documented" not in item:
            errors.append(f"{path}: {name}: missing documented flag")


def validate_allowlist(allowlist: dict[str, Any], path: Path, errors: list[str]) -> None:
    require_schema(allowlist, ALLOWLIST_SCHEMA, path, errors)
    seen: set[str] = set()
    for item in allowlist.get("allowed_asymmetries", []):
        symbol = item.get("symbol")
        if not isinstance(symbol, str) or not symbol:
            errors.append(f"{path}: allowlist entry missing symbol")
            continue
        seen.add(symbol)
        if item.get("classification") not in {"intentional", "roadmap", "language_specific", "deprecated", "experimental"}:
            errors.append(f"{path}: {symbol}: invalid classification {item.get('classification')!r}")
        if not item.get("reason"):
            errors.append(f"{path}: {symbol}: missing reason")
        if not item.get("review_by"):
            errors.append(f"{path}: {symbol}: missing review_by")
    if len(seen) != len(allowlist.get("allowed_asymmetries", [])):
        errors.append(f"{path}: duplicate allowed_asymmetries symbols")
    if not allowlist.get("forbidden_drift"):
        errors.append(f"{path}: forbidden_drift must not be empty")


def check_current_against_baseline(
    *,
    current: dict[str, Any],
    baseline: dict[str, Any],
    label: str,
    errors: list[str],
) -> None:
    current_names = name_set(current)
    baseline_names = name_set(baseline)
    missing_alpha = sorted(alpha_names(baseline) - current_names)
    new_unrecorded = sorted(current_names - baseline_names)
    missing_documented = sorted(documented_names(baseline) - current_names)
    if missing_alpha:
        errors.append(f"{label}: alpha_public symbols missing from current export: {', '.join(missing_alpha)}")
    if new_unrecorded:
        errors.append(f"{label}: current export has unrecorded symbols: {', '.join(new_unrecorded)}")
    if missing_documented:
        errors.append(f"{label}: documented symbols missing from current export: {', '.join(missing_documented)}")


def check_cross_language_allowlist(
    python_baseline: dict[str, Any],
    typescript_baseline: dict[str, Any],
    allowlist: dict[str, Any],
    errors: list[str],
) -> None:
    py_names = name_set(python_baseline)
    ts_names = name_set(typescript_baseline)
    asymmetries = (py_names - ts_names) | (ts_names - py_names)
    allowed = {str(item["symbol"]) for item in allowlist.get("allowed_asymmetries", [])}
    missing = sorted(asymmetries - allowed)
    stale = sorted(allowed - asymmetries)
    if missing:
        errors.append(f"cross-language: asymmetries missing allowlist entries: {', '.join(missing)}")
    if stale:
        errors.append(f"cross-language: stale allowlist entries are no longer asymmetric: {', '.join(stale)}")


def deterministic_check(path: Path, data: dict[str, Any], errors: list[str]) -> None:
    expected = json.dumps(data, indent=2, sort_keys=True) + "\n"
    if path.read_text(encoding="utf-8") != expected:
        errors.append(f"{path}: JSON is not deterministic; run the extractor/checker with sorted output")


def run(args: argparse.Namespace) -> int:
    paths = [
        args.python_current,
        args.typescript_current,
        args.python_baseline,
        args.typescript_baseline,
        args.allowlist,
    ]
    py_current, ts_current, py_baseline, ts_baseline, allowlist = [load_json(path) for path in paths]
    errors: list[str] = []
    for manifest, path in [
        (py_current, args.python_current),
        (ts_current, args.typescript_current),
        (py_baseline, args.python_baseline),
        (ts_baseline, args.typescript_baseline),
    ]:
        validate_manifest_shape(manifest, path, errors)
        deterministic_check(path, manifest, errors)
    validate_allowlist(allowlist, args.allowlist, errors)
    deterministic_check(args.allowlist, allowlist, errors)
    check_current_against_baseline(current=py_current, baseline=py_baseline, label="python", errors=errors)
    check_current_against_baseline(current=ts_current, baseline=ts_baseline, label="typescript", errors=errors)
    check_cross_language_allowlist(py_baseline, ts_baseline, allowlist, errors)
    if errors:
        print("Public API manifest check FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(
        "Public API manifest check PASS: "
        f"python={len(name_set(py_baseline))} symbols, "
        f"typescript={len(name_set(ts_baseline))} exports, "
        f"allowlist={len(allowlist.get('allowed_asymmetries', []))} asymmetries"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-current", type=Path, required=True)
    parser.add_argument("--typescript-current", type=Path, required=True)
    parser.add_argument("--python-baseline", type=Path, required=True)
    parser.add_argument("--typescript-baseline", type=Path, required=True)
    parser.add_argument("--allowlist", type=Path, required=True)
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
