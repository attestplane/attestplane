<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->
## Development Plan Request

- milestone: `v1.8.1`
- plan_level: `daily`
- anchor: `v1.5.0`
- head_sha: `f61086a3dd18edcb1b2c37f38daf46a3031bc707`
- stable releases since anchor: `25`
- real commits since anchor: `104`
- release-prep commits since anchor: `30`
- decision: `daily-plan` / `daily_small_upgrade`

## Opus Prompt

Run locally from the repository root after downloading the workflow artifact:

```bash
ask_opus.sh architect "$(cat reports/architecture-audits/architecture-gap-audit-v1.8.1.md)"
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

- `60aadf014726` 2026-05-25T11:33:27+08:00 Fix #254: [P1][conformance] Pin `verify --explain` and `verify --json` to the single versioned reason-code taxonomy with a cross-surface parity vector (#264)
- `d828417e0b35` 2026-05-25T11:06:03+08:00 Fix #255: [P1][conformance] Bind landed negative canonicalization vectors to stable reason codes (#263)
- `274a084a12c7` 2026-05-25T10:18:17+08:00 Exclude docs release tasks from product delta recovery
- `919fabe6a916` 2026-05-25T10:10:58+08:00 Include idle product tasks in runner candidate pool
- `9c85484fd62b` 2026-05-25T10:03:37+08:00 Mark lane product tasks during idle recovery
- `d0b5256aaf2c` 2026-05-25T09:36:57+08:00 Recover product-delta idle with implementation tasks
- `8dfcafe4b257` 2026-05-25T04:37:37+08:00 Fix #244: [P1][conformance] Bind landed negative canonicalization vectors to stable reason codes (#251)
- `d07f88e3fb25` 2026-05-25T04:23:57+08:00 Fix #236 public API manifests
- `460a3c90334d` 2026-05-25T04:19:00+08:00 Fix #236: unify verify reason-code taxonomy
- `ee6a31bc2068` 2026-05-25T04:17:12+08:00 Fix #246: [P2][docs] Extend v1.7.x user-visible delta with reason-code taxonomy versioning (#248)
- `5cda4fc8e040` 2026-05-25T03:35:50+08:00 Fix #237 TypeScript formatting
- `c42b50b3c4dc` 2026-05-25T03:28:17+08:00 Fix #237: [P1][sdk] Add negative conformance vector for `schema_version` unknown-required-field rejection
- `b27450025368` 2026-05-25T03:26:48+08:00 Fix #239: [P2][docs] Refresh v1.7.x user-visible delta for landed `--explain` / `--json` / `schema_version` + reason-code stability (#240)
- `a1896fd71e04` 2026-05-25T02:54:53+08:00 Fix #227 CI recovery for verify explain
- `bb3dd5e1cc4c` 2026-05-25T02:33:32+08:00 Fix #227: [P1][cli] Implement `verify --explain` reason-code rationale output
- `921a60a38bd8` 2026-05-25T02:05:10+08:00 Fix #228: [P1][test] Close the #173 ↔ #184/#198 negative-conformance vector gap (#233)
- `8142f6b66288` 2026-05-25T01:55:43+08:00 Fix #230: [P2][docs] Extend v1.7.x user-visible delta with the `--explain` surface once ISSUE 1 lands (#231)
- `aaa73a56f0ec` 2026-05-25T01:55:33+08:00 Fix #229: [P0][security] Resolve release-signing foundation: land minimum viable signing or publish explicit deferral (#232)
- `fa11d4748f3b` 2026-05-25T01:36:39+08:00 Automate product-delta idle recovery
- `c751a4dddce0` 2026-05-25T01:23:23+08:00 Fix #220: add verify JSON CI output

## Current Open GitHub Issues

The plan must consider all currently open issues, not only tasks generated
from this milestone. Avoid duplicating open work; extend or reference
existing issues when the new plan overlaps.

- #500 [tooling] Decouple issue-queue refill from version tag gate in auto-loop
- #415 [P0][anchoring] Restore claim-safe FreeTSA live anchoring verification with quarantine path [priority-P0, planned-task]
- #412 [P1][cli] Pin the versioned `verify --json` output-contract fixture and deterministic exit-code contract for CI gating [priority:P1, area:conformance, planned-task]
- #410 [P1][verifier] Consolidate stable `taxonomy_version` surfacing across `verify --json`, `--explain`, and SDK result object [priority:P1, area:verifier, planned-task]
- #400 [P1][cli] Pin the versioned `verify --json` output-contract fixture and deterministic exit-code contract for CI gating [priority:P1, area:conformance, planned-task]
- #396 [P0][anchoring] Restore claim-safe FreeTSA live anchoring verification with quarantine path [priority-P0, planned-task]
- #366 [P1][verifier] Implement `--require-taxonomy-version` consumer pinning gate with negative conformance vector [priority:P1, area:verifier, planned-task]
- #358 [P1][conformance] Land the positive forward-compatible additive-optional-field acceptance vector under `schema_version` [priority:P1, area:conformance, planned-task]
- #349 [P1][cli] Pin a deterministic `verify` exit-code contract for CI gating [priority:P1, area:conformance, planned-task]
- #347 [P0][anchoring] Restore claim-safe FreeTSA live anchoring verification with quarantine path [priority-P0, planned-task]
- #337 [P1][verifier] Implement `--require-taxonomy-version` consumer pinning gate [priority:P1, area:verifier, planned-task]
- #299 [nightly-anchor] A5 FreeTSA live verification FAILED 2026-05-27 [gate-failure, priority-P0, claim-safety, codex-needs-human]
- #279 [P1][verifier] Add `--require-taxonomy-version` consumer pinning gate to `verify` [priority:P1, area:verifier, planned-task, auto-codex-approved, codex-needs-human]
- #276 [P1][cli] Pin a versioned `verify --json` output-contract fixture for CI consumers [priority:P1, area:conformance, planned-task, auto-codex-approved, codex-needs-human]
- #274 [P1][verifier] Add a consumer `taxonomy_version` pinning gate to `verify` (`--require-taxonomy-version`) [priority:P1, area:verifier, planned-task, auto-codex-approved, codex-pr-opened, codex-needs-human]
- #269 [P2][docs] Document `taxonomy_version` consumer-pinning in the v1.8.x user-visible delta [type:docs, area:docs, priority:P2, planned-task, codex-needs-human]
- #267 [P1][verifier] Surface a stable `taxonomy_version` field on `verify --json` and `--explain` for consumer pinning [priority:P1, area:verifier, planned-task, codex-needs-human]
- #245 [P1][test] Golden lock preventing silent reason-code taxonomy drift [type:docs, priority:P1, planned-task, auto-codex-approved, codex-pr-opened]
- #243 [P1][conformance] Establish single versioned reason-code taxonomy shared by `verify --explain` and `verify --json` [priority:P1, area:verifier, area:conformance, planned-task, auto-codex-approved, codex-pr-opened]
- #211 [P2][docs] Extend v1.7.x user-visible delta with `--explain`, `--json`, and `schema_version` policy [type:docs, area:docs, priority:P2, planned-task, auto-codex-approved, codex-needs-human]
- #210 [P1][test] Close the gap between #173 and the already-landed #184/#198 negative conformance vectors [type:docs, priority:P1, planned-task, auto-codex-approved, codex-pr-opened]
- #207 [P1][cli] Wire `verify --explain` to the reason-code taxonomy landed in #172 [priority:P1, area:conformance, planned-task, auto-codex-approved, codex-needs-human]
- #221 [P1][test] Close the residual gap between #173 negative vectors and the landed #184/#198 set [type:docs, priority:P1, planned-task, auto-codex-approved, codex-needs-human]
- #219 [P1][cli] Implement `verify --explain` consuming the landed reason-code taxonomy [priority:P1, area:conformance, planned-task, auto-codex-approved, codex-needs-human]

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
