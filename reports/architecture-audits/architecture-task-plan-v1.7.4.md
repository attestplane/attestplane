<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Daily Development Plan for v1.7.4

## Concise Plan

- Keep this daily upgrade diff-level, but make the product increment real: classify observability
  release-planning automation as product implementation, enabling the stable train product-delta
  gate to correctly detect observability planning tasks as product_implementation_delta rather
  than support_only_delta.
- Cross-wire canonicalization edge-case vectors into signed-schema round-trip regression coverage
  and fix conformance test-helper imports to prevent package-name shadowing.
- Emit structured observability events for the planned-task post-create refetch path, with scoped
  tests and documentation, and ensure the event module is tracked as product implementation.
- Publish a small docs/update task that explains the v1.7.4 user-visible delta and records the
  validation evidence, without changing `CHANGELOG.md` or any release workflow.

## P0 Issues

### ISSUE 1 · \[P0\]\[release\]\[observability\] Classify observability planning as product delta

Owner: release/observability

Affected modules:

- release gate
- product-delta classification
- observability planning workflow
- stable train product-delta checks

Acceptance criteria:

1. `scripts/release/release_gate.py` adds `scripts/observability/` to the
   `PRODUCT_IMPLEMENTATION_PREFIXES` set so that observability planning changes
   are classified as `product_implementation_delta` instead of `support_only_delta`.
2. The release gate correctly returns `product_implementation_delta` when scanning
   a diff range that includes observability planning files.
3. Existing support-only release train scripts remain classified as
   `support_only_delta`.
4. The product-delta gate does not block or accidentally allow observability
   planning changes through a bypass path.

Validation commands:

- `python scripts/release/release_gate.py --release-tag v1.7.4 --channel latest --json`
- `PYTHONPATH=sdk/python/src python -m pytest sdk/python/tests/test_release_gate.py -q --tb=short`
- `git diff --check`

Rollout / migration notes:

- This is the required product increment for the v1.7.4 daily plan.
- Do not remove or weaken existing product-delta bypass paths.
- Do not change the `scripts/release/plan_to_issues.py` classification.

## P1 Issues

### ISSUE 2 · \[P1\]\[canonical\]\[conformance\] Cross-wire canonicalization vectors into signed-schema round-trip regression

Owner: conformance/verifier

Affected modules:

- canonicalization edge-case vectors
- conformance test helpers
- signed-schema round-trip tests
- minimum-bundle canonicalization vectors

Acceptance criteria:

1. Canonicalization edge-case vectors (e.g. empty object, nested keys, unicode
   normalization edge cases, int64 boundary values) are published in
   `tests/conformance/canonicalization_vectors.py`.
2. The signed-schema round-trip regression in
   `tests/verifier/test_signed_schema_roundtrip.py` imports those vectors
   and exercises each one end-to-end through canonicalize → sign → verify.
3. Canonicalization test helpers are loaded by file path so that top-level
   conformance tests are not shadowed by `sdk/python/tests` package names.
4. Negative vectors (malformed canonical JSON) are kept in the conformance
   test suite and are not rebased into the round-trip regression.

Validation commands:

- `PYTHONPATH=sdk/python/src pytest tests/conformance/canonicalization_vectors.py -q --tb=short`
- `PYTHONPATH=sdk/python/src pytest tests/verifier/test_signed_schema_roundtrip.py -q --tb=short`
- `git diff --check`

Rollout / migration notes:

- Add only additive vectors to `canonicalization_vectors.py`; do not remove
  existing vectors unless they conflict with the round-trip schema.
- Keep the helper import fix (`test_canonicalization_minimum_bundle_vectors.py`)
  as a minimal diff that does not refactor the entire module.

### ISSUE 3 · \[P1\]\[observability\]\[release\] Emit structured planned-task post-create fetch events

Owner: observability/release

Affected modules:

- observability events module
- plan-to-issues workflow
- observability docs
- post-create fetch refetch path

Acceptance criteria:

1. `scripts/observability/events.py` defines a structured
   `planned_issue_post_create_fetch` event with fields for milestone,
   created_count, refetched_count, latency_ms, and ok.
