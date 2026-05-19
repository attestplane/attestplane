<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Next Alpha Release Plan — 2026-05-19

## Status

Planning only. No tag, release, publish, deploy, or workflow dispatch was
performed for this plan.

## Context

The `v0.0.3-alpha` tag and release assets are frozen. Subsequent `main` work
includes the FreeTSA SHA-512 ECDSA timestamp verification fix, issue #7 design
closure documents, and documentation consistency updates. Those changes should
not be retroactively inserted into the frozen `v0.0.3-alpha` artifacts.

If these changes should be distributed as release artifacts, cut a new alpha
instead of moving or replacing the old tag.

## Candidate Scope

Recommended next alpha scope:

1. FreeTSA SHA-512 ECDSA timestamp verification recovery.
2. AIA-12 aligned profile document.
3. Verifier independence architecture document.
4. Commit-then-redact retention evidence ADR.
5. Documentation consistency updates for the current public alpha posture.

## Candidate Version

Use a new version after `v0.0.3-alpha`; do not reuse or retag
`v0.0.3-alpha`.

Possible names:

- `v0.0.4-alpha`
- Python package `0.0.4a0`
- npm package `0.0.4-alpha`

The exact version should be selected only when a release gate is run.

## Required Gate Before Tagging

Before creating a new tag:

1. Confirm `main == origin/main`.
2. Run Python tests, TypeScript tests, cross-SDK round-trip, public API gate,
   proof-bundle verifier gate, release-claim gate, and secret scan.
3. Rebuild package artifacts from the candidate tag.
4. Generate a new release artifact manifest and checksums for the new version.
5. Confirm the new release notes preserve alpha and no-go claim boundaries.
6. Confirm npm `latest` is not changed unless separately authorized.

## Explicit Non-Actions

- `v0.0.3-alpha` tag movement: not allowed.
- `v0.0.3-alpha` release asset replacement: not allowed.
- package publish: not part of this plan.
- deploy: not part of this plan.
- workflow dispatch: not part of this plan.

## Recommendation

Do not cut a new alpha only for documentation. Cut a new alpha when the
FreeTSA recovery and issue #7 profile documents are considered useful enough
for downstream users to install as package artifacts.
