#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Validate release artifact hygiene manifests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "release_artifact_manifest.v1"
FORBIDDEN_PHRASES = (
    "SLSA L3 completed",
    "production-grade supply-chain security",
    "certified provenance",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_bool(value: Any) -> bool:
    return isinstance(value, bool) and value


def phrase_paths(value: Any, phrase: str, path: str = "$") -> list[str]:
    if isinstance(value, str):
        return [path] if phrase in value else []
    if isinstance(value, list):
        found: list[str] = []
        for index, item in enumerate(value):
            found.extend(phrase_paths(item, phrase, f"{path}[{index}]"))
        return found
    if isinstance(value, dict):
        found = []
        for key, item in value.items():
            found.extend(phrase_paths(item, phrase, f"{path}.{key}"))
        return found
    return []


def validate_manifest(manifest: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        errors.append(f"{path}: schema_version must be {MANIFEST_SCHEMA!r}")
    for field in ("release", "tag", "target_commit", "status"):
        if not isinstance(manifest.get(field), str) or not manifest[field]:
            errors.append(f"{path}: missing non-empty {field}")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append(f"{path}: artifacts must be a non-empty array")
        artifacts = []
    checksums = manifest.get("checksums")
    signatures = manifest.get("signatures")
    if not isinstance(checksums, list):
        errors.append(f"{path}: checksums must be an array")
        checksums = []
    if not isinstance(signatures, list):
        errors.append(f"{path}: signatures must be an array")
        signatures = []
    checksum_names = {entry.get("artifact") or entry.get("name") for entry in checksums if isinstance(entry, dict)}
    signature_names = {entry.get("artifact") or entry.get("name") for entry in signatures if isinstance(entry, dict)}

    seen: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            errors.append(f"{path}: artifact entries must be objects")
            continue
        name = artifact.get("name")
        kind = artifact.get("kind")
        if not isinstance(name, str) or not name:
            errors.append(f"{path}: artifact entry missing non-empty name")
            continue
        if name in seen:
            errors.append(f"{path}: duplicate artifact name {name!r}")
        seen.add(name)
        if not isinstance(kind, str) or not kind:
            errors.append(f"{path}: {name}: missing non-empty kind")
        for field in ("required", "published", "checksum_required", "signature_required"):
            if not isinstance(artifact.get(field), bool):
                errors.append(f"{path}: {name}: {field} must be boolean")
        if as_bool(artifact.get("published")) and as_bool(artifact.get("checksum_required")):
            remote_generated = kind == "github_source_archive" and artifact.get("checksum_status") == "remote_generated"
            if name not in checksum_names and not remote_generated:
                errors.append(f"{path}: {name}: published artifact requiring checksum has no checksum entry")
        if as_bool(artifact.get("signature_required")) and name not in signature_names:
            errors.append(f"{path}: {name}: signature_required=true but no signature entry exists")
        if as_bool(artifact.get("signature_required")) and not as_bool(artifact.get("published")):
            errors.append(f"{path}: {name}: unpublished artifact cannot require a signature")

    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        errors.append(f"{path}: provenance must be an object")
        provenance = {}
    if provenance.get("slsa_level_claimed") is not None:
        errors.append(f"{path}: slsa_level_claimed must be null for alpha-safe manifests")
    no_go_claims = manifest.get("no_go_claims")
    if not isinstance(no_go_claims, list):
        errors.append(f"{path}: no_go_claims must be an array")
        no_go_claims = []
    for phrase in FORBIDDEN_PHRASES:
        if phrase not in no_go_claims:
            errors.append(f"{path}: no_go_claims must include {phrase!r}")
    for phrase in FORBIDDEN_PHRASES:
        bad_paths = [
            found_path
            for found_path in phrase_paths(manifest, phrase)
            if not found_path.startswith("$.no_go_claims")
        ]
        if bad_paths:
            errors.append(
                f"{path}: forbidden phrase appears outside no_go_claims: {phrase!r} at {', '.join(bad_paths)}"
            )
    expected = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if path.read_text(encoding="utf-8") != expected:
        errors.append(f"{path}: JSON is not deterministic; sort keys and use two-space indentation")
    return errors


def run(args: argparse.Namespace) -> int:
    all_errors: list[str] = []
    for manifest_path in args.manifests:
        all_errors.extend(validate_manifest(load_json(manifest_path), manifest_path))
    if all_errors:
        print("Release artifact manifest check FAILED", file=sys.stderr)
        for error in all_errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Release artifact manifest check PASS: {len(args.manifests)} manifest(s)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", type=Path, nargs="+")
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