2. `scripts/release/plan_to_issues.py` emits this event after creating
   planned-task issues and refetching them from GitHub.
3. The event module is tracked as product implementation (see P0) so that
   future observability changes are visible in the product-delta gate.
4. Scoped tests exist in `tests/observability/test_events.py`.

Validation commands:

- `PYTHONPATH=sdk/python/src pytest tests/observability/test_events.py -q --tb=short`
- `PYTHONPATH=sdk/python/src python -m scripts.release.plan_to_issues --plan-file reports/architecture-audits/architecture-task-plan-v1.8.5.md --source-issue 0 --dry-run --json 2>&1 | head -5`
- `git diff --check`

Rollout / migration notes:

- The event schema is additive; existing events are not changed.
- Dry-run mode (`--dry-run`) should emit a synthetic event for local validation
  without hitting the GitHub API.

## P2 Issues

### ISSUE 4 · \[P2\]\[docs\]\[release\] Document the v1.7.4 user-visible delta and claim-safety boundary

Owner: docs/release

Affected modules:

- docs
- validation evidence
- runbooks

Acceptance criteria:

1. Document the v1.7.4 user-visible delta: the observability planning
   classification change and the canonicalization round-trip coverage.
2. Record the open blocker context for the live verification claim-safety
   issue without implying published packages are blocked.
3. Keep the wording within the existing claim-safety boundaries and do not
   touch `CHANGELOG.md`.

Validation commands:

- `markdown-link-check docs/**/*.md`
- `git diff --check`

Rollout / migration notes:

- This is support work only and must not become a substitute for the product increment.
- Do not modify release tags, publish artifacts, or weaken gates.

### ISSUE 5 · \[P2\]\[runner\] Fix local runner infra: detached-head PR pushes, evidence filtering, and issue starvation

Owner: runner

Affected modules:

- local Codex runner
- runner evidence
- runner PR handling

Acceptance criteria:

1. Local runner handles detached-head state when pushing PR branches.
2. Transient runner markdown (e.g. generated issue descriptions) is treated
   as transient evidence and not persisted as permanent runner evidence.
3. Untracked runner evidence is expanded before filtering to prevent
   exclusion of newly added run artifacts.
4. The local runner does not starve available issues when the issue queue
   is empty or blocked.

Validation commands:

- `python scripts/local_codex_runner/run.py --dry-run 2>&1 | head -20`
- `git diff --check`

Rollout / migration notes:

