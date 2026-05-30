# Architecture Gap Audit: v1.8.19

## Development Plan Request

- milestone: `v1.8.19`
- plan_level: `daily`
- anchor: `v1.5.0`
- head_sha: `a1b39380180284b3ccb08469dadf63e623863b5e`
- stable releases since anchor: `43`
- real commits since anchor: `181`
- release-prep commits since anchor: `60`
- decision: `daily-plan` / `daily_small_upgrade`

## Recent Real Commits

- `a16dfec2f99f` 2026-05-29T23:42:35+08:00 chore(versioning): infer CC prefix from issue title; raise batch gate to 10
- `bf4923ba3dae` 2026-05-29T23:24:15+08:00 fix(autodev): extend fix_ci timeout to 20min; UNSTABLE only blocks on pytest/mypy failures
- `fc2d8d360d70` 2026-05-29T23:21:31+08:00 fix(autodev): wait for pending CI before CLEAN early-return; treat UNSTABLE as mergeable
- `17451a08b550` 2026-05-29T23:08:57+08:00 fix(autodev): use -y flag for qwen YOLO mode; increase max-session-turns to 5
- `20e8ecd202fe` 2026-05-29T22:53:23+08:00 fix(autodev): add 5-min cooldown gate in auto-loop to prevent duplicate version tags
- `87a95f401154` 2026-05-29T22:49:04+08:00 fix(autodev): purge whitespace-only diffs before commit; narrow ruff to changed files
- `508c61824002` 2026-05-29T22:32:28+08:00 fix(autodev): properly structure rebase/conflict handling in merge_pr_activity
- `ac7175a7c629` 2026-05-29T22:29:49+08:00 fix(autodev): close conflicting PRs properly; use --auto for rebase+merge
- `50b1616532ff` 2026-05-29T22:20:48+08:00 fix(autodev): handle oversized PR diff in review_pr_activity
- `2db1d7a20f71` 2026-05-29T22:17:41+08:00 fix(autodev): register fix_ci_activity in Temporal worker
- `cbdd2147d9d6` 2026-05-29T22:15:04+08:00 fix(ci): fix YAML syntax in auto-loop batch gate Python fix
- `44a644a27948` 2026-05-29T22:06:14+08:00 fix(ci): use Python for robust epoch comparison in auto-loop batch gate
- `d4bd1d798262` 2026-05-29T21:56:57+08:00 fix(autodev): dispatch auto-loop on PR close; add workflow_dispatch to auto-loop
- `61a7b5906dca` 2026-05-29T21:51:39+08:00 feat(autodev): add fix_ci_activity — Codex auto-fixes CI errors after create_pr
- `f4b12024aed9` 2026-05-29T21:32:41+08:00 fix(auto-loop): generate release artifact stubs before tagging so release-cd Create GitHub Release step succeeds
- `47ff4f792903` 2026-05-29T21:22:06+08:00 fix(autodev): run ruff --fix + format after Codex before commit to reduce CI failures
- `f3616989e6f2` 2026-05-29T21:14:54+08:00 fix(auto-loop): bump package versions before tagging so release-cd sees correct version
- `805e6a22a295` 2026-05-29T21:05:45+08:00 fix(architecture-audit): actions: read → write to allow workflow_dispatch
- `febce07ff1a7` 2026-05-29T20:53:04+08:00 fix(autodev): handle CI failures and REQUEST_CHANGES PRs gracefully
- `3f6296389b6b` 2026-05-29T20:38:58+08:00 fix(auto-loop): publish to latest channel — autodev patches are production releases

## Current Open GitHub Issues

The plan must consider all currently open issues, not only tasks generated
from this milestone. Avoid duplicating open work; extend or reference
existing issues when the new plan overlaps.

- *No open issues snapshot available in this local context.*

## Issue-First Completion Contract

1. Run the Opus consultation for the milestone-level plan.
2. Post the generated issue-ready plan as a comment on this issue.
3. Let the `plan-to-issues` workflow create one GitHub issue per accepted P0/P1/P2 task with `planned-task`.
4. Link every generated task issue back here before implementation starts.
5. Keep the planning issue open as the source of truth until the task set is created and the milestone owner accepts the plan.

## Planned Task Issue Template

Use this shape for each generated task issue:

```markdown
Title: [P1][module] Concrete task title

Source planning issue: #<this issue>
Priority: P0 | P1 | P2
Affected modules:
Acceptance criteria:
Validation commands:
Rollout / migration notes:
```

Execution rule: work only starts from those generated task issues, one
issue at a time, with validation recorded on the task issue before close.
