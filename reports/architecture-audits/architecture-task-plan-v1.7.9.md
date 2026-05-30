<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Daily Development Plan for v1.7.9

## Concise Plan

- Keep this daily upgrade diff-level, but make the product increment real: ship structured verify JSON output in the TypeScript SDK, bringing it to parity with the Python `verify --json` surface that landed in v1.7.9.
- Add cross-SDK conformance binding that pins the verify output JSON schema across Python and TypeScript so a drift between the two SDKs cannot ship undetected.
- Wire the automated product-delta idle recovery into the stable train release-gate decision logic so recovered ranges are soft-skipped instead of hard-blocked.
- Complete the release-signing deferral closeout (milestone-owner sign-off per the Issue #229 decision document) and publish a small docs update explaining the v1.7.9 user-visible delta, without changing `CHANGELOG.md` or any release workflow.

## P0 Issues

### ISSUE 1 · \[P0\]\[sdk\]\[typescript\] Implement structured verify JSON output in TypeScript SDK

Owner: sdk/typescript

Affected modules:

- TypeScript SDK verifier
- TypeScript SDK CLI proofbundle entry point
- Verify JSON output schema contract
- TypeScript verifier tests

Acceptance criteria:

1. `sdk/typescript/src/verifier.ts` exports a `verifyProofBundleJson(bundle, options?)` function that returns a structured JSON object matching the Python `verify --json` output schema (`schema_version`, `result`, `exit_code`, `reason_code`, `taxonomy_version`, `reasons[]`, `bundle.digest`).
2. When `explain: true` is passed as an option, the output includes `explanation[]` with `{primary_reason, pointer, message}` entries matching the Python `verify --explain` surface.
3. The JSON output contract matches `schemas/cli/verify-result-v1.json` wherever the schema defines constraints.
4. Exit-code mapping follows the same contract as Python: `0` for verified, `1` for verification failure, `2` for pinning-gate failure, `3` for usage/malformed-input error.
5. TypeScript-specific error paths (e.g. I/O errors, JSON parse errors) map to the same `att.verify.*` reason codes as the Python SDK.
6. Existing `verifyProofBundle()` and `verifyProofBundleFile()` behavior is unchanged. The new function is additive.

Validation commands:

- `cd sdk/typescript && npm test -- --runInBand 2>&1 | tail -20`
- `PYTHONPATH=sdk/python/src python sdk/python/tests/cli/test_verify_json_ts_parity.py -q --tb=short 2>&1 | tail -10`
- `cd sdk/typescript && npx tsc --noEmit 2>&1`
- `git diff --check`

Rollout / migration notes:

- This is the required product increment for the v1.7.9 daily plan.
- The Python `verify --json` output contract (`schema_version=1`, `taxonomy_version=1`) is the canonical reference. The TypeScript implementation must produce byte-identical JSON for the same input.
- Do not refactor or rename existing `BundleVerificationResult` fields. The new function is a serialization layer on top.

## P1 Issues

### ISSUE 2 · \[P1\]\[conformance\]\[test\] Add cross-SDK verify output conformance binding

Owner: conformance/test

Affected modules:

- cross-SDK conformance tests
- conformance test vectors
- verify output JSON schema fixture
- CI conformance workflow

Acceptance criteria:

1. `tests/cross_sdk/verify_conformance/` directory is created with a three-step harness mirroring the existing canonicalization round-trip (py_emit → ts_roundtrip → py_verify), but operating on verify-output JSON shapes instead of canonical bytes.
2. A corpus of test bundles (positive and negative) is placed in `tests/cross_sdk/verify_conformance/corpus/`.
3. The Python step runs `verify --json --explain` on each corpus bundle and records the output JSON golden file.
4. The TypeScript step runs `verifyProofBundleJson()` on the same corpus and asserts structural + value parity with the golden file.
5. The conformance binding is gated in CI via a workflow job that must pass before merge.
6. The existing canonicalization round-trip (`tests/cross_sdk/py_emit.py` etc.) continues to pass unchanged.

Validation commands:

- `PYTHONPATH=sdk/python/src python tests/cross_sdk/verify_conformance/py_emit.py 2>&1`
- `cd sdk/typescript && node tests/cross_sdk/verify_conformance/ts_verify.mjs 2>&1`
- `PYTHONPATH=sdk/python/src python tests/cross_sdk/verify_conformance/py_verify.py 2>&1`
- `git diff --check`

Rollout / migration notes:

- The test corpus should include at least one pass bundle, one schema-version mismatch bundle, one malformed-signature bundle, and one canonicalization-failure bundle.
- Golden files are checked in and must be updated atomically with any intentional verify-output schema change.
- Do not modify the existing cross-SDK canonicalization harness.

### ISSUE 3 · \[P1\]\[release\] Wire product-delta idle recovery into stable train release gate

Owner: release

Affected modules:

- release gate decision logic
- stable train auto-release
- product-delta idle recovery script

Acceptance criteria:

1. When `scripts/release/product_delta_idle_recovery.py` detects a support-only delta and enters the idle-recovery path, the stable train release gate returns a `soft_skip` status instead of a hard `block` status.
2. The release train workflow (`scripts/release/stable_auto_train.py` or equivalent) reads the `soft_skip` status and skips the release creation step without raising an error or blocking the runner.
3. Existing hard-block behaviour for active product-delta failures is preserved.
4. The idle-recovery path is logged at the `info` level so release-train operators can audit skipped releases.

Validation commands:

- `PYTHONPATH=sdk/python/src python scripts/release/product_delta_idle_recovery.py --dry-run 2>&1 | head -10`
- `PYTHONPATH=sdk/python/src python -m pytest tests/release/test_stable_auto_train.py -q --tb=short 2>&1 | tail -10`
- `python scripts/release/release_gate.py --release-tag v1.7.10 --channel latest --json 2>&1 | head -5`
- `git diff --check`

Rollout / migration notes:

- This is a release-train reliability improvement, not a product feature.
- The `soft_skip` status must not appear in the CLI exit-code contract for `verify --json`.
- Do not change the existing product-delta classification logic in `scripts/release/release_gate.py`.

## P2 Issues

### ISSUE 4 · \[P2\]\[docs\]\[release\] Update v1.7.x user-visible delta for TypeScript verify surface expansion

Owner: docs/release

Affected modules:

- docs/release-notes/v1.7.x-delta.md
- docs/cli/verify-json.md
- cross-reference links

Acceptance criteria:

1. `docs/release-notes/v1.7.x-delta.md` records the TypeScript `verifyProofBundleJson()` function as a new user-visible surface, including the supported `explain` option and the exit-code contract.
2. `docs/cli/verify-json.md` notes that TypeScript consumers can use `verifyProofBundleJson()` in addition to the Python `verify --json` CLI.
3. All cross-references are updated to reflect the TypeScript parity.
4. The wording stays within existing claim-safety boundaries and does not imply TypeScript deployment maturity beyond the published prototype scope.
5. No changes to `CHANGELOG.md` or any release workflow.

Validation commands:

- `markdown-link-check docs/release-notes/v1.7.x-delta.md 2>&1`
- `markdown-link-check docs/cli/verify-json.md 2>&1`
- `git diff --check`

Rollout / migration notes:

- This is support work only and must not become a substitute for the product increment.
- Do not modify release tags, publish artifacts, or weaken gates.

### ISSUE 5 · \[P2\]\[security\]\[governance\] Formalize release-signing deferral closeout

Owner: security/governance

Affected modules:

- docs/security/release-signing.md
- release governance records
- milestone boundary documentation

Acceptance criteria:

1. The milestone owner (as referenced in `docs/security/release-signing.md`) formally reviews and signs off on the `v1.7.x` release-signing deferral.
2. The decision document is updated with the closeout approval (date, reviewer, rationale).
3. A concrete re-evaluation milestone is committed (e.g. `v1.8.x` or `v2.0.0`), replacing the relative "M5 W4" target.
4. The closeout is recorded in the release governance records without implying that published packages are now release-signed.

Validation commands:

- `grep -r 'release-signing' docs/security/` (visual inspection)
- `git diff --check`
- Manual review of the updated decision document.

Rollout / migration notes:

- This is governance/support work only. No code changes.
- Do not imply that the deferral has been lifted or that release-signing has shipped.
- The closeout must reference the original Issue #229 and the decision document.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{"anchor_tag":"v1.5.0","consultation_level":"diff","head_sha":"fee6e15d3074f831fcebad73826eb81d5801f080","issues":[{"acceptance_criteria":["`sdk/typescript/src/verifier.ts` exports a `verifyProofBundleJson(bundle, options?)` function that returns a structured JSON object matching the Python `verify --json` output schema.","When `explain: true` is passed, output includes `explanation[]` with `{primary_reason, pointer, message}` entries.","JSON output contract matches `schemas/cli/verify-result-v1.json`.","Exit-code mapping follows the same contract as Python.","TypeScript-specific error paths map to the same `att.verify.*` reason codes.","Existing `verifyProofBundle()` and `verifyProofBundleFile()` unchanged."],"modules":["TypeScript SDK verifier","TypeScript SDK CLI proofbundle entry point","Verify JSON output schema contract","TypeScript verifier tests"],"ordinal":1,"priority":"P0","rollout_notes":"This is the required product increment for the v1.7.9 daily plan. The Python `verify --json` output contract is the canonical reference. Do not refactor or rename existing `BundleVerificationResult` fields.","title":"[P0][sdk][typescript] Implement structured verify JSON output in TypeScript SDK","validation_commands":["cd sdk/typescript && npm test -- --runInBand 2>&1 | tail -20","PYTHONPATH=sdk/python/src python sdk/python/tests/cli/test_verify_json_ts_parity.py -q --tb=short 2>&1 | tail -10","cd sdk/typescript && npx tsc --noEmit 2>&1","git diff --check"]},{"acceptance_criteria":["`tests/cross_sdk/verify_conformance/` directory created with three-step harness.","Corpus of test bundles (positive and negative) placed in `tests/cross_sdk/verify_conformance/corpus/`.","Python step runs `verify --json --explain` and records golden file.","TypeScript step runs `verifyProofBundleJson()` and asserts parity with golden file.","Conformance binding gated in CI.","Existing canonicalization round-trip unchanged."],"modules":["cross-SDK conformance tests","conformance test vectors","verify output JSON schema fixture","CI conformance workflow"],"ordinal":2,"priority":"P1","rollout_notes":"Golden files are checked in and must be updated atomically with intentional verify-output schema changes. Do not modify existing cross-SDK harness.","title":"[P1][conformance][test] Add cross-SDK verify output conformance binding","validation_commands":["PYTHONPATH=sdk/python/src python tests/cross_sdk/verify_conformance/py_emit.py 2>&1","cd sdk/typescript && node tests/cross_sdk/verify_conformance/ts_verify.mjs 2>&1","PYTHONPATH=sdk/python/src python tests/cross_sdk/verify_conformance/py_verify.py 2>&1","git diff --check"]},{"acceptance_criteria":["Idle-recovery path returns `soft_skip` status instead of hard `block`.","Release train workflow reads `soft_skip` and skips release creation without raising error.","Existing hard-block behaviour for active product-delta failures preserved.","Idle-recovery path logged at `info` level."],"modules":["release gate decision logic","stable train auto-release","product-delta idle recovery script"],"ordinal":3,"priority":"P1","rollout_notes":"This is a release-train reliability improvement. `soft_skip` must not appear in the CLI exit-code contract. Do not change product-delta classification logic.","title":"[P1][release] Wire product-delta idle recovery into stable train release gate","validation_commands":["PYTHONPATH=sdk/python/src python scripts/release/product_delta_idle_recovery.py --dry-run 2>&1 | head -10","PYTHONPATH=sdk/python/src python -m pytest tests/release/test_stable_auto_train.py -q --tb=short 2>&1 | tail -10","python scripts/release/release_gate.py --release-tag v1.7.10 --channel latest --json 2>&1 | head -5","git diff --check"]},{"acceptance_criteria":["`docs/release-notes/v1.7.x-delta.md` records TypeScript `verifyProofBundleJson()` surface.","`docs/cli/verify-json.md` notes TypeScript parity.","Cross-references updated.","Wording stays within claim-safety boundaries.","No changes to `CHANGELOG.md` or release workflow."],"modules":["docs/release-notes","docs/cli/verify-json.md","cross-reference links"],"ordinal":4,"priority":"P2","rollout_notes":"Support work only. Do not modify release workflow artifacts.","title":"[P2][docs][release] Update v1.7.x user-visible delta for TypeScript verify surface expansion","validation_commands":["markdown-link-check docs/release-notes/v1.7.x-delta.md 2>&1","markdown-link-check docs/cli/verify-json.md 2>&1","git diff --check"]},{"acceptance_criteria":["Milestone owner formally reviews and signs off on the `v1.7.x` release-signing deferral.","Decision document updated with closeout approval (date, reviewer, rationale).","Concrete re-evaluation milestone committed replacing relative \"M5 W4\" target.","Closeout recorded without implying published packages are now release-signed."],"modules":["docs/security/release-signing.md","release governance records","milestone boundary documentation"],"ordinal":5,"priority":"P2","rollout_notes":"Governance/support work only. No code changes. Reference original Issue #229 and decision document.","title":"[P2][security][governance] Formalize release-signing deferral closeout","validation_commands":["grep -r 'release-signing' docs/security/","git diff --check","Manual review of updated decision document"]}],"milestone_tag":"v1.7.9","plan_level":"daily","schema":"attestplane.plan.v1","schema_version":1}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
