<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Planned Task: [P1][autodev][auto-loop] Converge mergeability state machine into a single tested function

Source planning issue: #0 (v1.8.19 daily development plan)
Plan schema: `attestplane.plan.v1`
Plan ID: `88e77e0f70082fbf`
Priority: P1

Title: [P1][autodev][auto-loop] Converge mergeability state machine into a single tested function

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
- `cd scripts/autodev && python -m pytest tests/ -x -q`
- `git diff --check`

Rollout / migration notes:
Write the tests first, then refactor. The scattered if-branches serve as the spec. Keep the old path in a compat module for one cycle. This is a pure refactoring landing on infrastructure code, not a product-facing change.

Generated from accepted development plan.
