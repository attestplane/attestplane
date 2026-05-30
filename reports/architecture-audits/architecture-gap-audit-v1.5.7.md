<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

## Development Plan Request

- milestone: `v1.5.7`
- plan_level: `daily`
- anchor: `v1.5.0`
- head_sha: `06f8104676860429bf729565e39cd95eef88a2b6`
- stable releases since anchor: `7`
- real commits since anchor: `13`
- release-prep commits since anchor: `10`
- decision: `daily-plan` / `daily_small_upgrade`

## Opus Prompt

Run locally from the repository root after downloading the workflow artifact:

```bash
ask_opus.sh architect "$(cat reports/architecture-audits/architecture-gap-audit-v1.5.7.md)"
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

- `df1f06239d7e` 2026-05-21T17:56:17+08:00 fix(release): skip idle cadence before remote probe
- `5c238d3e0161` 2026-05-21T18:23:10+08:00 ci: convert accepted plans into task issues
- `3af24b1757e6` 2026-05-21T18:44:24+08:00 ci: auto-accept major architecture plans
- `8167261632fe` 2026-05-21T19:33:51+08:00 Unify plan issuance across release tiers
- `ba569a9fa5f0` 2026-05-21T20:22:51+08:00 Add structured autodev train events
- `5b5ec86fe0d0` 2026-05-21T20:20:55+08:00 Unify release planning schema and fanout
- `42119e46507c` 2026-05-21T22:09:49+08:00 fix: satisfy markdownlint and plan parser test
- `05c9cb26ddae` 2026-05-21T22:18:53+08:00 fix: make release planning scripts importable in CI
- `4c43d96800d9` 2026-05-21T22:40:14+08:00 fix: generate daily architecture audit plans
- `dceefbd5ce25` 2026-05-21T22:43:07+08:00 fix: fan out daily architecture plans
- `31aa211b069f` 2026-05-21T23:15:10+08:00 fix: include open issues in release planning
- `ccc1e42769e5` 2026-05-21T23:18:42+08:00 fix: reload planned issues from github
- `6b3e59a3de3b` 2026-05-21T23:28:24+08:00 ci: ignore transient scorecard link failures

## Current Open GitHub Issues

- none

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
