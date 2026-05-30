<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Issue #7 Closure Report — 2026-05-19

## Scope

This report records the formal documentation work for
Issue #7: EU AI Act Article 12 surface, verifier independence, and
retention/deletion proof handling.

It converts the earlier conservative design response into project docs and an
ADR. It does not implement new verifier behavior and does not expand public
claims.

## Baseline

- Branch: `main`
- HEAD before changes: `fb0f0f524fe9bf4de21f35924abf097ae6a3d713`
- `origin/main` before changes:
  `fb0f0f524fe9bf4de21f35924abf097ae6a3d713`

## Deliverables

- `docs/spec/aia-12-aligned-profile.md`
  - Defines a concrete AIA-12 aligned evidence profile.
  - Preserves the boundary: aligned evidence infrastructure, not legal
    compliance conclusion.
- `docs/architecture/verifier_independence.md`
  - Defines independent verification around OSS deterministic verifier,
    versioned schemas, exported bytes, and declared trust roots.
  - Hosted APIs are convenience surfaces, not the trust root.
- `docs/adr/0015-retention-deletion-proof-profile.md`
  - Adopts the commit-then-redact retention evidence profile.
  - Keeps raw personal data out of append-only evidence by default.
  - Records deletion/redaction evidence without rewriting historical chain
    entries.
- `docs/roadmap/next_alpha_release_plan_20260519.md`
  - Plans a future alpha path for the FreeTSA recovery and #7 docs.
  - Explicitly forbids moving or replacing the frozen `v0.0.3-alpha` tag and
    assets.
- `README.md`
  - Links the new AIA-12 aligned profile and verifier independence documents
    from the governance and legal document table.
- `docs/policy/allowed_claims.md`
  - Updates issue #7 status language from open design question to
    resolved-by-docs stance.

## Claim Safety

- EU AI Act compliance claimed: false
- GDPR compliance claimed: false
- legal certification claimed: false
- production readiness claimed: false
- hosted API required for truth: false
- `v0.0.3-alpha` tag moved: false

## Explicit Non-Actions

- tag: not performed
- release write: not performed
- publish: not performed
- deploy: not performed
- workflow_dispatch: not performed
- secrets printed: false

## Verdict

`issue_7_ready_to_close_after_validation`
