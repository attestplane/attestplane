#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Extract TypeScript root exports with a conservative text parser."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INDEX = REPO_ROOT / "sdk/typescript/src/index.ts"
BASELINE_RELEASE = "v0.0.2-alpha"
DOCUMENTED_SYMBOLS = {
    "AttestSubstrate",
    "ProofBundleBuilder",
    "makeEventDraft",
    "makeSubjectRef",
    "verifyProofBundle",
}

EXPORT_BLOCK_RE = re.compile(
    r"export\s*\{(?P<body>.*?)\}\s*from\s*['\"](?P<source>[^'\"]+)['\"];", re.DOTALL
)


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//.*", "", text)


def _parse_export_item(raw: str) -> tuple[str, str] | None:
    item = raw.strip()
    if not item:
        return None
    item = item.rstrip(",").strip()
    is_type = item.startswith("type ")
    if is_type:
        item = item.removeprefix("type ").strip()
    if " as " in item:
        _, exported = [part.strip() for part in item.split(" as ", 1)]
    else:
        exported = item
    if not exported or not re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", exported):
        return None
    return exported, "type" if is_type else "value"


def extract_exports(index_path: Path) -> list[dict[str, str]]:
    text = index_path.read_text(encoding="utf-8")
    exports: dict[str, dict[str, str]] = {}
    for match in EXPORT_BLOCK_RE.finditer(text):
        source = match.group("source")
        body = _strip_comments(match.group("body"))
        for raw in body.split(","):
            parsed = _parse_export_item(raw)
            if parsed is None:
                continue
            name, export_kind = parsed
            exports[name] = {"name": name, "source": source, "export_kind": export_kind}
    return [exports[name] for name in sorted(exports)]


def classify_export(name: str, export_kind: str) -> str:
    if export_kind == "type":
        return "type"
    if name.isupper():
        return "constant"
    if name and name[0].isupper():
        return "class"
    return "function"


def stability_for_symbol(name: str) -> str:
    if name in {"verifyChainFull", "verifyChainWithSignatures"}:
        return "experimental"
    return "alpha_public"


def build_manifest(index_path: Path) -> dict[str, Any]:
    exports = [
        {
            "name": item["name"],
            "kind": classify_export(item["name"], item["export_kind"]),
            "source": f"src/{item['source'].removeprefix('./').removesuffix('.js')}.ts",
            "stability": stability_for_symbol(item["name"]),
            "documented": item["name"] in DOCUMENTED_SYMBOLS,
            "notes": "",
        }
        for item in extract_exports(index_path)
    ]
    return {
        "schema_version": "public_api_manifest.v1",
        "language": "typescript",
        "package": "@attestplane/attestplane",
        "baseline_release": BASELINE_RELEASE,
        "exports": exports,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_INDEX)
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
