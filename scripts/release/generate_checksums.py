#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Generate deterministic SHA-256 checksum reports for release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "release_checksums.v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checksum_entry(path: Path, base: Path | None) -> dict[str, Any]:
    resolved = path.resolve()
    name = str(resolved.relative_to(base.resolve())) if base else str(path)
    return {
        "name": name,
        "path": str(path),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def build_report(paths: list[Path], base: Path | None) -> dict[str, Any]:
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("checksum inputs must be files: " + ", ".join(missing))
    entries = [
        checksum_entry(path, base) for path in sorted(paths, key=lambda item: str(item))
    ]
    return {
        "checksums": entries,
        "schema_version": SCHEMA_VERSION,
    }


def run(args: argparse.Namespace) -> int:
    report = build_report(args.files, args.base)
    if args.format == "sha256sum":
        lines = [f"{entry['sha256']}  {entry['path']}" for entry in report["checksums"]]
        output = "\n".join(lines) + ("\n" if lines else "")
    else:
        output = json.dumps(report, indent=2, sort_keys=True) + "\n"

    if args.out:
        args.out.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", type=Path, nargs="+", help="Artifact files to hash")
    parser.add_argument(
        "--base", type=Path, help="Base directory for deterministic relative names"
    )
    parser.add_argument("--format", choices=["json", "sha256sum"], default="json")
    parser.add_argument(
        "--out", type=Path, help="Write output to this path instead of stdout"
    )
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
