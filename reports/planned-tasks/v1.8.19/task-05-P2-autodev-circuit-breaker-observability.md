<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Planned Task: [P2][autodev][observability] Add fix-ci circuit breaker and structured autodev metrics

Source planning issue: #0 (v1.8.19 daily development plan)
Plan schema: `attestplane.plan.v1`
Plan ID: `88e77e0f70082fbf`
Priority: P2

Title: [P2][autodev][observability] Add fix-ci circuit breaker and structured autodev metrics

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
Circuit breaker must be mergeable independently of the observability counters. Keep existing timeout (fix_ci_activity 20-min) as a complementary guard. This is support work only and must not become a substitute for the P0/P1 product increment.

Generated from accepted development plan.
