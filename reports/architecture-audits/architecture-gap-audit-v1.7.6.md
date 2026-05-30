<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Architecture Gap Audit — v1.7.6

**Date**: 2026-05-30  
**Anchor**: v1.5.0  
**Head SHA**: 9532411999b59f40baf05c2348dd6c39a511db6f  
**Stable releases since anchor**: 19  
**Real commits since anchor**: 80  
**Release-prep commits since anchor**: 24  
**Plan level**: daily (diff-level)

## Scope

This audit examines the diff range between v1.5.0 and `95324119` (v1.7.6 release
prep commit) to identify residual gaps in:

- cross-SDK verifier parity (Python SDK vs TypeScript SDK)
- conformance vector coverage and fixture lock integrity
- negative canonicalization edge matrix closure
- release gate / stable train product-delta classification

## Key Changes Since v1.7.4 (last daily plan)

| SHA | Area | Description |
|-----|------|-------------|
| `7dce5fc1` | verifier | Introduce stable rejection reason-code taxonomy for `verify` failures (Fix #172) |
| `c15606b0` | canonical | Add canonicalization property tests |
| `9c29781e` | sdk | Land negative conformance vectors mirroring #150 canonicalization edges (Fix #184) |
| `36541154` | runner | Align queue test with priority ordering |
| `f4dda594` | runner | Add multi-lane local Codex runner configuration |

## Gap Analysis

### G1. TypeScript SDK verifier anchoring gap (CRITICAL)

The TypeScript `validateShape()` does not recognize `"anchoring"` as an allowed
top-level field. A bundle containing an `anchoring` block passes Python
`verify_proof_bundle()` (which validates anchoring shape with
`_validate_shape()`), but fails TypeScript `verifyProofBundle()` because
`ALLOWED_TOP_LEVEL` does not include `"anchoring"`.

Additionally, the TypeScript `BundleVerificationResult` lacks:
- `anchoring_quarantined: boolean`
- `quarantine_reason: VerifyReasonCodeV1 | null`
- `anchoring_status: "verified" | "quarantined" | "absent"`

The TypeScript `verifyProofBundle()` error code chain does not include the
`VERIFY_EXTENSION_FAILED` path (Python maps explicit quarantine to this code).

**Module**: sdk/typescript (verifier.ts, verify_errors.ts)  
**Severity**: P1 — cross-SDK verifier parity blocker

### G2. Canonicalization negative vector edge matrix — newly landed vectors not yet in matrix (NEW)

The #184 PR landed 9 versioned negative vectors under
`tests/conformance/vectors/canonicalization/negative/v1/` and 4 un-versioned
negative raw fixtures. The edge matrix in
`tests/conformance/canonicalization_negative_matrix.py` must be audited to
ensure every landed vector has a corresponding edge row with the correct
`covered_labels` and `expected_reason_code` binding.

**Module**: tests/conformance  
**Severity**: P1 — conformance completeness

### G3. Conformance fixture lock — versioned negative vectors missing from lock (NEW)

The `FIXTURE_HASHES.lock` includes the `v1/` negative vectors, but the
3 gap-closure vectors from the #173/#184 gap resolution
(`nested-array-order`, `deep-nfc-string`, `nested-float-prohibition`) may not
yet be present on disk.

**Module**: tests/conformance  
**Severity**: P1 — fixture integrity

### G4. Python SDK conformance negative classifier — no TypeScript equivalent (EXISTING)

The Python SDK has `attestplane/conformance/negative_vectors.py` with a
`classify_negative_vector()` function and `assert_negative_vector()` assertion
helper. The TypeScript SDK has no equivalent negative vector classifier — TS
tests currently assert rejection manually in test files.

**Module**: sdk/typescript (conformance)  
**Severity**: P1 — cross-SDK test parity

### G5. Release gate product-delta — verifier reason-code files not in product prefix list (NEW)

The reason-code taxonomy files in `sdk/python/src/attestplane/verify_reason_codes.py`
and `sdk/typescript/src/verify_reason_codes.ts` are product implementation, but
the release gate's `PRODUCT_IMPLEMENTATION_PREFIXES` may not yet include
`sdk/typescript/src/` with sufficient granularity to detect TypeScript SDK
changes as product delta.

**Module**: scripts/release  
**Severity**: P2 — observability

## Summary

| Gap | Module | Severity | Status |
|-----|--------|----------|--------|
| G1 — TS verifier anchoring | sdk/typescript/verifier.ts | P1 | Open |
| G2 — Edge matrix coverage | tests/conformance | P1 | Open |
| G3 — Fixture lock completeness | tests/conformance | P1 | Open |
| G4 — TS negative vector classifier | sdk/typescript | P1 | Open |
| G5 — Release gate product prefix | scripts/release | P2 | Open |
