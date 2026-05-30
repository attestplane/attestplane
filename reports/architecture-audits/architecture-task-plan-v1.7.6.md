<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Daily Development Plan for v1.7.6

## Concise Plan

- Keep this daily upgrade diff-level, but make the product increment real: close
  the TypeScript verifier `anchoring` parity gap so that bundles with anchoring
  blocks pass `verifyProofBundle()` (matching Python behavior), and expose the
  anchoring quarantine/status fields on the TypeScript `BundleVerificationResult`.
- Audit the canonicalization negative-edge matrix for the newly landed v1
  negative vectors (#184) and add any missing edge rows to close the gap between
  the on-disk corpus and the matrix assertion.
- Add the TypeScript `negative_vectors.ts` classifier (mirroring
  `attestplane/conformance/negative_vectors.py`) so TS tests can declare
  conformance-classified negative vectors instead of ad-hoc manual assertions.
- Add the 3 gap-closure negative vectors (`nested-array-order`, `deep-nfc-string`,
  `nested-float-prohibition`) to the on-disk corpus and fixture hash lock.
- Publish a small docs/update task that explains the v1.7.6 user-visible delta —
  the TypeScript anchoring fix — without changing `CHANGELOG.md` or any release
  workflow.

## P0 Issues

### ISSUE 1 · [P0]\[typescript\]\[verifier\] Close the TypeScript verifier anchoring parity gap

Owner: sdk/typescript

Affected modules:

- TypeScript verifier (`sdk/typescript/src/verifier.ts`)
- TypeScript verify errors (`sdk/typescript/src/verify_errors.ts`)
- TypeScript SDK index (`sdk/typescript/src/index.ts`)
- TypeScript `BundleVerificationResult` interface

Acceptance criteria:

1. `validateShape()` in `sdk/typescript/src/verifier.ts` adds `"anchoring"` to
   the `ALLOWED_TOP_LEVEL` set and validates its shape: must be an object with
   a `method` string and `state` string (either `"verified"` or `"quarantined"`).
2. `BundleVerificationResult` in `sdk/typescript/src/verifier.ts` exposes three
   new fields:
   - `anchoring_quarantined: boolean`
   - `quarantine_reason: VerifyReasonCodeV1 | null`
   - `anchoring_status: "verified" | "quarantined" | "absent"`
3. `verifyProofBundle()` error-code chain includes a `VERIFY_EXTENSION_FAILED`
   branch for explicitly quarantined bundles, matching the Python SDK behavior.
4. The `VerifyAnchoringState` class (matching Python's frozen dataclass) is
   exported from `verifier.ts` and wired into the result.

5. Existing tests continue to pass; new tests cover a quarantined-bundle path
   returning `VERIFY_EXTENSION_FAILED` with `anchoring_quarantined: true`.

Validation commands:

- `cd sdk/typescript && npm run build`
- `cd sdk/typescript && npm test -- --runInBand`
- `PYTHONPATH=sdk/python/src python -m pytest sdk/python/tests/verifier/ -q --tb=short`
- `git diff --check`

Rollout / migration notes:

- This is the required product increment for the v1.7.6 daily plan.
- The anchoring fields are additive — existing TS consumers that destructure
  without the new fields will get `undefined`, which is type-safe with
  optional-chaining.
- Do not remove or rename existing verifier fields.

## P1 Issues

### ISSUE 2 · [P1]\[conformance\] Audit and complete the negative-edge matrix for newly landed v1 vectors

Owner: conformance

Affected modules:

- Canonicalization negative edge matrix (`tests/conformance/canonicalization_negative_matrix.py`)
- Edge row definitions
- Negative vector corpus on disk

Acceptance criteria:

1. Every `v1/` versioned negative vector under
   `tests/conformance/vectors/canonicalization/negative/v1/` has a corresponding
   `EDGE_ROWS` entry in the edge matrix with the correct `covered_labels` set.
2. Every un-versioned raw negative fixture under
   `tests/conformance/vectors/canonicalization/negative/` (bom-trailing-bytes,
   duplicate-json-keys, int64-overflow, nfd-payload-string) has a corresponding
   edge row or an explicit rationale for exclusion.
3. The `test_canonicalization_negative_edge_matrix_covers_every_landed_vector()`
   test passes with the updated matrix.

Validation commands:

- `PYTHONPATH=sdk/python/src pytest tests/conformance/test_canonicalization_negative_coverage.py -q --tb=short`
- `PYTHONPATH=sdk/python/src pytest tests/conformance/test_canonicalization_minimum_bundle_vectors.py -v --tb=short`
- `git diff --check`

Rollout / migration notes:

- Add only missing edge rows; do not remove or rename existing rows.
- Verify that the matrix asserts the same expected reason codes the vectors declare.

### ISSUE 3 · [P1]\[typescript\]\[conformance\] Add TypeScript negative vector classifier matching Python SDK

Owner: sdk/typescript

Affected modules:

- TypeScript SDK conformance (`sdk/typescript/src/conformance/`)
- TypeScript test negative vector assertions (`sdk/typescript/test/`)

Acceptance criteria:

1. `sdk/typescript/src/conformance/negative_vectors.ts` exports:
   - `NegativeVectorResult` interface (mirrors Python's `NegativeVectorResult`)
   - `classifyNegativeVector(raw: string): NegativeVectorResult` function that
     detects duplicate keys (via `JSON.parse` with a reviver), non-NFC strings,
     non-sorted object keys, trailing whitespace, embedded NUL, and invalid
     surrogate pairs
   - `assertNegativeVector(raw: string, expectedReasonCode: string): void`
     assertion helper
2. The existing TS verify-reason-code tests wire through the classifier for
   the negative vectors that were previously asserted manually.
3. The module is exported from the SDK barrel (`sdk/typescript/src/index.ts`).

Validation commands:

- `cd sdk/typescript && npm run build`
- `cd sdk/typescript && npm test -- --runInBand`
- `git diff --check`

Rollout / migration notes:

- The classifier is additive — existing TS negative vector tests are not removed.
- Keep the classification logic structurally similar to the Python SDK.

### ISSUE 4 · [P1]\[conformance\] Add 3 gap-closure negative vectors to on-disk corpus

Owner: conformance

Affected modules:

- Versioned negative vector corpus (`tests/conformance/vectors/canonicalization/negative/v1/`)
- Fixture hash lock (`sdk/python/tests/conformance/FIXTURE_HASHES.lock`)
- Canonicalization negative edge matrix (`tests/conformance/canonicalization_negative_matrix.py`)

Acceptance criteria:

1. Three new `v1/` versioned negative vectors are added:
   - `nested-array-order.json` — array with unsorted inner object keys
   - `deep-nfc-string.json` — NFD string in a deeply nested path
   - `nested-float-prohibition.json` — float value in a nested path
2. Each vector uses `att.verify.canonical_mismatch` reason code.
3. Each vector wraps array content in an object (`{"data":[...]}`) because the
   SDK classifier (`_validate_json_candidate`) assumes `parsed` is a dict.
4. The fixture hash lock is updated to include the new vectors.
5. The edge matrix has new rows for `nested-array-order`, `deep-nfc-string`,
   and `nested-float-prohibition`.
6. The conformance minimum-bundle negative vector test covers the new vectors.

Validation commands:

- `PYTHONPATH=sdk/python/src pytest tests/conformance/test_canonicalization_minimum_bundle_vectors.py -k "nested-array-order or deep-nfc-string or nested-float-prohibition" -v --tb=short`
- `PYTHONPATH=sdk/python/src pytest tests/conformance/test_canonicalization_negative_coverage.py -q --tb=short`
- `bash scripts/check-fixture-hashes.sh`
- `git diff --check`

Rollout / migration notes:

- New vectors are additive — existing vectors are not modified.
- The `nested-array-order` vector wraps the array in an object (see acceptance
  criterion 3) to satisfy the SDK classifier's top-level-dict assumption.

## P2 Issues

### ISSUE 5 · [P2]\[docs\]\[release\] Document the v1.7.6 user-visible delta: TypeScript anchoring fix

Owner: docs/release

Affected modules:

- docs
- validation evidence
- release notes

Acceptance criteria:

1. Document the v1.7.6 user-visible delta: the TypeScript verifier anchoring
   parity fix (anchoring block acceptance, quarantine fields, EXPORT_FAILED
   code path, VerifyAnchoringState export).
2. Record the open blocker context for the live verification claim-safety issue
   without implying published packages are blocked.
3. Keep the wording within the existing claim-safety boundaries and do not touch
   `CHANGELOG.md`.

Validation commands:

- `markdown-link-check docs/**/*.md`
- `git diff --check`

Rollout / migration notes:

- This is support work only and must not become a substitute for the product increment.
- Do not modify release tags, publish artifacts, or weaken gates.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{"anchor_tag":"v1.5.0","consultation_level":"diff","head_sha":"9532411999b59f40baf05c2348dd6c39a511db6f","issues":[{"acceptance_criteria":["`validateShape()` in `sdk/typescript/src/verifier.ts` adds `\"anchoring\"` to the `ALLOWED_TOP_LEVEL` set and validates its shape: must be an object with a `method` string and `state` string (either `\"verified\"` or `\"quarantined\"`).","`BundleVerificationResult` in `sdk/typescript/src/verifier.ts` exposes three new fields: `anchoring_quarantined: boolean`, `quarantine_reason: VerifyReasonCodeV1 | null`, `anchoring_status: \"verified\" | \"quarantined\" | \"absent\"`.","`verifyProofBundle()` error-code chain includes a `VERIFY_EXTENSION_FAILED` branch for explicitly quarantined bundles, matching Python SDK behavior.","The `VerifyAnchoringState` class (matching Python's frozen dataclass) is exported from `verifier.ts` and wired into the result.","Existing tests continue to pass; new tests cover a quarantined-bundle path returning `VERIFY_EXTENSION_FAILED` with `anchoring_quarantined: true`."],"modules":["TypeScript verifier (`sdk/typescript/src/verifier.ts`)","TypeScript verify errors (`sdk/typescript/src/verify_errors.ts`)","TypeScript SDK index (`sdk/typescript/src/index.ts`)","TypeScript `BundleVerificationResult` interface"],"ordinal":1,"priority":"P0","rollout_notes":"This is the required product increment for the v1.7.6 daily plan. The anchoring fields are additive — existing TS consumers that destructure without the new fields will get `undefined`, which is type-safe with optional-chaining. Do not remove or rename existing verifier fields.","title":"[P0][typescript][verifier] Close the TypeScript verifier anchoring parity gap","validation_commands":["cd sdk/typescript && npm run build","cd sdk/typescript && npm test -- --runInBand","PYTHONPATH=sdk/python/src python -m pytest sdk/python/tests/verifier/ -q --tb=short","git diff --check"]},{"acceptance_criteria":["Every `v1/` versioned negative vector under `tests/conformance/vectors/canonicalization/negative/v1/` has a corresponding `EDGE_ROWS` entry in the edge matrix with the correct `covered_labels` set.","Every un-versioned raw negative fixture under `tests/conformance/vectors/canonicalization/negative/` (bom-trailing-bytes, duplicate-json-keys, int64-overflow, nfd-payload-string) has a corresponding edge row or an explicit rationale for exclusion.","The `test_canonicalization_negative_edge_matrix_covers_every_landed_vector()` test passes with the updated matrix."],"modules":["Canonicalization negative edge matrix (`tests/conformance/canonicalization_negative_matrix.py`)","Edge row definitions","Negative vector corpus on disk"],"ordinal":2,"priority":"P1","rollout_notes":"Add only missing edge rows; do not remove or rename existing rows. Verify that the matrix asserts the same expected reason codes the vectors declare.","title":"[P1][conformance] Audit and complete the negative-edge matrix for newly landed v1 vectors","validation_commands":["PYTHONPATH=sdk/python/src pytest tests/conformance/test_canonicalization_negative_coverage.py -q --tb=short","PYTHONPATH=sdk/python/src pytest tests/conformance/test_canonicalization_minimum_bundle_vectors.py -v --tb=short","git diff --check"]},{"acceptance_criteria":["`sdk/typescript/src/conformance/negative_vectors.ts` exports: `NegativeVectorResult` interface, `classifyNegativeVector(raw: string): NegativeVectorResult` function that detects duplicate keys (via `JSON.parse` with a reviver), non-NFC strings, non-sorted object keys, trailing whitespace, embedded NUL, and invalid surrogate pairs, and `assertNegativeVector(raw: string, expectedReasonCode: string): void` assertion helper.","The existing TS verify-reason-code tests wire through the classifier for the negative vectors that were previously asserted manually.","The module is exported from the SDK barrel (`sdk/typescript/src/index.ts`)."],"modules":["TypeScript SDK conformance (`sdk/typescript/src/conformance/`)","TypeScript test negative vector assertions (`sdk/typescript/test/`)"],"ordinal":3,"priority":"P1","rollout_notes":"The classifier is additive — existing TS negative vector tests are not removed. Keep the classification logic structurally similar to the Python SDK.","title":"[P1][typescript][conformance] Add TypeScript negative vector classifier matching Python SDK","validation_commands":["cd sdk/typescript && npm run build","cd sdk/typescript && npm test -- --runInBand","git diff --check"]},{"acceptance_criteria":["Three new `v1/` versioned negative vectors are added: `nested-array-order.json`, `deep-nfc-string.json`, `nested-float-prohibition.json`.","Each vector uses `att.verify.canonical_mismatch` reason code.","Each vector wraps array content in an object (`{\"data\":[...]}`) because the SDK classifier (`_validate_json_candidate`) assumes `parsed` is a dict.","The fixture hash lock is updated to include the new vectors.","The edge matrix has new rows for `nested-array-order`, `deep-nfc-string`, and `nested-float-prohibition`.","The conformance minimum-bundle negative vector test covers the new vectors."],"modules":["Versioned negative vector corpus (`tests/conformance/vectors/canonicalization/negative/v1/`)","Fixture hash lock (`sdk/python/tests/conformance/FIXTURE_HASHES.lock`)","Canonicalization negative edge matrix (`tests/conformance/canonicalization_negative_matrix.py`)"],"ordinal":4,"priority":"P1","rollout_notes":"New vectors are additive — existing vectors are not modified. The `nested-array-order` vector wraps the array in an object to satisfy the SDK classifier's top-level-dict assumption.","title":"[P1][conformance] Add 3 gap-closure negative vectors to on-disk corpus","validation_commands":["PYTHONPATH=sdk/python/src pytest tests/conformance/test_canonicalization_minimum_bundle_vectors.py -k \"nested-array-order or deep-nfc-string or nested-float-prohibition\" -v --tb=short","PYTHONPATH=sdk/python/src pytest tests/conformance/test_canonicalization_negative_coverage.py -q --tb=short","bash scripts/check-fixture-hashes.sh","git diff --check"]},{"acceptance_criteria":["Document the v1.7.6 user-visible delta: the TypeScript verifier anchoring parity fix (anchoring block acceptance, quarantine fields, EXPORT_FAILED code path, VerifyAnchoringState export).","Record the open blocker context for the live verification claim-safety issue without implying published packages are blocked.","Keep the wording within the existing claim-safety boundaries and do not touch `CHANGELOG.md`."],"modules":["docs","validation evidence","release notes"],"ordinal":5,"priority":"P2","rollout_notes":"This is support work only and must not become a substitute for the product increment. Do not modify release tags, publish artifacts, or weaken gates.","title":"[P2][docs][release] Document the v1.7.6 user-visible delta: TypeScript anchoring fix","validation_commands":["markdown-link-check docs/**/*.md","git diff --check"]}],"milestone_tag":"v1.7.6","plan_level":"daily","schema":"attestplane.plan.v1","schema_version":1}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
