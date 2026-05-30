<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

> Plan source: opus-fake-response

## Daily Development Plan for v1.5.7

### Concise Plan

- Keep this daily upgrade diff-level, but close the remaining conformance gap: pin the `schema_version` additive-optional contract in the verifier output fixture and extend cross-SDK `taxonomy_version` coverage.
- The v1.5.0→v1.5.7 cycle built out the release-planning infrastructure (architecture audit trigger, plan schema, plan-to-issues). No product-level verifier or conformance changes landed in that window — these tasks close that gap with a small but real product delta.
- Reference the existing conformance/schema_version vectors instead of duplicating them.

### P0 Issues

No standalone P0 product task is proposed for this daily plan. The release-planning infrastructure from the real commits is already shipped; the product gap is P1-sized and self-contained.

### P1 Issues

**ISSUE 1 · \[P1]\[verifier]\[conformance] Pin additive-optional schema_version conformance contract and verifier output fixture**

Owner: verifier / conformance

Affected modules:

- Python SDK verifier
- verifier conformance fixtures
- CLI output-contract fixture
- schema_version vectors

Acceptance criteria:

1. Add or update the positive forward-compatible vector for unknown additive-optional fields under `schema_version`.
2. Pin a stable `verify --json` output-contract fixture for CI consumers in the v1.5.7 milestone.
3. Keep the negative vectors rejecting malformed or non-forward-compatible shapes passing.
4. Reference existing schema_version conformance issues without duplicating their scope.

Validation commands:

- `PYTHONPATH=sdk/python/src pytest tests/conformance -k "schema_version or forward or additive" -q --tb=short`
- `PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance -q --tb=short`
- `git diff --check`

Rollout / migration notes:

Update locked fixture hashes only if the new vector is intentionally added. Do not regenerate unrelated fixtures.

**ISSUE 2 · \[P1]\[sdk]\[test] Extend cross-SDK taxonomy_version conformance coverage for verifier surface**

Owner: SDK / test

Affected modules:

- Python SDK verifier
- TypeScript SDK verifier
- cross-SDK roundtrip tests
- conformance fixtures

Acceptance criteria:

1. Verify Python and TypeScript SDKs expose the same `taxonomy_version` for identical proof bundles.
2. Add cross-SDK conformance test that compares `verify --json` output across SDK boundaries.
3. Keep existing `error_code` behavior and human-readable failure strings unchanged.

Validation commands:

- `PYTHONPATH=sdk/python/src pytest tests/verifier -k "taxonomy_version or reason_code" -q --tb=short`
- `PYTHONPATH=sdk/python/src pytest sdk/python/tests/cli -q --tb=short`
- `cd sdk/typescript && npm test -- --runInBand`
- `git diff --check`

Rollout / migration notes:

Keep the current failure semantics stable. Do not remove or rename existing error fields.

### P2 Issues

**ISSUE 3 · \[P2]\[docs]\[release] Document the v1.5.7 user-visible delta and conformance boundary**

Owner: docs / release

Affected modules:

- docs
- validation evidence
- release notes

Acceptance criteria:

1. Document the `schema_version` additive-optional behavior and the cross-SDK `taxonomy_version` verification.
2. Record the validation evidence for the verifier output-contract fixture.
3. Keep wording within claim-safety boundaries and do not touch `CHANGELOG.md`.

Validation commands:

- `markdown-link-check docs/**/*.md`
- `git diff --check`

Rollout / migration notes:

Docs-only work cannot satisfy the daily plan unless ISSUE 1 and ISSUE 2 land product changes.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{"anchor_tag":"v1.5.0","consultation_level":"diff","head_sha":"06f8104676860429bf729565e39cd95eef88a2b6","issues":[{"acceptance_criteria":["Add or update the positive forward-compatible vector for unknown additive-optional fields under schema_version.","Pin a stable verify --json output-contract fixture for CI consumers in the v1.5.7 milestone.","Keep the negative vectors rejecting malformed or non-forward-compatible shapes passing.","Reference existing schema_version conformance issues without duplicating their scope."],"modules":["Python SDK verifier","verifier conformance fixtures","CLI output-contract fixture","schema_version vectors"],"ordinal":1,"priority":"P1","rollout_notes":"Update locked fixture hashes only if the new vector is intentionally added. Do not regenerate unrelated fixtures.","title":"[P1][verifier][conformance] Pin additive-optional schema_version conformance contract and verifier output fixture","validation_commands":["PYTHONPATH=sdk/python/src pytest tests/conformance -k \"schema_version or forward or additive\" -q --tb=short","PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance -q --tb=short","git diff --check"]},{"acceptance_criteria":["Verify Python and TypeScript SDKs expose the same taxonomy_version for identical proof bundles.","Add cross-SDK conformance test that compares verify --json output across SDK boundaries.","Keep existing error_code behavior and human-readable failure strings unchanged."],"modules":["Python SDK verifier","TypeScript SDK verifier","cross-SDK roundtrip tests","conformance fixtures"],"ordinal":2,"priority":"P1","rollout_notes":"Keep the current failure semantics stable. Do not remove or rename existing error fields.","title":"[P1][sdk][test] Extend cross-SDK taxonomy_version conformance coverage for verifier surface","validation_commands":["PYTHONPATH=sdk/python/src pytest tests/verifier -k \"taxonomy_version or reason_code\" -q --tb=short","PYTHONPATH=sdk/python/src pytest sdk/python/tests/cli -q --tb=short","cd sdk/typescript && npm test -- --runInBand","git diff --check"]},{"acceptance_criteria":["Document the schema_version additive-optional behavior and the cross-SDK taxonomy_version verification.","Record the validation evidence for the verifier output-contract fixture.","Keep wording within claim-safety boundaries and do not touch CHANGELOG.md."],"modules":["docs","validation evidence","release notes"],"ordinal":3,"priority":"P2","rollout_notes":"Docs-only work cannot satisfy the daily plan unless ISSUE 1 and ISSUE 2 land product changes.","title":"[P2][docs][release] Document the v1.5.7 user-visible delta and conformance boundary","validation_commands":["markdown-link-check docs/**/*.md","git diff --check"]}],"milestone_tag":"v1.5.7","plan_id":"dd7b313679e7e6f2","plan_level":"daily","schema":"attestplane.plan.v1","schema_version":1}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