- These are quality-of-life fixes for the autodev workflow.
- No change to product behavior, SDK surface, or release gates.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{"anchor_tag":"v1.5.0","consultation_level":"diff","head_sha":"28311f82f8798f8d71281791b0cadf7701e82527","issues":[{"acceptance_criteria":["`scripts/release/release_gate.py` adds `scripts/observability/` to the `PRODUCT_IMPLEMENTATION_PREFIXES` set so that observability planning changes are classified as `product_implementation_delta` instead of `support_only_delta`.","The release gate correctly returns `product_implementation_delta` when scanning a diff range that includes observability planning files.","Existing support-only release train scripts remain classified as `support_only_delta`.","The product-delta gate does not block or accidentally allow observability planning changes through a bypass path."],"modules":["release gate","product-delta classification","observability planning workflow","stable train product-delta checks"],"ordinal":1,"priority":"P0","rollout_notes":"This is the required product increment for the v1.7.4 daily plan. Do not remove or weaken existing product-delta bypass paths. Do not change the `scripts/release/plan_to_issues.py` classification.","title":"[P0][release][observability] Classify observability planning as product delta","validation_commands":["python scripts/release/release_gate.py --release-tag v1.7.4 --channel latest --json","PYTHONPATH=sdk/python/src python -m pytest sdk/python/tests/test_release_gate.py -q --tb=short","git diff --check"]},{"acceptance_criteria":["Canonicalization edge-case vectors (e.g. empty object, nested keys, unicode normalization edge cases, int64 boundary values) are published in `tests/conformance/canonicalization_vectors.py`.","The signed-schema round-trip regression in `tests/verifier/test_signed_schema_roundtrip.py` imports those vectors and exercises each one end-to-end through canonicalize \u2192 sign \u2192 verify.","Canonicalization test helpers are loaded by file path so that top-level conformance tests are not shadowed by `sdk/python/tests` package names.","Negative vectors (malformed canonical JSON) are kept in the conformance test suite and are not rebased into the round-trip regression."],"modules":["canonicalization edge-case vectors","conformance test helpers","signed-schema round-trip tests","minimum-bundle canonicalization vectors"],"ordinal":2,"priority":"P1","rollout_notes":"Add only additive vectors to `canonicalization_vectors.py`; do not remove existing vectors unless they conflict with the round-trip schema. Keep the helper import fix as a minimal diff that does not refactor the entire module.","title":"[P1][canonical][conformance] Cross-wire canonicalization vectors into signed-schema round-trip regression","validation_commands":["PYTHONPATH=sdk/python/src pytest tests/conformance/canonicalization_vectors.py -q --tb=short","PYTHONPATH=sdk/python/src pytest tests/verifier/test_signed_schema_roundtrip.py -q --tb=short","git diff --check"]},{"acceptance_criteria":["`scripts/observability/events.py` defines a structured `planned_issue_post_create_fetch` event with fields for milestone, created_count, refetched_count, latency_ms, and ok.","`scripts/release/plan_to_issues.py` emits this event after creating planned-task issues and refetching them from GitHub.","The event module is tracked as product implementation (see P0) so that future observability changes are visible in the product-delta gate.","Scoped tests exist in `tests/observability/test_events.py`."],"modules":["observability events module","plan-to-issues workflow","observability docs","post-create fetch refetch path"],"ordinal":3,"priority":"P1","rollout_notes":"The event schema is additive; existing events are not changed. Dry-run mode (`--dry-run`) should emit a synthetic event for local validation without hitting the GitHub API.","title":"[P1][observability][release] Emit structured planned-task post-create fetch events","validation_commands":["PYTHONPATH=sdk/python/src pytest tests/observability/test_events.py -q --tb=short","PYTHONPATH=sdk/python/src python -m scripts.release.plan_to_issues --plan-file reports/architecture-audits/architecture-task-plan-v1.8.5.md --source-issue 0 --dry-run --json 2>&1 | head -5","git diff --check"]},{"acceptance_criteria":["Document the v1.7.4 user-visible delta: the observability planning classification change and the canonicalization round-trip coverage.","Record the open blocker context for the live verification claim-safety issue without implying published packages are blocked.","Keep the wording within the existing claim-safety boundaries and do not touch `CHANGELOG.md`."],"modules":["docs","validation evidence","runbooks"],"ordinal":4,"priority":"P2","rollout_notes":"This is support work only and must not become a substitute for the product increment. Do not modify release tags, publish artifacts, or weaken gates.","title":"[P2][docs][release] Document the v1.7.4 user-visible delta and claim-safety boundary","validation_commands":["markdown-link-check docs/**/*.md","git diff --check"]},{"acceptance_criteria":["Local runner handles detached-head state when pushing PR branches.","Transient runner markdown (e.g. generated issue descriptions) is treated as transient evidence and not persisted as permanent runner evidence.","Untracked runner evidence is expanded before filtering to prevent exclusion of newly added run artifacts.","The local runner does not starve available issues when the issue queue is empty or blocked."],"modules":["local Codex runner","runner evidence","runner PR handling"],"ordinal":5,"priority":"P2","rollout_notes":"These are quality-of-life fixes for the autodev workflow. No change to product behavior, SDK surface, or release gates.","title":"[P2][runner] Fix local runner infra: detached-head PR pushes, evidence filtering, and issue starvation","validation_commands":["python scripts/local_codex_runner/run.py --dry-run 2>&1 | head -20","git diff --check"]}],"milestone_tag":"v1.7.4","plan_level":"daily","schema":"attestplane.plan.v1","schema_version":1}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
