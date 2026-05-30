<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Architecture Gap Audit: v1.8.2

## Context

- **Anchor:** v1.5.0
- **Milestone:** v1.8.2
- **Head SHA:** `7b9bdb7f374e4d05d21cdf28cf5b7199d6e7f02a`
- **Plan level:** Daily (diff-level consultation)
- **Stable releases since anchor:** 26
- **Real commits since anchor:** 107
- **Release-prep commits since anchor:** 31

## What v1.8.2 Shipped

| Issue | Title | Area |
|---|---|---|
| Fix #174 | Add `verify --explain` CLI flag with human-readable rejection rationale aligned with reason codes | CLI / verifier |
| Fix #268 | Pin cross-surface `taxonomy_version` parity + stability vector | Conformance / verifier |
| Fix #238 | Bind landed negative canonicalization vectors to stable reason codes | Conformance / verifier |

## Diff-Level Analysis (v1.5.0 → v1.8.2)

602 files changed, 34,438 insertions, 298 deletions.

### Product changes landed

1. **CLI verify surface:** `verify --explain` prints human-readable rejection rationale; `verify --json` surfaces stable taxonomy_version; `verify-result-v1.json` schema published under `schemas/cli/`.
2. **Taxonomy version stability:** `BundleVerificationResult.taxonomy_version` exposed on both Python and TypeScript SDKs; cross-surface parity vector in conformance; CLI `--require-taxonomy-version` flag.
3. **Reason-code taxonomy (10 codes):** `att.verify.*` codes fully plumbed through verifier, CLI explain output, JSON contract, and cross-language conformance vectors.
4. **Negative canonicalization vectors:** 6 negative fixture files bound to stable reason codes; verifier conformance tests exercising the rejection path.
5. **Schema version validation:** `schema_version` forward-compatible additive-optional rules in `_verify_metadata_closure()`; conformance gate for unknown-required-field rejection (Fix #209).

### Infrastructure changes landed

1. **Local codex runner:** Complete issue flow pipeline with state store, advance queue, human-in-loop review guard, CI watch.
2. **Autodev pipeline:** Temporal worker with SQLite persistence, implement/review/merge/automerge activities, auto-loop dispatch, fix_ci_activity.
3. **Testing framework:** CI testing framework doc, release gate tests, stable/RC auto-train tests.
4. **Observability:** Events module for release-train observability.

## Identified Gaps

### Gap 1: TypeScript SDK has no CLI layer

The Python SDK ships a full CLI (`verify`, `verify-proofbundle`, `inspect`, `export`, `doctor`) with `--json`, `--explain`, `--strict-schema`, `--require-taxonomy-version` flags. The TypeScript SDK remains library-only. Users consuming Attestplane from npm cannot use the CLI verify workflow without installing the Python package.

**Impact:** Cross-SDK parity gap; restricts TS SDK to programmatic-only usage.

### Gap 2: Schema version forward-compatible additive-optional acceptance not gated in CI

While Fix #209 implemented `schema_version` forward-compatible additive rules in `_verify_metadata_closure()`, the positive forward-compatible vector (unknown additive-optional fields pass without error) is not yet pinned as a CI conformance gate. The negative vector (unknown required fields reject) is tested.

**Impact:** Risk of regressing the additive-optional acceptance path during future changes.

### Gap 3: Conformance vector CI lock not automated

The conformance vector registry has manual fixture-lock maintenance. The `scripts/conformance/verify_fixture_lock.py` script exists but is not wired into CI blocking gates. Golden bundles can drift without notice.

**Impact:** Silent conformance regression possible between releases.

### Gap 4: v1.8.x user-visible delta documentation incomplete

The `docs/release-notes/v1.7.x-delta.md` exists but the v1.8.2-specific user-visible changes (`--explain`, taxonomy version stability, reason-code taxonomy finalization) are not yet documented in a consolidated v1.8.x delta document.

**Impact:** Users upgrading from v1.7.x cannot easily discover what changed.
