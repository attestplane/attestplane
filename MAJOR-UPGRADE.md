# Attestplane Major Upgrade Track

This document defines the lightweight `major-track` used for v1.0 and later
breaking-version work. It is intentionally separate from the stable
`autodev-train`: normal suffix-free patch and minor releases continue through
the existing short path unless a major-track trigger is explicit.

## Current Major Track

- Branch: `next/v1.0`
- Target milestone: `v1.0.0-prep`
- GitHub label: `track:major`
- Release-gate track on merge to `main`: `audit`
- Stable registry channel: forbidden from `next/*`; only `main` plus
  `release-cd` may publish suffix-free stable packages.

## Entry Triggers

Use the major track only when at least one item below is true:

- Public Python or TypeScript API shape changes in a breaking way.
- Wire-format, schema, canonicalization, or hash-chain behavior changes
  incompatibly.
- Storage migration requires data movement or is not backward compatible.
- Attestation, signing, key, authentication, or trust-boundary semantics change.
- Cross-SDK or cross-component contracts change.
- GA, CA, or v1.0 readiness criteria change.
- A maintainer explicitly applies `track:major`.

Do not use the major track for ordinary bug fixes, behavior-equivalent
refactors, performance work, additive optional features, or feature flags that
are disabled by default.

## Required Plan

Every major-track branch needs one Opus plan before implementation begins. The
plan must cover:

- The public API and wire-format surfaces affected.
- Migration path and deprecation table.
- Compatibility risks and fail-closed behavior.
- Security and compliance boundary impact.
- Validation evidence required before merge.

The plan is a review artifact, not executable instructions. Codex/autodev may
work through the plan, but cannot self-approve the final audit state.

## v1.0 Surface Freeze

The initial v1.0 surface snapshot is stored in:

- `api/public/v1.0/python_surface_freeze.json`
- `api/public/v1.0/typescript_surface_freeze.json`

These files are advisory evidence for the `next/v1.0` branch. They do not
replace the existing public API drift gate on `main`, and they do not change
the stable train.

## Merge Rules

- Major-track work stays on `next/<version>` until review.
- Merging a major-track branch into `main` must go through release-gate audit
  track.
- A merge must include the Opus plan link, migration guide, validation
  evidence, and an explicit maintainer approval.
- `next/*` must not publish `latest`, `ca`, or any suffix-free stable package.
- Existing released tags must not be retagged or republished.

## Rollback

If the major-track work is abandoned, delete or archive the `next/<version>`
branch. The stable train on `main` remains the source of truth for published
packages.
