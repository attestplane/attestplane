<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Daily Development Plan for v1.8.7

## Development Plan Request

- milestone: `v1.8.7`
- plan_level: `daily`
- anchor: `v1.5.0`
- head_sha: `febce07ff1a78637cfb4cfe0bcddab841a8bd189`
- stable releases since anchor: `31`
- real commits since anchor: `163`
- release-prep commits since anchor: `34`
- decision: `daily-plan` / `daily_small_upgrade`

## Opus Prompt

Run locally from the repository root after downloading the workflow artifact:

```bash
ask_opus.sh architect "$(cat reports/architecture-audits/architecture-gap-audit-v1.8.7.md)"
```

The review should first produce a concise plan, then decompose the
plan into issue-ready P0/P1/P2 sections. The workflow posts that plan
back as a comment on this issue. Opus-authored plans are parsed
directly from their issue-ready Markdown; deterministic fallback plans
also include a structured `ATT_PLAN_SCHEMA_V1` block. The
`plan-to-issues` workflow converts
those sections into GitHub issues with `planned-task` plus the
appropriate priority/module labels. No planned task should be
implemented directly from this planning issue, the Opus output, or
chat. Daily small upgrades stay on a diff-level plan; `x.5.0`
milestones should focus on medium product gaps; integer `x.0.0`
milestones should focus on architecture-level redesign, compatibility,
security boundaries, and migration risk. Return issue-ready P0/P1/P2
tasks with owners, affected modules, acceptance criteria, and
validation commands. Do not include secrets, do not move release tags,
and do not block already published packages.

Product increment is mandatory: every accepted daily, medium, or
architecture plan must include at least one P0/P1 task that changes
Attestplane SDK, verifier, proof-bundle, canonicalization, conformance,
signing, anchoring, CLI, or API behavior. Release train, CI, runner,
docs, observability, and package metadata tasks are support work only
unless the request shows an active blocker.

## Recent Real Commits

- `febce07ff1a7` 2026-05-29T20:53:04+08:00 fix(autodev): handle CI failure
- `3f629638ca25` 2026-05-29T20:37:16+08:00 fix(auto-loop): publish to latest channel — autodev patches are production releases
- `4ed62c481c6a` 2026-05-29T20:18:06+08:00 feat(auto-loop): auto-publish alpha release via release-cd after each semver tag
- `c20d887159b2` 2026-05-29T20:08:39+08:00 feat(autodev): wait for CI checks before merge (10 min timeout, fail-fast on required failures)
- `f62fb364d189` 2026-05-29T19:57:08+08:00 fix(auto-loop): use shell interpolation for version bump
- `abc712e7fbd7` 2026-05-29T19:46:36+08:00 fix(auto-loop): use git log %ct (epoch) instead of %cI
- `fc316c61b05a` 2026-05-29T19:37:54+08:00 chore: re-trigger auto-loop with timezone fix applied [autodev]
- `81197270406f` 2026-05-29T19:17:01+08:00 fix(auto-loop): normalize tag_date to UTC epoch
- `b036afb9130f` 2026-05-29T19:07:05+08:00 chore: trigger auto-loop after Loop 1 batch close [autodev]
- `3df241aff197` 2026-05-29T18:56:52+08:00 fix(autodev): rebase PR branch on main before squash-merge

## Current Open GitHub Issues

The plan must consider all currently open issues, not only tasks generated
from this milestone. Avoid duplicating open work; extend or reference
existing issues when the new plan overlaps.

- No open issues loaded — deterministic fallback plan.

## Issue-First Completion Contract

1. Run the Opus consultation for the milestone-level plan.
2. Post the generated issue-ready plan as a comment on this issue.
3. Let the `plan-to-issues` workflow create one GitHub issue per accepted P0/P1/P2 task with `planned-task`.
4. Link every generated task issue back here before implementation starts.
5. Keep the planning issue open as the source of truth until the task
   set is created and the milestone owner accepts the plan.

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
