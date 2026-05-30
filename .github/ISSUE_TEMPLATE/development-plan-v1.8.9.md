<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Daily Development Plan for v1.8.9

- milestone: `v1.8.9`
- plan_level: `daily`
- anchor: `v1.5.0`
- head_sha: `1b1f99f89108ba7b43dcdac0eca0f90dd1f18ee4`
- stable releases since anchor: `33`
- real commits since anchor: `181`
- release-prep commits since anchor: `34`
- decision: `daily_small_upgrade`

## Concise Plan

Keep this daily upgrade diff-level. The v1.8.8→v1.8.9 range carried zero
product-facing changes (only autodev/CI infrastructure). The product
increment for this plan closes the small `schema_version` parity gap:
add `schema_version` to the Python `BundleVerificationResult` data class
(populated from `chain_metadata.schema_version`), and add a verifier
conformance vector for `evidence_taxonomy_version` rejection so both
SDK verifiers exercise that path. Document the v1.8.9 user-visible delta
without touching CHANGELOG.md or release workflows.

## P1 Issues

### ISSUE 1 · **[P1][sdk][verifier] Add `schema_version` to Python `BundleVerificationResult` for bundle chain-metadata schema parity**

Owner: sdk/verifier

Affected modules:
- Python SDK verifier (`BundleVerificationResult` data class)
- Python SDK CLI verify JSON output (consistency)
- TypeScript SDK verifier (`BundleVerificationResult` interface)

Acceptance criteria:
1. `BundleVerificationResult` gains an `schema_version: int | None` field populated from `chain_metadata.schema_version` during verification.
2. The field is `None` when the bundle has no `chain_metadata.schema_version`, and the parsed integer value when present.
3. Python tests cover both the populated and missing-schema paths.
4. TypeScript `BundleVerificationResult` gains a matching `schemaVersion: number | null` field, populated during `verifyProofBundle`.
5. TypeScript tests cover both paths.
6. Existing behavior (error_code, reason_code, taxonomy_version) is unchanged.

Validation commands:
- `PYTHONPATH=sdk/python/src pytest sdk/python/tests -k 'schema_version' -q --tb=short`
- `PYTHONPATH=sdk/python/src pytest tests/verifier -q --tb=short`
- `cd sdk/typescript && npx jest test/verifier --no-coverage 2>&1 | tail -15`
- `git diff --check`

Rollout / migration notes:
- The new field is additive only. Existing consumers that destructure the result object will not break.
- Do not change the `verify --json` output contract (`bundle.schema_version` remains `VERIFY_BUNDLE_SCHEMA_VERSION` = 1).
- The new field is the bundle's *internal* `chain_metadata.schema_version`, not the output contract version.

### ISSUE 2 · **[P1][conformance] Add verifier conformance vector for `evidence_taxonomy_version` rejection path**

Owner: conformance

Affected modules:
- Python verifier conformance vectors
- TypeScript verifier conformance tests
- Conformance fixture maintenance

Acceptance criteria:
1. Add a conformance vector (in `verifier_conformance_vectors.json`) for a bundle whose `chain_metadata.evidence_taxonomy_version` is set to a non-1 value (e.g. `999`).
2. The expected `error_code` is `VERIFY_METADATA_CLOSURE_FAILED` and `primary_reason` is `att.verify.schema_unknown`.
3. The vector passes through both Python and TypeScript verifier conformance tests.
4. Reference the existing `test_require_taxonomy_version.py` test coverage (which tests the `--require-taxonomy-version` CLI flag) without duplicating the CLI path.

Validation commands:
- `PYTHONPATH=sdk/python/src pytest tests/conformance -k 'verifier' -q --tb=short`
- `cd sdk/typescript && npx jest test/verifier_conformance --no-coverage 2>&1 | tail -15`
- `git diff --check`

Rollout / migration notes:
- Add the vector to the verifier conformance vectors JSON file.
- Lock new fixtures only; do not regenerate unrelated fixtures.
- The CLI `--require-taxonomy-version` path is tested separately in `test_require_taxonomy_version.py`.

## P2 Issues

### ISSUE 3 · **[P2][docs][release] Document the v1.8.9 user-visible delta and the `schema_version` SDK surface**

Owner: docs/release

Affected modules:
- docs
- release notes
- validation evidence

