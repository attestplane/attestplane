<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Daily Development Plan for v1.6.1

> Plan source: deterministic-template
> Opus consultation fallback reason: opus_command_not_configured

## Concise Plan

- Keep this daily upgrade diff-level, but make the product increment real: the v1.6.1 development cycle unified the release planning architecture across tiers (`architecture_audit_trigger.py`, `plan_schema.py`, `plan_to_issues.py`). Close the remaining parity gaps in the planning fan-out, open-issue ingestion, and deterministic fallback path.
- Pin the `ATT_PLAN_SCHEMA_V1` output contract and add conformance coverage for the unified planning schema.
- Publish a docs/update task that explains the v1.6.1 user-visible delta and records the verification evidence, without changing `CHANGELOG.md` or any release workflow.

## P0 Issues

No standalone P0 product task is proposed for this daily plan. The unified planning workflow infrastructure was landed during this cycle; the remaining gaps are already scoped to P1.

## P1 Issues

### ISSUE 1 · [P1][sdk][verifier] Add a verifier-facing product increment for v1.6.1

Owner: verifier/CLI

Affected modules:

- Python SDK verifier
- TypeScript SDK verifier
- proof bundle fixtures

Acceptance criteria:

1. Implement one small verifier or proof-bundle behavior that is visible to SDK users.
2. Keep the change backward compatible with the current stable proof bundle contract.
3. Record the product-facing behavior and validation evidence on the task issue before close.

Validation commands:

- `sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'verifier or proof_bundle or conformance' -x`
- `npm test --prefix sdk/typescript -- --runInBand`
- `git diff --check`

Rollout / migration notes:

- Daily work should land a real Attestplane product delta before any release-train-only task.

### ISSUE 2 · [P1][test][conformance] Pin cross-SDK coverage for the daily product change

Owner: conformance

Affected modules:

- Python SDK tests
- TypeScript SDK tests
- conformance fixtures

Acceptance criteria:

1. Add or update conformance coverage for the product behavior from issue 1.
2. Confirm Python and TypeScript validation expectations stay aligned.
3. Record the validation evidence on the task issue before close.

Validation commands:

- `sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'conformance or canonical or roundtrip' -x`
- `npm test --prefix sdk/typescript -- --runInBand`
- `git diff --check`

Rollout / migration notes:

- Coverage must follow the product change, not release metadata churn.

## P2 Issues

### ISSUE 3 · [P2][docs][api] Document the user-visible product delta for v1.6.1

Owner: docs/release

Affected modules:

- docs
- SDK API docs
- release notes

Acceptance criteria:

1. Document the verifier or proof-bundle behavior added by issue 1.
2. Link the documentation to the source planning issue and task issues.
3. Keep wording within claim boundaries and avoid secrets.

Validation commands:

- `git diff --check`

Rollout / migration notes:

- Docs-only work cannot satisfy the daily plan unless issue 1 lands a product change.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{"anchor_tag":"v1.5.0","consultation_level":"diff","head_sha":"f2a55d4baea9d27bfac2ea40fd835c0f3e237048","issues":[{"acceptance_criteria":["Implement one small verifier or proof-bundle behavior that is visible to SDK users.","Keep the change backward compatible with the current stable proof bundle contract.","Record the product-facing behavior and validation evidence on the task issue before close."],"modules":["Python SDK verifier","TypeScript SDK verifier","proof bundle fixtures"],"ordinal":1,"priority":"P1","rollout_notes":"Daily work should land a real Attestplane product delta before any release-train-only task.","title":"[P1][sdk][verifier] Add a verifier-facing product increment for v1.6.1","validation_commands":["sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'verifier or proof_bundle or conformance' -x","npm test --prefix sdk/typescript -- --runInBand","git diff --check"]},{"acceptance_criteria":["Add or update conformance coverage for the product behavior from issue 1.","Confirm Python and TypeScript validation expectations stay aligned.","Record the validation evidence on the task issue before close."],"modules":["Python SDK tests","TypeScript SDK tests","conformance fixtures"],"ordinal":2,"priority":"P1","rollout_notes":"Coverage must follow the product change, not release metadata churn.","title":"[P1][test][conformance] Pin cross-SDK coverage for the daily product change","validation_commands":["sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'conformance or canonical or roundtrip' -x","npm test --prefix sdk/typescript -- --runInBand","git diff --check"]},{"acceptance_criteria":["Document the verifier or proof-bundle behavior added by issue 1.","Link the documentation to the source planning issue and task issues.","Keep wording within claim boundaries and avoid secrets."],"modules":["docs","SDK API docs","release notes"],"ordinal":3,"priority":"P2","rollout_notes":"Docs-only work cannot satisfy the daily plan unless issue 1 lands a product change.","title":"[P2][docs][api] Document the user-visible product delta for v1.6.1","validation_commands":["git diff --check"]}],"milestone_tag":"v1.6.1","plan_level":"daily","schema":"attestplane.plan.v1","schema_version":1}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
