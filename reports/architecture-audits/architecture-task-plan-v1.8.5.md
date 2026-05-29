<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Daily Development Plan for v1.8.5

## Concise Plan

- Keep this daily upgrade diff-level, but make the product increment real: close the remaining `taxonomy_version` parity gap in the verifier/CLI/SDK surface.
- Pin the forward-compatible conformance path for additive-optional `schema_version` fields and lock the consumer-facing output contract.
- Publish a small docs/update task that explains the v1.8.5 user-visible delta and records the validation evidence, without changing `CHANGELOG.md` or any release workflow.
- Reference the already-open taxonomy/version and conformance issues instead of duplicating them.

## P0 Issues

No standalone P0 product task is proposed for this daily plan. The active release-claim blocker remains tracked in the existing open issue set and is handled as support/context work only in this plan.

## P1 Issues

### ISSUE 1 · [P1][verifier][cli] Close the remaining `taxonomy_version` parity gap in verify outputs

Owner: verifier/CLI

Affected modules:

- Python SDK verifier
- Python CLI JSON serialization
- TypeScript SDK verifier
- SDK result object

Acceptance criteria:

1. `verify --json` and `verify --explain` expose the same stable `taxonomy_version` for the same bundle.
2. The SDK result object carries the same version field without changing existing `error_code` behavior or human-readable failure strings.
3. The implementation is linked back to the already-open taxonomy/version issues instead of duplicating them.

Validation commands:

- `PYTHONPATH=sdk/python/src pytest tests/verifier -k 'reason_code or taxonomy_version' -q`
- `PYTHONPATH=sdk/python/src pytest sdk/python/tests/cli -q`
- `cd sdk/typescript && npm test -- --runInBand`
- `git diff --check`

Rollout / migration notes:

- Keep the current failure semantics stable during the migration window.
- Do not remove or rename existing error fields.

### ISSUE 2 · [P1][conformance] Pin forward-compatible additive-optional acceptance and the CI output contract

Owner: conformance

Affected modules:

- Python conformance vectors
- Verifier conformance tests
- CLI output-contract fixture
- Fixture-lock maintenance

Acceptance criteria:

1. Add or update the positive forward-compatible vector for unknown additive-optional fields under `schema_version`.
2. Pin a stable `verify --json` output-contract fixture for CI consumers.
3. Keep the negative vectors rejecting malformed or non-forward-compatible shapes.
4. Reference the existing open conformance issues rather than duplicating their scope.

Validation commands:

- `PYTHONPATH=sdk/python/src pytest tests/conformance -k 'negative or forward' -q`
- `PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance -q`
- `python scripts/conformance/verify_fixture_lock.py`
- `git diff --check`

Rollout / migration notes:

- Update locked fixture hashes only if the new vector is intentionally added.
- Do not regenerate unrelated fixtures.

## P2 Issues

### ISSUE 3 · [P2][docs][release] Document the v1.8.5 user-visible delta and claim-safety boundary

Owner: docs/release

Affected modules:

- docs
- validation evidence
- runbooks

Acceptance criteria:

1. Document the v1.8.5 user-visible delta and the migration notes for the verifier/output-contract work.
2. Record the open blocker context for the live verification claim-safety issue without implying published packages are blocked.
3. Keep the wording within the existing claim-safety boundaries and do not touch `CHANGELOG.md`.

Validation commands:

- `markdown-link-check docs/**/*.md`
- `git diff --check`

Rollout / migration notes:

- This is support work only and must not become a substitute for the product increment.
- Do not modify release tags, publish artifacts, or weaken gates.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{"anchor_tag":"v1.5.0","consultation_level":"diff","head_sha":"06933d29fa1d9d7ec08a5def71736b1c2b5d4256","issues":[{"acceptance_criteria":["`verify --json` and `verify --explain` expose the same stable `taxonomy_version` for the same bundle.","The SDK result object carries the same version field without changing existing `error_code` behavior or human-readable failure strings.","The implementation is linked back to the already-open taxonomy/version issues instead of duplicating them."],"modules":["Python SDK verifier","Python CLI JSON serialization","TypeScript SDK verifier","SDK result object"],"ordinal":1,"priority":"P1","rollout_notes":"Keep the current failure semantics stable during the migration window. Do not remove or rename existing error fields.","title":"[P1][verifier][cli] Close the remaining `taxonomy_version` parity gap in verify outputs","validation_commands":["PYTHONPATH=sdk/python/src pytest tests/verifier -k 'reason_code or taxonomy_version' -q","PYTHONPATH=sdk/python/src pytest sdk/python/tests/cli -q","cd sdk/typescript && npm test -- --runInBand","git diff --check"]},{"acceptance_criteria":["Add or update the positive forward-compatible vector for unknown additive-optional fields under `schema_version`.","Pin a stable `verify --json` output-contract fixture for CI consumers.","Keep the negative vectors rejecting malformed or non-forward-compatible shapes.","Reference the existing open conformance issues rather than duplicating their scope."],"modules":["Python conformance vectors","Verifier conformance tests","CLI output-contract fixture","Fixture-lock maintenance"],"ordinal":2,"priority":"P1","rollout_notes":"Update locked fixture hashes only if the new vector is intentionally added. Do not regenerate unrelated fixtures.","title":"[P1][conformance] Pin forward-compatible additive-optional acceptance and the CI output contract","validation_commands":["PYTHONPATH=sdk/python/src pytest tests/conformance -k 'negative or forward' -q","PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance -q","python scripts/conformance/verify_fixture_lock.py","git diff --check"]},{"acceptance_criteria":["Document the v1.8.5 user-visible delta and the migration notes for the verifier/output-contract work.","Record the open blocker context for the live verification claim-safety issue without implying published packages are blocked.","Keep the wording within the existing claim-safety boundaries and do not touch `CHANGELOG.md`."],"modules":["docs","validation evidence","runbooks"],"ordinal":3,"priority":"P2","rollout_notes":"This is support work only and must not become a substitute for the product increment. Do not modify release tags, publish artifacts, or weaken gates.","title":"[P2][docs][release] Document the v1.8.5 user-visible delta and claim-safety boundary","validation_commands":["markdown-link-check docs/**/*.md","git diff --check"]}],"milestone_tag":"v1.8.5","plan_level":"daily","schema":"attestplane.plan.v1","schema_version":1}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