Acceptance criteria:
1. Document the v1.8.9 user-visible delta: note that the release carried only autodev/CI fixes and no product-facing changes.
2. Document the new `schema_version` field added to `BundleVerificationResult` and its migration notes.
3. The wording must not imply published packages are blocked and must not touch `CHANGELOG.md`.

Validation commands:
- `markdown-link-check docs/**/*.md`
- `git diff --check`

Rollout / migration notes:
- This is support work only. The product increment is ISSUE 1.
- Do not modify release tags, publish artifacts, or weaken gates.
- Reference the new conformance vector in ISSUE 2 without implying the CLI path is incomplete.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{"anchor_tag":"v1.5.0","consultation_level":"diff","head_sha":"1b1f99f89108ba7b43dcdac0eca0f90dd1f18ee4","issues":[{"acceptance_criteria":["`BundleVerificationResult` gains an `schema_version: int | None` field populated from `chain_metadata.schema_version` during verification.","The field is `None` when the bundle has no `chain_metadata.schema_version`, and the parsed integer value when present.","Python tests cover both the populated and missing-schema paths.","TypeScript `BundleVerificationResult` gains a matching `schemaVersion: number | null` field, populated during `verifyProofBundle`.","TypeScript tests cover both paths.","Existing behavior (error_code, reason_code, taxonomy_version) is unchanged."],"modules":["Python SDK verifier","Python SDK CLI verify JSON output","TypeScript SDK verifier"],"ordinal":1,"priority":"P1","rollout_notes":"The new field is additive only. Existing consumers that destructure the result object will not break. Do not change the `verify --json` output contract (`bundle.schema_version` remains `VERIFY_BUNDLE_SCHEMA_VERSION` = 1). The new field is the bundle's *internal* `chain_metadata.schema_version`, not the output contract version.","title":"[P1][sdk][verifier] Add `schema_version` to Python `BundleVerificationResult` for bundle chain-metadata schema parity","validation_commands":["PYTHONPATH=sdk/python/src pytest sdk/python/tests -k 'schema_version' -q --tb=short","PYTHONPATH=sdk/python/src pytest tests/verifier -q --tb=short","cd sdk/typescript && npx jest test/verifier --no-coverage 2>&1 | tail -15","git diff --check"]},{"acceptance_criteria":["Add a conformance vector (in `verifier_conformance_vectors.json`) for a bundle whose `chain_metadata.evidence_taxonomy_version` is set to a non-1 value (e.g. `999`).","The expected `error_code` is `VERIFY_METADATA_CLOSURE_FAILED` and `primary_reason` is `att.verify.schema_unknown`.","The vector passes through both Python and TypeScript verifier conformance tests.","Reference the existing `test_require_taxonomy_version.py` test coverage (which tests the `--require-taxonomy-version` CLI flag) without duplicating the CLI path."],"modules":["Python verifier conformance vectors","TypeScript verifier conformance tests","Conformance fixture maintenance"],"ordinal":2,"priority":"P1","rollout_notes":"Add the vector to the verifier conformance vectors JSON file. Lock new fixtures only; do not regenerate unrelated fixtures. The CLI `--require-taxonomy-version` path is tested separately in `test_require_taxonomy_version.py`.","title":"[P1][conformance] Add verifier conformance vector for `evidence_taxonomy_version` rejection path","validation_commands":["PYTHONPATH=sdk/python/src pytest tests/conformance -k 'verifier' -q --tb=short","cd sdk/typescript && npx jest test/verifier_conformance --no-coverage 2>&1 | tail -15","git diff --check"]},{"acceptance_criteria":["Document the v1.8.9 user-visible delta: note that the release carried only autodev/CI fixes and no product-facing changes.","Document the new `schema_version` field added to `BundleVerificationResult` and its migration notes.","The wording must not imply published packages are blocked and must not touch `CHANGELOG.md`."],"modules":["docs","release notes","validation evidence"],"ordinal":3,"priority":"P2","rollout_notes":"This is support work only. The product increment is ISSUE 1. Do not modify release tags, publish artifacts, or weaken gates. Reference the new conformance vector in ISSUE 2 without implying the CLI path is incomplete.","title":"[P2][docs][release] Document the v1.8.9 user-visible delta and the `schema_version` SDK surface","validation_commands":["markdown-link-check docs/**/*.md","git diff --check"]}],"milestone_tag":"v1.8.9","plan_level":"daily","schema":"attestplane.plan.v1","schema_version":1}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
