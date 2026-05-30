<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Architecture Gap Audit v1.7.9

Baseline: `v1.5.0`
HEAD: `fee6e15d3074f831fcebad73826eb81d5801f080` (v1.7.9 release-prep)
Consultation level: `diff`
Plan type: `daily_small_upgrade`

## Audit Summary

The v1.7.9 boundary ships the following product surface landed since v1.7.8:

| Issue | Surface | Status |
|-------|---------|--------|
| #227 | `verify --explain` reason-code rationale output (CLI) | Shipped |
| #228 | Negative conformance vector gap closure (#173 ↔ #184/#198) | Shipped |
| #229 | Release-signing foundation — explicit deferral decision | Closed (deferred) |
| #230 | v1.7.x user-visible delta for `--explain` surface | Shipped |
| — | Automated product-delta idle recovery | Shipped |

## Identified Gaps

### G1 · TypeScript SDK lacks `verify` structured JSON output

The Python SDK ships `verify --json` (`cli/verify_json.py`) with a full structured output contract including `schema_version`, `result`, `exit_code`, `taxonomy_version`, `reasons[]`, `explanation[]`, and `bundle.digest`. The TypeScript SDK exposes `verifyProofBundle()` and `verifyProofBundleFile()` that return a `BundleVerificationResult` object but does **not** implement the structured JSON output equivalent (`verifyProofBundleJson` or a serialization layer).

Cross-SDK consumers who need machine-readable verifier results currently have no choice but to shell out to Python or parse raw `BundleVerificationResult` manually. This gaps the `verify --json` API parity commitment documented in `docs/cli/verify-json.md`.

**Affected modules:** `sdk/typescript/src/verifier.ts`, `sdk/typescript/src/cli/` (no CLI directory yet)
**Severity:** Medium (product gap, not a correctness gap)

### G2 · Cross-SDK conformance matrix does not pin verify output schema

The cross-SDK round-trip (`tests/cross_sdk/`) currently pins canonicalization byte-equality between Python and TypeScript. There is no equivalent conformance test that pins the *verify output JSON schema* across SDK boundaries. The structured `reasons[]`, `explanation[]`, and `taxonomy_version` contract is only tested in Python (`tests/verifier/test_verify_reason_codes.py`).

This means a drift between Python and TypeScript verifier output shapes could ship without any cross-SDK conformance gate catching it.

**Affected modules:** `tests/cross_sdk/`, `tests/conformance/`, `sdk/typescript/src/verifier.ts`
**Severity:** Medium

### G3 · Release-signing deferral closeout not formalized

Issue #229 resolved release-signing by publishing an explicit deferral decision (`docs/security/release-signing.md`). The decision document requires a milestone-owner review and approval before closing. The closeout procedure (formal sign-off, concrete target milestone commitment) has not been completed.

**Affected modules:** `docs/security/release-signing.md`, `docs/governance/`
**Severity:** Low (process/Security)

### G4 · Product-delta idle recovery not wired into stable train release gate

Commit `fa11d474` automated product-delta idle recovery (detects when the pending diff range contains only support-only deltas and automatically retries). However, the recovered state is not yet wired into the stable train release gate's decision logic — the release gate still emits a hard block rather than a soft-skip when the idle-recovery path triggers.

**Affected modules:** `scripts/release/`, `release gate`
**Severity:** Low (automation completeness)

## Gap-to-Priority Mapping

| Gap | Recommended Priority | Rationale |
|-----|---------------------|-----------|
| G1 | P1 | Product increment: changes SDK surface (TypeScript structured verify output). Required per daily plan product-increment mandate. |
| G2 | P1 | Cross-SDK conformance: prevents drift between Python and TypeScript verify output. Complements G1. |
| G3 | P2 | Process closeout: no code change, but required for release governance hygiene. |
| G4 | P2 | Automation wiring: improves release train reliability but not a product feature. |
