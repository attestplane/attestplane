<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Daily Development Plan for v1.8.19

## Concise Plan

- Pin the `taxonomy_version` consensus formatting across the `verify --json` and `verify --explain` CLI surfaces to close a cross-output-format consistency gap, meeting the mandatory product increment.
- Eliminate the YOLO cross-deletion root cause in worktree allocation (P0), replace the 5-minute cooldown band-aid with idempotent tag push (P0/P1), converge the scattered mergeability state machine into a single tested function (P1), and add a fix-ci circuit breaker plus structured autodev observability (P2).
- Reference the already-open conformance and autodev issues instead of duplicating scope where applicable.

## P0 Issues

### ISSUE 1 · [P0][autodev][worktree] Eliminate worktree cross-deletion by enforcing per-job directory isolation

Owner: autodev

Affected modules:
- Worktree allocation logic (scripts/autodev)
- Qwen invocation wrapper
- Shared /tmp worktree lock/fencing

Acceptance criteria:
1. Each job allocates a UUID-based unique worktree path and holds an exclusive `flock` before using it.
2. The Qwen working directory is forcibly restricted to that isolated path via `--cwd` semantics; no job can delete or modify files outside its own worktree.
3. Concurrent execution of 2+ jobs must not produce directory-not-found or cross-deletion errors on any agent worktree (verified via CI e2e).
4. The existing guards in `127773de` and `bf461620` remain as defense-in-depth, but the root cause (same shared path) is eliminated.

Validation commands:
- `cd scripts/autodev && python -m pytest tests/ -k 'worktree or isolation or flock' -x -q`
- `cd scripts/autodev && python -m pytest tests/ -k 'qwen or cwd' -x -q`
- `git diff --check`

Rollout / migration notes:
- This is the highest-risk change (shared filesystem deletion). Merge only after manual sign-off of the CI e2e concurrency result.
- Keep the old path-based guards for one release cycle before removing them, to allow safe rollback.
- Do not bundle with any other P0/P1 change.

## P1 Issues

### ISSUE 2 · [P1][conformance][cli] Pin consensus `taxonomy_version` formatting across `verify --json` and `verify --explain` output surfaces

Owner: cli/conformance

Affected modules:
- Python SDK CLI (`attestplane verify --json`, `attestplane verify --explain`)
- Python CLI output formatting
- Conformance golden fixtures
- Fixture-lock maintenance

Acceptance criteria:
1. `verify --json` and `verify --explain` expose the same stable `taxonomy_version` integer for the same proof bundle.
2. The Python SDK CLI renders `taxonomy_version` consistently across both output formats (no string vs. int mismatch, no missing field).
3. A conformance fixture pins the combined `--json` + `--explain` consensus contract.
4. Reference the existing open conformance issues rather than duplicating their scope.

Validation commands:
- `cd sdk/python && python -m pytest tests/cli -k 'taxonomy_version or explain' -x -q`
- `cd sdk/python && python -m pytest tests/conformance -k 'taxonomy_version' -x -q`
- `python scripts/conformance/verify_fixture_lock.py`
- `git diff --check`

Rollout / migration notes:
- Keep existing `exit_code`, `error_code`, and human-readable failure strings unchanged.
- Update locked fixture hashes only for the intentionally added taxonomy_version assertion.
- Do not regenerate unrelated fixtures.

### ISSUE 3 · [P1][autodev][release] Replace cooldown band-aid with idempotent tag push

Owner: autodev

Affected modules:
- auto-loop tag-creation step
- `release/` module tag-allocation logic
- Version-bump script

Acceptance criteria:
1. Before pushing a tag, check `git ls-remote --tags` for existence; if the tag already exists remotely, skip creation (idempotent).
2. Remove the 5-minute cooldown gate from `20e8ecd2` or keep it only as a last-resort safety net.
3. Repeated auto-loop trigger on the same HEAD does not produce duplicate tags or duplicate release-cd dispatches.
4. Manual `workflow_dispatch` with an explicit tag override still works.

Validation commands:
- `scripts/release/test_tag_idempotency.sh` (create if needed) or manual two-step: first push, second push no-op.
- `git diff --check`
- Examine auto-loop CI log for tag-skipped lines.

