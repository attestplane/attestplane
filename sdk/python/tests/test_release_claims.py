# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Release-facing claim safety checks for the public alpha surface."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

PUBLIC_CLAIM_SURFACES = [
    "README.md",
    "CHANGELOG.md",
    "docs/release-notes/v0.0.2-alpha.draft.md",
    "docs/policy/allowed_claims.md",
    "sdk/python/README.md",
    "sdk/typescript/README.md",
]

FORBIDDEN_POSITIVE_PHRASES = [
    "production-ready",
    "production ready",
    "compliance-ready",
    "compliance ready",
    "production-grade",
    "eu ai act compliant",
    "dora compliant",
    "gdpr compliant",
    "fully compliant",
    "full verifier",
    "full proofbundle verifier",
    "full proof-bundle verification",
    "complete verifier",
    "verifies signatures",
    "verifies anchors",
    "runtime governance",
    "end-to-end compliance",
    "production governance",
    "slsa l3",
    "certified",
]

ALLOWED_CONTEXT_MARKERS = [
    "not ",
    "does not ",
    "do not ",
    "must not ",
    "forbidden",
    "no-go",
    "planned",
    "roadmap",
    "no external certification claimed",
    "compliance certification",
    "not production-ready",
    "not compliance-ready",
    "must not be described as",
]


def _is_allowed_context(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in ALLOWED_CONTEXT_MARKERS)


def test_public_release_surfaces_do_not_make_positive_p0_overclaims() -> None:
    violations: list[str] = []
    for rel_path in PUBLIC_CLAIM_SURFACES:
        path = REPO_ROOT / rel_path
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            lowered = line.lower()
            for phrase in FORBIDDEN_POSITIVE_PHRASES:
                if phrase in lowered and not _is_allowed_context(line):
                    violations.append(f"{rel_path}:{lineno}: {phrase!r}: {line.strip()}")

    assert not violations, "positive P0 overclaims found:\n" + "\n".join(violations)


def test_readme_and_release_notes_declare_verify_scope() -> None:
    for rel_path in ["README.md", "docs/release-notes/v0.0.2-alpha.draft.md"]:
        text = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
        assert "chain/report-oriented" in text
        assert "does not perform full ProofBundle" in text
        assert "signature" in text
        assert "anchor" in text
        assert "compliance certification" in text
