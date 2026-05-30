<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Daily Development Plan for v1.7.0

## Concise Plan

- This daily small-upgrade carries the first product-bearing stable cut since
  v1.5.0. The product increment is already landed (commits `3f551d9`,
  `5b32c86`, `8cb5458`): non-empty proof bundles on demand, product-delta
  release gating, and autodev product prioritization.
- Keep the remaining work diff-level and focused: close the SDK proof-bundle
  builder API boundary gaps (typed error coverage for edge cases), pin a
  strict-schema output-contract fixture for CI consumers, and finalize the
  integrator migration documentation.
- Reference the already-open v1.7.0 planning issues instead of duplicating
  their scope.

## P0 Issues

### ISSUE 1 · [P0][verifier][sdk] Close SDK proof-bundle builder API boundary gaps and verify strict-mode typed error coverage

Owner: verifier/SDK

Affected modules:

- Python SDK ProofBundleBuilder
- TypeScript SDK ProofBundleBuilder
- Verifier error handling (EmptyProofBundleError, IncompleteProofBundleError)

Acceptance criteria:

1. `ProofBundleBuilder.minimal(subject_digest, signer)` raises
   `EmptyProofBundleError` for zero-length digest in both Python and
   TypeScript SDKs.
2. `ProofBundleBuilder.minimal(subject_digest, signer)` raises
   `IncompleteProofBundleError` for nil/invalid signer in both Python and
   TypeScript SDKs.
3. Python/TypeScript verifier strict-mode
   (`require_signed_attestation=True`) produces the same error-code
   mapping for the same malformed strict-bundle input.
4. Existing human-readable failure strings and public symbols are unchanged.

Validation commands:

- `PYTHONPATH=sdk/python/src pytest sdk/python/tests/test_proof_bundle.py -q`
- `cd sdk/typescript && npm test -- --testPathPattern=proof_bundle.test.ts`
- `PYTHONPATH=sdk/python/src pytest tests/conformance -k "strict or minimum_schema" -q`
- `cd sdk/typescript && npm test -- --testPathPattern=verifier_conformance`
- `git diff --check`

Rollout / migration notes:

- Keep current failure semantics stable during the migration window.
- Do not remove or rename existing error fields or human-readable strings.

## P1 Issues

### ISSUE 2 · [P1][conformance][cli] Pin strict-schema output-contract fixture for CI consumers

Owner: conformance/CLI

Affected modules:

- CLI output-contract fixture
- Python verifier conformance vectors
- TypeScript verifier conformance test
- Fixture-lock maintenance (FIXTURE_HASHES.lock)

Acceptance criteria:

1. A pinned `verify --json` output-contract fixture is added for
   strict-mode rejection
   (`require_non_empty=True`, `require_signed_attestation=True`).
2. The fixture is locked in `FIXTURE_HASHES.lock` and verified by the
   fixture-lock verification script.
3. A positive forward-compatible vector exists for additive-optional
   fields under the strict schema.
4. Existing negative vectors rejecting malformed strict bundles remain
   intact and unchanged.

Validation commands:

- `PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance -k "strict or non_empty" -q`
- `python scripts/conformance/verify_fixture_lock.py`
- `cd sdk/typescript && npm test -- --runInBand 2>&1 | tail -10`
- `git diff --check`

Rollout / migration notes:

- Update locked fixture hashes only for intentionally added vectors.
- Do not regenerate unrelated fixtures or modify existing negative vectors.

## P2 Issues

### ISSUE 3 · [P2][docs][release] Finalize v1.7.0 integrator migration documentation

Owner: docs/release

Affected modules:

- docs/release-notes/v1.7.0.md
- validation evidence
- runbooks (cross-reference)

Acceptance criteria:

1. `docs/release-notes/v1.7.0.md` reflects the actual landed product delta
   including `--require-non-empty`, `--strict-schema`, and
   `ProofBundleBuilder.minimal()` migration path.
2. A reason-code catalog section is added referencing the SDK-public
   `att.verify.*` taxonomy with all codes, meanings, and migration notes.
3. Migration examples for `EmptyProofBundleError` and
   `IncompleteProofBundleError` are included.