Rollout / migration notes:
- Remove the cooldown gate only after confirming idempotency is working in CI.
- Keep the cooldown gate in code for one release cycle as a rollback path.
- Do not change any existing tag format or signing behavior.

### ISSUE 4 · [P1][autodev][auto-loop] Converge mergeability state machine into a single tested function

Owner: autodev

Affected modules:
- auto-loop PR-status polling
- CLEAN/UNSTABLE/pending-CI decision logic
- Temporal merge activity

Acceptance criteria:
1. Extract a single pure function `decide_mergeability(pr) -> {MERGE, WAIT, BLOCK}` that enumerates all possible PR states.
2. Replace the scattered if-branches patched in `fc2d8d3`, `bf4923b`, `febce07` with calls to this function.
3. Unit tests cover at least: pending-checks, UNSTABLE-with-pytest-failure, UNSTABLE-with-only-non-pytest-failure, REQUEST_CHANGES, merge-conflict, and clean-pass.
4. Existing behavior is preserved; no regression in the auto-loop cycle.

Validation commands:
- `cd scripts/autodev && python -m pytest tests/ -k 'mergeability or decide_merge' -x -q`
- `cd scripts/autodev && python -m pytest tests/ -x -q` (full suite no regression)
- `git diff --check`

Rollout / migration notes:
- Write the tests first, then refactor. The scattered if-branches serve as the spec.
- Keep the old implementation path in a compat module for one cycle, but default to the new function.
- This is a pure refactoring landing on infrastructure code, not a product-facing change.

## P2 Issues

### ISSUE 5 · [P2][autodev][observability] Add fix-ci circuit breaker and structured autodev metrics

Owner: autodev

Affected modules:
- `fix_ci_activity` implementation
- auto-loop stage log formatting
- Release-train metrics

Acceptance criteria:
1. Limit auto-fix retries per PR to maximum 2 attempts; consecutive failed retries without improvement mark the PR as `needs-human`.
2. Emit structured counters for: tag-conflict rate, whitespace-only diff rate, CI auto-fix attempt count, mergeability-state transitions.
3. Output goes to the existing structured log channel; no new dependencies or dashboards are introduced.
4. Documentation for the counters is added to the autodev runbook.

Validation commands:
- `cd scripts/autodev && python -m pytest tests/ -k 'circuit_breaker or fix_ci' -x -q`
- `git diff --check`
- `markdown-link-check docs/runbooks/autodev-train.md`

