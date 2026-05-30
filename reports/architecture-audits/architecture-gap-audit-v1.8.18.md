<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Architecture Gap Audit — v1.8.18

- **Milestone**: `v1.8.18`
- **Anchor**: `v1.5.0`
- **Head**: `3003ef91ff0dd75efb9728a1a10abd9083a419bd`
- **Plan level**: `daily` (small upgrade)
- **Stable releases since anchor**: 42
- **Real commits since anchor**: 205
- **Release-prep commits since anchor**: 34

## 1. Diff Summary (v1.8.17 → v1.8.18)

Only one non-release commit landed between `v1.8.17` and `v1.8.18`:

| SHA | Subject | Affected files |
|-----|---------|----------------|
| `a16dfec2` | chore(versioning): infer CC prefix from issue title; raise batch gate to 10 | `.github/workflows/auto-loop.yml`, `scripts/autodev/temporal/activities.py` |

The change is entirely release-train / CI plumbing — no SDK, verifier, CLI, or product code was modified.

**Verification**: product surface is identical to v1.8.17.

## 2. Current Product-State Overview

### What changed since v1.5.0 anchor (product-visible)

Since the `v1.5.0` anchor, the active product increments have been:

- **Anchoring quarantine path (in-flight)**: Live FreeTSA verification behind an explicit quarantine verdict path. Multiple P0 planned-task issues exist across recent milestones (#415, #423). Python SDK has full `anchoring_quarantined` / `quarantine_reason` / `anchoring_status` fields in `BundleVerificationResult`; TypeScript SDK does not.
- **`taxonomy_version` surfacing (in-flight)**: Plumb stable `taxonomy_version` through `verify --json` and `--explain` output. Multiple P1 planned-task issues exist (#424, #425, etc.).
- **`verify --json` output-contract fixture (in-flight)**: Deterministic exit-code contract for CI gating. Multiple P1 issues exist (#426, etc.).
- **Forward-compatible `schema_version` acceptance (in-flight)**: Positive additive-optional-field acceptance vectors. Multiple P1/P2 issues exist (#427, etc.).

### SDK cross-language parity gaps

| Gap | Python | TypeScript | Impact |
|-----|--------|------------|--------|
| Anchoring quarantine fields in `BundleVerificationResult` | ✅ Full (`anchoring_quarantined`, `quarantine_reason`, `anchoring_status`) | ❌ Missing | TS consumers can't access quarantine state |
| `verifyProofBundle` quarantine logic | ✅ `_result_is_quarantined()`, quarantine chain, `anchoring_status` assignment | ❌ Missing | TS bundles with `anchoring` field are rejected |
| `ALLOWED_TOP_LEVEL` includes `"anchoring"` | ✅ Yes | ❌ No | TS rejects valid bundles with `anchoring` |
| `_FAIL_CLOSED_UNKNOWN_TOP_LEVEL_FIELDS` (proof_type) | ✅ Yes | ❌ No | TS treats `proof_type` as generic unknown field |
| Explicit `schema_version_missing` detection | ✅ Separate check before version support check | ❌ Falls through to "unsupported" | Wrong reason code in TS |
| CLI JSON output builder (`verify_json.py` / `verify_json.ts`) | ✅ Full (836 lines) | ❌ Does not exist | TS CLI consumers lack structured output |

## 3. Blockers / Risks

- **Anchoring P0 (#415)**: Open across multiple milestones. No new anchoring-related product or test code landed in v1.8.18. Risk unchanged.
- **Verifier taxonomy_version P1 (#424, #425)**: No progress in this milestone window. Risk: continuing to defer extends the gap between Python and consumer-facing CLI output contracts.
- **Conformance P1 (#426, #427)**: No new conformance vectors landed in this window. Risk: CI output-contract fixture remains unpinned.

## 4. Recommendation

This is a genuine daily small upgrade with no product changes in the window. The plan should:

1. **Add one P1 product increment**: Close the TypeScript SDK anchoring/quarantine parity gap — the most impactful single piece of product work that can be completed in a daily cycle without destabilizing the existing Python pipeline.
2. **Reference existing open issues** for anchoring P0, taxonomy_version P1, and conformance P1/P2 rather than re-creating them.
3. **P2 docs task** to capture the v1.8.18 delta (batch-gate change only) without touching CHANGELOG.md or release workflows.