4. All links resolve and documentation entries are consistent with the
   changelog.

Validation commands:

- `markdown-link-check docs/release-notes/v1.7.0.md --quiet`
- `git diff --check`

Rollout / migration notes:

- Docs-only support task. Must not modify CHANGELOG.md, release tags, or
  published artifacts.
- Must not replace the product increment mandate in this plan.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{"anchor_tag":"v1.5.0","consultation_level":"diff","head_sha":"cb3d33451aeac60d6314e49e5079bdccc9862778","issues":[{"acceptance_criteria":["ProofBundleBuilder.minimal(subject_digest, signer) raises EmptyProofBundleError for zero-length digest in both Python and TypeScript SDKs.","ProofBundleBuilder.minimal(subject_digest, signer) raises IncompleteProofBundleError for nil/invalid signer in both Python and TypeScript SDKs.","Python/TypeScript verifier strict-mode (require_signed_attestation=True) produces the same error-code mapping for the same malformed strict-bundle input.","Existing human-readable failure strings and public symbols are unchanged."],"modules":["Python SDK ProofBundleBuilder","TypeScript SDK ProofBundleBuilder","Verifier error handling (EmptyProofBundleError, IncompleteProofBundleError)"],"ordinal":1,"priority":"P0","rollout_notes":"Keep current failure semantics stable during the migration window. Do not remove or rename existing error fields or human-readable strings.","title":"[P0][verifier][sdk] Close SDK proof-bundle builder API boundary gaps and verify strict-mode typed error coverage","validation_commands":["PYTHONPATH=sdk/python/src pytest sdk/python/tests/test_proof_bundle.py -q","cd sdk/typescript && npm test -- --testPathPattern=proof_bundle.test.ts","PYTHONPATH=sdk/python/src pytest tests/conformance -k \"strict or minimum_schema\" -q","cd sdk/typescript && npm test -- --testPathPattern=verifier_conformance","git diff --check"]},{"acceptance_criteria":["A pinned verify --json output-contract fixture is added for strict-mode rejection (require_non_empty=True, require_signed_attestation=True).","The fixture is locked in FIXTURE_HASHES.lock and verified by the fixture-lock verification script.","A positive forward-compatible vector exists for additive-optional fields under the strict schema.","Existing negative vectors rejecting malformed strict bundles remain intact and unchanged."],"modules":["CLI output-contract fixture","Python verifier conformance vectors","TypeScript verifier conformance test","Fixture-lock maintenance (FIXTURE_HASHES.lock)"],"ordinal":2,"priority":"P1","rollout_notes":"Update locked fixture hashes only for intentionally added vectors. Do not regenerate unrelated fixtures or modify existing negative vectors.","title":"[P1][conformance][cli] Pin strict-schema output-contract fixture for CI consumers","validation_commands":["PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance -k \"strict or non_empty\" -q","python scripts/conformance/verify_fixture_lock.py","cd sdk/typescript && npm test -- --runInBand 2>&1 | tail -10","git diff --check"]},{"acceptance_criteria":["docs/release-notes/v1.7.0.md reflects the actual landed product delta including --require-non-empty, --strict-schema, and ProofBundleBuilder.minimal() migration path.","A reason-code catalog section is added referencing the SDK-public att.verify.* taxonomy with all codes, meanings, and migration notes.","Migration examples for EmptyProofBundleError and IncompleteProofBundleError are included.","All links resolve and documentation entries are consistent with the changelog."],"modules":["docs/release-notes/v1.7.0.md","validation evidence","runbooks (cross-reference)"],"ordinal":3,"priority":"P2","rollout_notes":"Docs-only support task. Must not modify CHANGELOG.md, release tags, or published artifacts. Must not replace the product increment mandate in this plan.","title":"[P2][docs][release] Finalize v1.7.0 integrator migration documentation","validation_commands":["markdown-link-check docs/release-notes/v1.7.0.md --quiet","git diff --check"]}],"milestone_tag":"v1.7.0","plan_id":"c1f6ec7ef03950b1","plan_level":"daily","schema":"attestplane.plan.v1","schema_version":1}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