Rollout / migration notes:
- Circuit breaker must be mergeable independently of the observability counters.
- Keep existing timeout (`fix_ci_activity` 20-min) as a complementary guard.
- This is support work only and must not become a substitute for the P0/P1 product increment.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{"anchor_tag":"v1.5.0","consultation_level":"diff","head_sha":"a1b39380180284b3ccb08469dadf63e623863b5e","issues":[{"acceptance_criteria":["Each job allocates a UUID-based unique worktree path and holds an exclusive flock before using it.","The Qwen working directory is forcibly restricted to that isolated path via --cwd semantics; no job can delete or modify files outside its own worktree.","Concurrent execution of 2+ jobs must not produce directory-not-found or cross-deletion errors on any agent worktree (verified via CI e2e).","The existing guards in 127773de and bf461620 remain as defense-in-depth, but the root cause (same shared path) is eliminated."],"modules":["Worktree allocation logic (scripts/autodev)","Qwen invocation wrapper","Shared /tmp worktree lock/fencing"],"ordinal":1,"priority":"P0","rollout_notes":"This is the highest-risk change (shared filesystem deletion). Merge only after manual sign-off of the CI e2e concurrency result. Keep old path-based guards for one release cycle before removing them. Do not bundle with any other P0/P1 change.","title":"[P0][autodev][worktree] Eliminate worktree cross-deletion by enforcing per-job directory isolation","validation_commands":["cd scripts/autodev && python -m pytest tests/ -k 'worktree or isolation or flock' -x -q","cd scripts/autodev && python -m pytest tests/ -k 'qwen or cwd' -x -q","git diff --check"]},{"acceptance_criteria":["verify --json and verify --explain expose the same stable taxonomy_version integer for the same proof bundle.","The Python SDK CLI renders taxonomy_version consistently across both output formats (no string vs int mismatch, no missing field).","A conformance fixture pins the combined --json + --explain consensus contract.","Reference the existing open conformance issues rather than duplicating their scope."],"modules":["Python SDK CLI (attestplane verify --json, verify --explain)","Python CLI output formatting","Conformance golden fixtures","Fixture-lock maintenance"],"ordinal":2,"priority":"P1","rollout_notes":"Keep existing exit_code, error_code, and human-readable failure strings unchanged. Update locked fixture hashes only for the intentionally added taxonomy_version assertion. Do not regenerate unrelated fixtures.","title":"[P1][conformance][cli] Pin consensus taxonomy_version formatting across verify --json and verify --explain output surfaces","validation_commands":["cd sdk/python && python -m pytest tests/cli -k 'taxonomy_version or explain' -x -q","cd sdk/python && python -m pytest tests/conformance -k 'taxonomy_version' -x -q","python scripts/conformance/verify_fixture_lock.py","git diff --check"]},{"acceptance_criteria":["Before pushing a tag, check git ls-remote --tags for existence; if the tag already exists remotely, skip creation (idempotent).","Remove the 5-minute cooldown gate from 20e8ecd2 or keep it only as a last-resort safety net.","Repeated auto-loop trigger on the same HEAD does not produce duplicate tags or duplicate release-cd dispatches.","Manual workflow_dispatch with an explicit tag override still works."],"modules":["auto-loop tag-creation step","release/ module tag-allocation logic","Version-bump script"],"ordinal":3,"priority":"P1","rollout_notes":"Remove the cooldown gate only after confirming idempotency is working in CI. Keep the cooldown gate in code for one release cycle as a rollback path. Do not change any existing tag format or signing behavior.","title":"[P1][autodev][release] Replace cooldown band-aid with idempotent tag push","validation_commands":["scripts/release/test_tag_idempotency.sh (create if needed) or manual two-step verification","git diff --check"]},{"acceptance_criteria":["Extract a single pure function decide_mergeability(pr) -> {MERGE, WAIT, BLOCK} that enumerates all possible PR states.","Replace the scattered if-branches patched in fc2d8d3, bf4923b, febce07 with calls to this function.","Unit tests cover at least: pending-checks, UNSTABLE-with-pytest-failure, UNSTABLE-with-only-non-pytest-failure, REQUEST_CHANGES, merge-conflict, and clean-pass.","Existing behavior is preserved; no regression in the auto-loop cycle."],"modules":["auto-loop PR-status polling","CLEAN/UNSTABLE/pending-CI decision logic","Temporal merge activity"],"ordinal":4,"priority":"P1","rollout_notes":"Write tests first, then refactor. Keep old path in a compat module for one cycle. Refactoring only, not a product-facing change.","title":"[P1][autodev][auto-loop] Converge mergeability state machine into a single tested function","validation_commands":["cd scripts/autodev && python -m pytest tests/ -k 'mergeability or decide_merge' -x -q","cd scripts/autodev && python -m pytest tests/ -x -q","git diff --check"]},{"acceptance_criteria":["Limit auto-fix retries per PR to maximum 2 attempts; consecutive failed retries without improvement mark the PR as needs-human.","Emit structured counters for: tag-conflict rate, whitespace-only diff rate, CI auto-fix attempt count, mergeability-state transitions.","Output goes to existing structured log channel; no new dependencies or dashboards are introduced.","Documentation for the counters is added to the autodev runbook."],"modules":["fix_ci_activity implementation","auto-loop stage log formatting","Release-train metrics"],"ordinal":5,"priority":"P2","rollout_notes":"Circuit breaker must be mergeable independently of the observability counters. Keep existing timeout (fix_ci_activity 20-min) as a complementary guard. This is support work only.","title":"[P2][autodev][observability] Add fix-ci circuit breaker and structured autodev metrics","validation_commands":["cd scripts/autodev && python -m pytest tests/ -k 'circuit_breaker or fix_ci' -x -q","git diff --check","markdown-link-check docs/runbooks/autodev-train.md"]}],"milestone_tag":"v1.8.19","plan_level":"daily","schema":"attestplane.plan.v1","schema_version":1}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
