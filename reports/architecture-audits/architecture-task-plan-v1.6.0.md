<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

## Auto-Generated Daily Plan

Milestone: `v1.6.0`
Anchor: `v1.5.0`
Head SHA: `f1b6241f1c07da33cac5fd483babdfbac0867c37`

This plan was generated after a diff-level Opus consultation. It creates
planning issues only; implementation still starts from the generated
`planned-task` issues, one issue at a time.

Product increment policy: at least one P0/P1 task must change Attestplane
SDK, verifier, proof-bundle, canonicalization, conformance, signing,
anchoring, CLI, or API behavior. Release/train/docs-only work is support
work and cannot satisfy this plan by itself.

Recent real commits considered:

- `b000b565c5ca` ci: use local python on opus runner
- `0cf46605f5b2` ci: run architecture planning on opus runner
- `a029c06e9c6c` test: cover opus planning levels
- `fd35d1057906` fix: consult opus for stable planning
- `84150013415a` fix: make stable train git proxy strategy explicit
- `6b3e59a3de3b` ci: ignore transient scorecard link failures
- `ccc1e42769e5` fix: reload planned issues from github
- `31aa211b069f` fix: include open issues in release planning
- `dceefbd5ce25` fix: fan out daily architecture plans
- `4c43d96800d9` fix: generate daily architecture audit plans

Open GitHub issues considered:

- none

**ISSUE 1 · [P1][sdk][verifier] Add a verifier-facing product increment for v1.6.0**
- Priority: P1
- Affected modules: Python SDK verifier, TypeScript SDK verifier, proof bundle fixtures
- Acceptance criteria:
  1. Implement one small verifier or proof-bundle behavior that is visible to SDK users.
  2. Keep the change backward compatible with the current stable proof bundle contract.
  3. Record the product-facing behavior and validation evidence on the task issue before close.
- Validation commands:
  - `sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'verifier or proof_bundle or conformance' -x`
  - `npm test --prefix sdk/typescript -- --runInBand`
  - `git diff --check`
- Rollout / migration notes: Daily work should land a real Attestplane product delta before any release-train-only task.

**ISSUE 2 · [P1][test][conformance] Pin cross-SDK coverage for the daily product change**
- Priority: P1
- Affected modules: Python SDK tests, TypeScript SDK tests, conformance fixtures
- Acceptance criteria:
  1. Add or update conformance coverage for the product behavior from issue 1.
  2. Confirm Python and TypeScript validation expectations stay aligned.
  3. Record the validation evidence on the task issue before close.
- Validation commands:
  - `sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'conformance or canonical or roundtrip' -x`
  - `npm test --prefix sdk/typescript -- --runInBand`
  - `git diff --check`
- Rollout / migration notes: Coverage must follow the product change, not release metadata churn.

**ISSUE 3 · [P2][docs][api] Document the user-visible product delta for v1.6.0**
- Priority: P2
- Affected modules: docs, SDK API docs, release notes
- Acceptance criteria:
  1. Document the verifier or proof-bundle behavior added by issue 1.
  2. Link the documentation to the source planning issue and task issues.
  3. Keep wording within claim boundaries and avoid secrets.
- Validation commands:
  - `git diff --check`
- Rollout / migration notes: Docs-only work cannot satisfy the daily plan unless issue 1 lands a product change.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{"anchor_tag":"v1.5.0","consultation_level":"diff","head_sha":"f1b6241f1c07da33cac5fd483babdfbac0867c37","issues":[{"acceptance_criteria":["Implement one small verifier or proof-bundle behavior that is visible to SDK users.","Keep the change backward compatible with the current stable proof bundle contract.","Record the product-facing behavior and validation evidence on the task issue before close."],"modules":["Python SDK verifier","TypeScript SDK verifier","proof bundle fixtures"],"ordinal":1,"priority":"P1","rollout_notes":"Daily work should land a real Attestplane product delta before any release-train-only task.","title":"[P1][sdk][verifier] Add a verifier-facing product increment for v1.6.0","validation_commands":["sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'verifier or proof_bundle or conformance' -x","npm test --prefix sdk/typescript -- --runInBand","git diff --check"]},{"acceptance_criteria":["Add or update conformance coverage for the product behavior from issue 1.","Confirm Python and TypeScript validation expectations stay aligned.","Record the validation evidence on the task issue before close."],"modules":["Python SDK tests","TypeScript SDK tests","conformance fixtures"],"ordinal":2,"priority":"P1","rollout_notes":"Coverage must follow the product change, not release metadata churn.","title":"[P1][test][conformance] Pin cross-SDK coverage for the daily product change","validation_commands":["sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'conformance or canonical or roundtrip' -x","npm test --prefix sdk/typescript -- --runInBand","git diff --check"]},{"acceptance_criteria":["Document the verifier or proof-bundle behavior added by issue 1.","Link the documentation to the source planning issue and task issues.","Keep wording within claim boundaries and avoid secrets."],"modules":["docs","SDK API docs","release notes"],"ordinal":3,"priority":"P2","rollout_notes":"Docs-only work cannot satisfy the daily plan unless issue 1 lands a product change.","title":"[P2][docs][api] Document the user-visible product delta for v1.6.0","validation_commands":["git diff --check"]}],"milestone_tag":"v1.6.0","plan_id":"ef106eb7d0d63c8e","plan_level":"daily","schema":"attestplane.plan.v1","schema_version":1}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
