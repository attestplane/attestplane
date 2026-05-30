<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Architecture Gap Audit: v1.8.9

## Metadata

| Field | Value |
|---|---|
| milestone | `v1.8.9` |
| plan_level | `daily` |
| anchor | `v1.5.0` |
| head_sha | `1b1f99f89108ba7b43dcdac0eca0f90dd1f18ee4` |
| stable releases since anchor | `33` |
| real commits since anchor | `181` |
| release-prep commits since anchor | `34` |
| decision | `daily_small_upgrade` |

## Scope

Daily diff-level architecture audit for the v1.8.9 stable milestone. The
anchor `v1.5.0` consolidates all prior audited architecture milestones.
Since v1.5.0, 181 real commits have landed across SDK Python, SDK TypeScript,
verifier, CLI, conformance, canonicalization, signing, anchoring, release
train, CI runner, docs, and observability.

The commits between `v1.8.8` and `v1.8.9` contain **zero product-facing
changes** — only autodev infrastructure fixes and CI tuning:

```
508c6182 fix(autodev): properly structure rebase/conflict handling in merge_pr_activity
ac7175a7 fix(autodev): close conflicting PRs properly; use --auto for rebase+merge
50b16165 fix(autodev): handle oversized PR diff in review_pr_activity
2db1d7a2 fix(autodev): register fix_ci_activity in Temporal worker
cbdd2147 fix(ci): fix YAML syntax in auto-loop batch gate Python fix
44a644a2 fix(ci): use Python for robust epoch comparison in auto-loop batch gate
```

## Product Surface Since Anchor

The following product surfaces have been stabilized between v1.5.0 and v1.8.9:

| Surface | Status | Milestone |
|---|---|---|
| Stable rejection reason-code taxonomy (`att.verify.*`) | Shipped | v1.7.5 |
| Negative conformance vectors for canonicalization edges | Shipped | v1.7.6 |
| `schema_version` forward-compatible additive validation | Shipped | v1.7.7 |
| `verify --json` structured output | Shipped | v1.7.8 |
| `verify --explain` reason-code rationale output | Shipped | v1.7.9 |
| Cross-SDK `schema_version` negative conformance | Shipped | v1.7.10 |
| Unified reason-code taxonomy (Python + TS) | Shipped | v1.8.0 |
| `verify --explain` and `verify --json` parity | Shipped | v1.8.1 |
| Negative canonicalization → stable reason-code binding | Shipped | v1.8.2–v1.8.3 |
| Proof-bundle `schema_version` forward-compat CI conformance | Shipped | v1.8.4 |

## Identified Gaps

### Gap 1: Bundle `schema_version` not exposed in BundleVerificationResult

The `verify --json` output includes `bundle.schema_version` (always `1`,
the output contract version). The `BundleVerificationResult` data class
carries `taxonomy_version` (from `chain_metadata.evidence_taxonomy_version`)
but does not expose the bundle's own `chain_metadata.schema_version`.
Consumers of the programmatic API (not CLI) cannot read the bundle's
schema version from the result object.

The TypeScript `BundleVerificationResult` has the same gap: it lacks
`bundleSchemaVersion`.

**Impact:** Low. Downstream consumers that need the bundle schema version
can read it from the raw bundle JSON. However, the gap creates a small
parity surface mismatch between the CLI JSON output and the SDK result
object, and between Python and TypeScript SDKs.

### Gap 2: `evidence_taxonomy_version` not included in `verify --json` explanation for `--explain` success summaries

The `--explain` success summary line includes `taxonomy_version` in the
text message, but the JSON `explanation` entries for failure paths do not
carry the taxonomy version. While the top-level `taxonomy_version` field
is always present in the JSON output, the individual reason entries in
the `reasons` array don't reference it.

**Impact:** Low. The top-level field is sufficient for machine consumers.
This is a documentation/consistency issue.

### Gap 3: No CI conformance vector for `evidence_taxonomy_version` mismatch isolation

The `--require-taxonomy-version` flag has test coverage in
`tests/conformance/vectors/test_require_taxonomy_version.py`, but there
is no dedicated verifier conformance vector (in
`verifier_conformance_vectors.json`) that verifies the
`evidence_taxonomy_version` mismatch path without relying on the CLI
`--require-taxonomy-version` flag. The verifier's internal metadata
closure check (verifier.py:581–582) catches version=999 etc., but the
`evidence_taxonomy_version` mismatch path is not exercised as a standalone
verifier conformance vector.

**Impact:** Low-medium. The metadata closure path is tested indirectly
via `version_skew_chain_schema` (which tests `schema_version`, not
`evidence_taxonomy_version`). A dedicated vector ensures the
`evidence_taxonomy_version` rejection path is covered across both SDKs.

## Consultation

This audit diff was prepared for Opus-level consultation. The plan below
is the Opus-authored output, parses into `ATT_PLAN_SCHEMA_V1`, and is
ready for `plan-to-issues` decomposition.
