<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Documentation Consistency Sweep — 2026-05-19

## Scope

This sweep updates reader-facing documentation after the v0.0.3-alpha release
surface, FreeTSA recovery, and issue-status changes.

Historical validation reports remain point-in-time evidence and were not
rewritten to describe newer facts. Current reader-facing docs were aligned to
the latest public alpha state.

## Baseline

- Branch: `main`
- HEAD before sweep: `b6a0f0a59a24c83b4e5ab16200616ce13b4b84b9`
- `origin/main` before sweep:
  `b6a0f0a59a24c83b4e5ab16200616ce13b4b84b9`

## Updated Docs

- `README.md`
  - PyPI badge now points at `attestplane==0.0.3a0`.
  - Current release posture now states that Python is published to PyPI as
    `0.0.3a0` and TypeScript is published to npm as `0.0.3-alpha` under the
    `alpha` dist-tag.
  - Quickstart now installs the current Python alpha from PyPI.
  - Architecture diagram, roadmap wording, and citation example now align with
    the current public alpha state.
  - Planned surfaces were narrowed to what is still actually unshipped.
- `sdk/python/README.md`
  - Install command now pins `attestplane==0.0.3a0` so pip does not skip the
    pre-release.
- `docs/policy/allowed_claims.md`
  - Added a v0.0.3-alpha section for published artifacts, verifier scope,
    FreeTSA recovery, and issue #7 limitation language.
- `docs/release-notes/v0.0.3-alpha.draft.md`
  - Changed release-candidate wording to published alpha prerelease wording.
  - Added a post-release FreeTSA recovery note without changing the frozen
    release boundary.

## Current Public State

- Python package: `attestplane==0.0.3a0` is available on PyPI as a pre-release.
- TypeScript package: `@attestplane/attestplane@0.0.3-alpha` is available on
  npm under the `alpha` dist-tag.
- GitHub Release: `v0.0.3-alpha` remains a prerelease with 5 assets.
- Default CLI verifier: chain/report-oriented only.
- Issue #11: closed after live `nightly-anchor` recovery.
- Issue #7: remains open as a design question.

## Claim-Safety Boundary

No production-ready, compliance-ready, certification-ready, full ProofBundle
verifier, default signed-verifier, default anchored-verifier, SLSA L3, or
production-grade supply-chain claim was added.

## Explicit Non-Actions

- tag: not performed
- release write: not performed
- publish: not performed
- deploy: not performed
- workflow_dispatch: not performed
- secrets printed: false

## Verdict

`documentation_consistency_ready_for_validation`
