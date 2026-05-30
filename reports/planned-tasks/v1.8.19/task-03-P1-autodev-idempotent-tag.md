<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Planned Task: [P1][autodev][release] Replace cooldown band-aid with idempotent tag push

Source planning issue: #0 (v1.8.19 daily development plan)
Plan schema: `attestplane.plan.v1`
Plan ID: `88e77e0f70082fbf`
Priority: P1

Title: [P1][autodev][release] Replace cooldown band-aid with idempotent tag push

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
- `scripts/release/test_tag_idempotency.sh` (create if needed) or manual two-step verification
- `git diff --check`

Rollout / migration notes:
Remove the cooldown gate only after confirming idempotency is working in CI. Keep the cooldown gate in code for one release cycle as a rollback path. Do not change any existing tag format or signing behavior.

Generated from accepted development plan.
