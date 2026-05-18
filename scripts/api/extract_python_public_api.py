#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Extract the Python root public API without importing optional dependencies."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INIT = REPO_ROOT / "sdk/python/src/attestplane/__init__.py"
BASELINE_RELEASE = "v0.0.2-alpha"
DOCUMENTED_SYMBOLS = {"AttestSubstrate", "EventDraft", "SubjectRef"}


def _literal_string_list(node: ast.AST) -> list[str]:
    if not isinstance(node, ast.List):
        return []
    values: list[str] = []
    for item in node.elts:
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            values.append(item.value)
    return values


def extract_symbols(init_path: Path) -> list[str]:
    tree = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))
    symbols: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    symbols.extend(_literal_string_list(node.value))
        elif isinstance(node, ast.If):
            for child in node.body:
                if (
                    isinstance(child, ast.Expr)
                    and isinstance(child.value, ast.Call)
                    and isinstance(child.value.func, ast.Attribute)
                    and child.value.func.attr == "extend"
                    and isinstance(child.value.func.value, ast.Name)
                    and child.value.func.value.id == "__all__"
                    and child.value.args
                ):
                    symbols.extend(_literal_string_list(child.value.args[0]))
    return sorted(dict.fromkeys(symbols))


def classify_symbol(name: str) -> str:
    if name == "__version__" or name.isupper():
        return "constant"
    if name and name[0].isupper():
        return "class"
    return "function"


def module_for_symbol(name: str) -> str:
    if name in {"AttestSubstrate", "__version__"}:
        return "attestplane"
    return "attestplane"


def stability_for_symbol(name: str) -> str:
    if name.startswith("_"):
        return "internal_exported"
    if name in {"bundle_to_dsse_envelope", "bundle_to_in_toto_statement", "proof_bundle_to_in_toto_statement"}:
        return "experimental"
    return "alpha_public"


def build_manifest(init_path: Path) -> dict[str, Any]:
    symbols = [
        {
            "name": name,
            "kind": classify_symbol(name),
            "module": module_for_symbol(name),
            "stability": stability_for_symbol(name),
            "documented": name in DOCUMENTED_SYMBOLS,
            "notes": "",
        }
        for name in extract_symbols(init_path)
    ]
    return {
        "schema_version": "public_api_manifest.v1",
        "language": "python",
        "package": "attestplane",
        "baseline_release": BASELINE_RELEASE,
        "symbols": symbols,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_INIT)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    manifest = build_manifest(args.source)
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
