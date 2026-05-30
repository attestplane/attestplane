<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Planned Task: [P0][autodev][worktree] Eliminate worktree cross-deletion by enforcing per-job directory isolation

Source planning issue: #0 (v1.8.19 daily development plan)
Plan schema: `attestplane.plan.v1`
Plan ID: `88e77e0f70082fbf`
Priority: P0

Title: [P0][autodev][worktree] Eliminate worktree cross-deletion by enforcing per-job directory isolation

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
This is the highest-risk change (shared filesystem deletion). Merge only after manual sign-off of the CI e2e concurrency result. Keep old path-based guards for one release cycle before removing them. Do not bundle with any other P0/P1 change.

Generated from accepted development plan.
