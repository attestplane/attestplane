<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Daily Development Plan for v1.8.18

## Concise Plan

- Keep this daily upgrade diff-level. The only non-release commit since v1.8.17 is the CI batch-gate adjustment — no product code changed.
- Make the product increment real: close the TypeScript SDK anchoring/quarantine parity gap. Python's `BundleVerificationResult` already carries `anchoring_quarantined`, `quarantine_reason`, and `anchoring_status`; the TypeScript `BundleVerificationResult` and `verifyProofBundle` do not. Adding `anchoring` to the TS `ALLOWED_TOP_LEVEL` set and implementing the quarantine path in `verifyProofBundle` brings TS into parity for consumers that use the `anchoring` bundle field.
- Reference the already-open anchoring P0 (#415), verifier taxonomy_version P1 (#424, #425), conformance P1/P2 (#426, #427), and CLI output-contract P1 (#426) issues instead of duplicating them.
- Publish a small docs task that captures the v1.8.18 user-visible delta (batch-gate tooling change only) without modifying `CHANGELOG.md` or any release workflow.

## P0 Issues

No standalone P0 product task is proposed for this daily plan. The active FreeTSA anchoring quarantine P0 remains tracked in the existing open issue set (#415) and is handled as context/support work only in this plan.

## P1 Issues

### ISSUE 1 · [P1][typescript][verifier] Close the TypeScript SDK anchoring/quarantine parity gap

**Owner**: typescript/verifier

**Affected modules**:

- TypeScript SDK verifier (`sdk/typescript/src/verifier.ts`)
- TypeScript SDK types (`sdk/typescript/src/types.ts`)
- TypeScript SDK proof-bundle types (`sdk/typescript/src/proof_bundle.ts`)
- Verification reason codes (`sdk/typescript/src/verify_reason_codes.ts`)

**Acceptance criteria**:

1. `BundleVerificationResult` in TypeScript exposes `anchoring_quarantined: boolean`, `quarantine_reason: VerifyReasonCodeV1 | null`, and `anchoring_status: "verified" | "quarantined" | "absent"` matching the Python dataclass shape.
2. `ALLOWED_TOP_LEVEL` in the TypeScript verifier includes `anchoring` so that valid bundles carrying the `anchoring` top-level field are not rejected.
3. `verifyProofBundle` implements the quarantine chain: if the bundle carries an `anchoring` field and the anchoring verification result is `"quarantined"`, the overall verification result reflects `ok = false` with `anchoring_quarantined = true` and a stable `quarantine_reason`.
4. The `_FAIL_CLOSED_UNKNOWN_TOP_LEVEL_FIELDS` set (`proof_type`) is mirrored in TypeScript so that `proof_type` is treated as a fail-closed unknown field.
5. Existing Python conformance vectors for anchoring/quarantine map to passing TypeScript tests.
6. Existing Python verifier behavior (`verify --json` quarantine output) is unchanged — the TS change is additive parity only.

**Validation commands**:

- `cd sdk/typescript && npm test -- --runInBand --testPathPattern='verifier'`
- `cd sdk/typescript && npx tsc --noEmit`
- `PYTHONPATH=sdk/python/src pytest tests/anchoring -q`
- `PYTHONPATH=sdk/python/src pytest sdk/python/tests/cli -k 'anchor or quarantine' -q`
- `git diff --check`

**Rollout / migration notes**:

- The TS `BundleVerificationResult` shape gains three new fields. Existing consumers that destructure the result without the new fields will not break (TypeScript allows optional properties on structural types, but explicit interface consumers may need a recompile). Document the new fields as additive.
- No Python SDK, verifier, CLI, or conformance code is modified. The increment is TypeScript-only.
- Existing Python anchoring quarantine behavior is the reference; TS must match it exactly.
- Do not introduce network dependencies in the TS test suite — use offline fixtures.

### ISSUE 2 · [P1][verifier][cli] Reference existing `taxonomy_version` surfacing and `--require-taxonomy-version` pinning gate tasks

**Owner**: verifier/cli

**Affected modules**:

- Python SDK verifier
- Python CLI JSON serialization
- SDK result object
- Consumer-facing output contract

**Acceptance criteria**:

1. Continue work tracked by existing planned-task issues #424 (consolidate stable `taxonomy_version` across verify output paths) and #425 (`--require-taxonomy-version` consumer pinning gate with negative conformance vector).
2. No new issue is created — this entry exists to confirm the work is still in scope for v1.8.18.
3. Blocking dependencies on conformance vectors (#426, #427) are cleared before closing.

**Validation commands**:

- Per the existing issue acceptance criteria.
- `PYTHONPATH=sdk/python/src pytest tests/verifier -k 'taxonomy_version' -q`
- `git diff --check`

**Rollout / migration notes**:

- Do not rename existing error fields or change existing failure semantics.
- The `--require-taxonomy-version` flag is additive; default behavior is unchanged.

## P2 Issues

### ISSUE 3 · [P2][docs][release] Document the v1.8.18 user-visible delta and record validation evidence

**Owner**: docs/release

**Affected modules**:

- docs
- validation evidence
- runbooks

**Acceptance criteria**:

1. Document the v1.8.18 delta: the batch-gate tooling change (`a16dfec2`) is the only non-release change — no product behavior was altered.
2. Link to the already-open TS anchoring parity P1 task and confirm that the product increment for this milestone is scoped to TypeScript parity only.
3. Record validation evidence that Python SDK, verifier, CLI, and conformance tests pass at the v1.8.18 tag.
4. Keep the wording within the existing claim-safety boundaries and do not touch `CHANGELOG.md`.

**Validation commands**:

- `markdown-link-check docs/**/*.md`
- `PYTHONPATH=sdk/python/src pytest tests/ -q --tb=short 2>&1 | tail -5`
- `git diff --check`

**Rollout / migration notes**:

- This is support work only and must not become a substitute for the product increment.
- Do not modify release tags, publish artifacts, or weaken gates.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{
  "schema": "attestplane.plan.v1",
  "schema_version": 1,
  "plan_level": "daily",
  "milestone_tag": "v1.8.18",
  "anchor_tag": "v1.5.0",
  "head_sha": "3003ef91ff0dd75efb9728a1a10abd9083a419bd",
  "consultation_level": "diff",
  "issues": [
    {
      "ordinal": 1,
      "priority": "P1",
      "title": "[P1][typescript][verifier] Close the TypeScript SDK anchoring/quarantine parity gap",
      "modules": [
        "TypeScript SDK verifier",
        "TypeScript SDK types",
        "TypeScript SDK proof-bundle types",
        "Verification reason codes"
      ],
      "acceptance_criteria": [
        "BundleVerificationResult in TypeScript exposes anchoring_quarantined, quarantine_reason, and anchoring_status matching the Python dataclass shape",
        "ALLOWED_TOP_LEVEL in the TypeScript verifier includes anchoring so that valid bundles carrying the anchoring field are not rejected",
        "verifyProofBundle implements the quarantine chain: anchoring field + quarantined result yields ok=false with stable quarantine_reason",
        "_FAIL_CLOSED_UNKNOWN_TOP_LEVEL_FIELDS (proof_type) is mirrored in TypeScript",
        "Existing Python conformance vectors for anchoring/quarantine map to passing TypeScript tests",
        "Existing Python verifier behavior (verify --json quarantine output) is unchanged"
      ],
      "validation_commands": [
        "cd sdk/typescript && npm test -- --runInBand --testPathPattern='verifier'",
        "cd sdk/typescript && npx tsc --noEmit",
        "PYTHONPATH=sdk/python/src pytest tests/anchoring -q",
        "PYTHONPATH=sdk/python/src pytest sdk/python/tests/cli -k 'anchor or quarantine' -q",
        "git diff --check"
      ],
      "rollout_notes": "TS BundleVerificationResult gains three new additive fields. Existing consumers that destructure the result without the new fields will not break. No Python SDK, verifier, CLI, or conformance code is modified. Document the new fields as additive. No network dependencies in the TS test suite — use offline fixtures."
    },
    {
      "ordinal": 2,
      "priority": "P1",
      "title": "[P1][verifier][cli] Reference existing taxonomy_version surfacing and --require-taxonomy-version pinning gate tasks",
      "modules": [
        "Python SDK verifier",
        "Python CLI JSON serialization",
        "SDK result object",
        "Consumer-facing output contract"
      ],
      "acceptance_criteria": [
        "Continue work tracked by existing planned-task issues #424 and #425",
        "No new issue is created — this entry confirms the work is still in scope for v1.8.18",
        "Blocking dependencies on conformance vectors (#426, #427) are cleared before closing"
      ],
      "validation_commands": [
        "PYTHONPATH=sdk/python/src pytest tests/verifier -k 'taxonomy_version' -q",
        "git diff --check"
      ],
      "rollout_notes": "Do not rename existing error fields or change existing failure semantics. The --require-taxonomy-version flag is additive; default behavior is unchanged."
    },
    {
      "ordinal": 3,
      "priority": "P2",
      "title": "[P2][docs][release] Document the v1.8.18 user-visible delta and record validation evidence",
      "modules": [
        "docs",
        "validation evidence",
        "runbooks"
      ],
      "acceptance_criteria": [
        "Document the v1.8.18 delta: the batch-gate tooling change (a16dfec2) is the only non-release change",
        "Link to the TS anchoring parity P1 task as the product increment for this milestone",
        "Record validation evidence that Python SDK, verifier, CLI, and conformance tests pass at the v1.8.18 tag",
        "Keep the wording within the existing claim-safety boundaries and do not touch CHANGELOG.md"
      ],
      "validation_commands": [
        "markdown-link-check docs/**/*.md",
        "PYTHONPATH=sdk/python/src pytest tests/ -q --tb=short 2>&1 | tail -5",
        "git diff --check"
      ],
      "rollout_notes": "Support work only. Do not modify release tags, publish artifacts, or weaken gates."
    }
  ]
}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
