<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Daily Development Plan for v1.5.10

## Concise Plan

- The real commits in this train are all release-infrastructure and planning-tooling work (opus consultation, plan schema unification, CI auto-accept/convert). There is no SDK or verifier product delta yet.
- Add a small but real product-facing increment: expose `verify_reason_taxonomy_version` alongside the existing `taxonomy_version` in `verify --json` output and `BundleVerificationResult`, so consumers can distinguish the verifier's own reason-code taxonomy from the bundle's evidence taxonomy version.
- Mirror the change in the TypeScript SDK to maintain cross-SDK parity.
- Add conformance vectors and update the output-contract fixture for CI.
- Reference the existing opus-planning and release-train issues that were produced in this train; do not duplicate them.

## P0 Issues

No standalone P0 product task is proposed for this daily plan. The active release-claim blocker remains tracked in the existing open issue set and is handled as support/context work only in this plan.

## P1 Issues

### ISSUE 1 · \[P1\]\[sdk\]\[verifier\] Expose `verify_reason_taxonomy_version` in verify output and SDK result object

Owner: sdk/verifier

Affected modules:

- Python SDK verifier (`BundleVerificationResult`)
- Python CLI JSON serialization (`verify --json`)
- TypeScript SDK verifier (`BundleVerificationResult`)
- SDK result object in both languages

Acceptance criteria:

1. `verify --json` output includes `verify_reason_taxonomy_version` alongside the existing `taxonomy_version` field.
2. `BundleVerificationResult` carries `verify_reason_taxonomy_version` without changing existing `error_code`, `primary_reason`, or `secondary_reasons` behavior.
3. The TypeScript SDK mirrors the field in its `BundleVerificationResult` and `verifyProofBundleFile` JSON output.
4. The implementation is backward compatible: existing consumers that read `taxonomy_version` continue to see the same value.
5. Reference the already-open opus-planning issues instead of duplicating them.

Validation commands:

- `PYTHONPATH=sdk/python/src pytest tests/verifier -k 'reason_code or taxonomy_version or verify_json' -q --tb=short`
- `PYTHONPATH=sdk/python/src pytest sdk/python/tests/cli -q --tb=short`
- `cd sdk/typescript && npm test -- --runInBand 2>&1 | tail -20`
- `python3.11 -m ruff check sdk/python/`
- `git diff --check`

Rollout / migration notes:

- Keep the current failure semantics stable during the migration window.
- Do not remove or rename existing `taxonomy_version` or error fields.
- The new field is additive-optional in the JSON output.

### ISSUE 2 · \[P1\]\[conformance\] Pin cross-SDK coverage for `verify_reason_taxonomy_version` exposure

Owner: conformance

Affected modules:

- Python conformance vectors
- Verifier conformance tests
- CLI output-contract fixture
- Fixture-lock maintenance

Acceptance criteria:

1. Add or update conformance vectors that verify `verify_reason_taxonomy_version` is present in both Python and TypeScript verifier output.
2. Pin a stable `verify --json` output-contract fixture for CI consumers that includes the new field.
3. Confirm Python and TypeScript validation expectations stay aligned.
4. Reference the existing open conformance issues rather than duplicating their scope.

Validation commands:

- `PYTHONPATH=sdk/python/src pytest tests/conformance -k 'negative or forward or verify_json' -q --tb=short`
- `PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance -q --tb=short`
- `cd sdk/typescript && npm test -- --runInBand 2>&1 | tail -20`
- `git diff --check`

Rollout / migration notes:

- Update locked fixture hashes only if the new vector is intentionally added.
- Do not regenerate unrelated fixtures.

## P2 Issues

### ISSUE 3 · \[P2\]\[docs\]\[api\] Document the v1.5.10 user-visible `verify_reason_taxonomy_version` delta

Owner: docs/api

Affected modules:

- docs
- SDK API docs
- release notes

Acceptance criteria:

1. Document the `verify_reason_taxonomy_version` field added to `verify --json` output and SDK result objects.
2. Link the documentation to the source planning issue and task issues.
3. Keep wording within claim-safety boundaries and avoid secrets.

Validation commands:

- `markdown-link-check docs/**/*.md`
- `git diff --check`

Rollout / migration notes:

- This is support work only and must not become a substitute for the product increment.
- Do not modify release tags, publish artifacts, or weaken gates.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{"anchor_tag":"v1.5.0","consultation_level":"diff","head_sha":"bfeb6aedc60540041cf76f27298b60b4b99d8c35","issues":[{"acceptance_criteria":["`verify --json` output includes `verify_reason_taxonomy_version` alongside the existing `taxonomy_version` field.","`BundleVerificationResult` carries `verify_reason_taxonomy_version` without changing existing `error_code`, `primary_reason`, or `secondary_reasons` behavior.","The TypeScript SDK mirrors the field in its `BundleVerificationResult` and `verifyProofBundleFile` JSON output.","The implementation is backward compatible: existing consumers that read `taxonomy_version` continue to see the same value.","Reference the already-open opus-planning issues instead of duplicating them."],"modules":["Python SDK verifier","Python CLI JSON serialization","TypeScript SDK verifier","SDK result object"],"ordinal":1,"priority":"P1","rollout_notes":"Keep the current failure semantics stable during the migration window. Do not remove or rename existing `taxonomy_version` or error fields. The new field is additive-optional in the JSON output.","title":"[P1][sdk][verifier] Expose `verify_reason_taxonomy_version` in verify output and SDK result object","validation_commands":["PYTHONPATH=sdk/python/src pytest tests/verifier -k 'reason_code or taxonomy_version or verify_json' -q --tb=short","PYTHONPATH=sdk/python/src pytest sdk/python/tests/cli -q --tb=short","cd sdk/typescript && npm test -- --runInBand 2>&1 | tail -20","python3.11 -m ruff check sdk/python/","git diff --check"]},{"acceptance_criteria":["Add or update conformance vectors that verify `verify_reason_taxonomy_version` is present in both Python and TypeScript verifier output.","Pin a stable `verify --json` output-contract fixture for CI consumers that includes the new field.","Confirm Python and TypeScript validation expectations stay aligned.","Reference the existing open conformance issues rather than duplicating their scope."],"modules":["Python conformance vectors","Verifier conformance tests","CLI output-contract fixture","Fixture-lock maintenance"],"ordinal":2,"priority":"P1","rollout_notes":"Update locked fixture hashes only if the new vector is intentionally added. Do not regenerate unrelated fixtures.","title":"[P1][conformance] Pin cross-SDK coverage for `verify_reason_taxonomy_version` exposure","validation_commands":["PYTHONPATH=sdk/python/src pytest tests/conformance -k 'negative or forward or verify_json' -q --tb=short","PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance -q --tb=short","cd sdk/typescript && npm test -- --runInBand 2>&1 | tail -20","git diff --check"]},{"acceptance_criteria":["Document the `verify_reason_taxonomy_version` field added to `verify --json` output and SDK result objects.","Link the documentation to the source planning issue and task issues.","Keep wording within claim-safety boundaries and avoid secrets."],"modules":["docs","SDK API docs","release notes"],"ordinal":3,"priority":"P2","rollout_notes":"This is support work only and must not become a substitute for the product increment. Do not modify release tags, publish artifacts, or weaken gates.","title":"[P2][docs][api] Document the v1.5.10 user-visible `verify_reason_taxonomy_version` delta","validation_commands":["markdown-link-check docs/**/*.md","git diff --check"]}],"milestone_tag":"v1.5.10","plan_level":"daily","schema":"attestplane.plan.v1","schema_version":1}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
