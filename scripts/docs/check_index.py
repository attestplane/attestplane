#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Lint the curated documentation index.

The docs hub at ``docs/README.md`` is the stable entrypoint for the
user-facing documentation corpus. This check ensures the index continues
to mention every file in the curated manifest below.

Run locally with:

    python scripts/docs/check_index.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = REPO_ROOT / "docs" / "README.md"

MANIFEST = (
    "README.md",
    "GOVERNANCE.md",
    "MAINTAINERS.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "SECURITY_zh.md",
    "CHANGELOG.md",
    "TRADEMARK.md",
    "docs/quickstart.md",
    "docs/non-goals.md",
    "docs/governance/conflict-resolution.md",
    "docs/governance/reviewer-tier.md",
    "docs/security/gpg-key-rotation-playbook.md",
    "docs/security/release-signing.md",
    "docs/security/threat-model-v0.0.5-alpha.md",
    "docs/security/threat-model-v1.md",
    "docs/security/openssf-best-practices.md",
    "docs/security/openssf-silver-roadmap.md",
    "docs/security/openssf-scorecard-publication.md",
    "docs/security/mitre-cna-application.md",
    "docs/security/reproducible-builds-submission.md",
    "docs/adr/README.md",
    "docs/architecture/ATTESTATION_GATES.md",
    "docs/architecture/verifier_independence.md",
    "docs/errors.md",
    "docs/policy/allowed_claims.md",
    "docs/policy/claims_policy.md",
    "docs/policy/forbidden_claims.md",
    "docs/release/verifying-signatures.md",
    "docs/release/ga-ca-cut-criteria.md",
    "docs/release/npm-dist-tag-policy.md",
    "docs/roadmap/USER_ROADMAP.md",
    "docs/spec/aia-12-aligned-profile.md",
    "docs/spec/canonical-json-v1.md",
    "docs/spec/canonical-text-v1.md",
    "docs/spec/compat.md",
    "docs/spec/evidence-event-taxonomy-v1.md",
    "docs/spec/gdpr-articles-5-22-30-mapping.md",
    "docs/spec/iso-iec-42001-aims-mapping.md",
    "docs/spec/nist-ai-rmf-1.0-mapping.md",
    "api/public/README.md",
    "sdk/python/README.md",
    "sdk/typescript/README.md",
    "docs/contributor/api-reference.md",
    "docs/schema/verify-json.md",
    "docs/usage/cli_proofbundle_verifier_alpha.md",
    "storage/compat/README.md",
    "tests/conformance/README.md",
    "tests/cross_sdk/README.md",
    "release/alpha-train/README.md",
    "scripts/local_codex_runner/README.md",
)

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _normalize_target(target: str) -> str | None:
    target = target.strip()
    if not target or target.startswith("#"):
        return None
    if target.startswith(("http://", "https://", "mailto:")):
        return None
    target = target.split("#", 1)[0].split("?", 1)[0]
    resolved = (INDEX_PATH.parent / target).resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT).as_posix())
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise RuntimeError(f"link escapes repo root: {target!r}") from exc


def _extract_index_targets(index_path: Path) -> set[str]:
    if not index_path.is_file():
        raise FileNotFoundError(f"missing docs index: {index_path}")
    targets: set[str] = set()
    for match in LINK_RE.finditer(index_path.read_text(encoding="utf-8")):
        normalized = _normalize_target(match.group(1))
        if normalized is not None:
            targets.add(normalized)
    return targets


def main() -> int:
    linked_targets = _extract_index_targets(INDEX_PATH)
    missing_files: list[str] = []
    missing_links: list[str] = []

    for rel_path in MANIFEST:
        abs_path = REPO_ROOT / rel_path
        if not abs_path.is_file():
            missing_files.append(rel_path)
            continue
        if rel_path not in linked_targets:
            missing_links.append(rel_path)

    if missing_files or missing_links:
        if missing_files:
            print("docs index check failed: manifest paths missing on disk:")
            for rel_path in missing_files:
                print(f"  - {rel_path}")
        if missing_links:
            print("docs index check failed: manifest paths missing from docs/README.md:")
            for rel_path in missing_links:
                print(f"  - {rel_path}")
        return 1

    print(
        f"docs index OK: {len(MANIFEST)} curated docs referenced by {INDEX_PATH.relative_to(REPO_ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
