<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

> Plan source: deterministic-template
> Opus consultation fallback reason: opus_command_not_configured
## Auto-Generated Daily Plan

Milestone: `v1.6.2`
Anchor: `v1.5.0`
Head SHA: `fa2ee99f9f893615ff9ae378342e7b882fa61c78`

This plan was generated after a diff-level Opus consultation. It creates
planning issues only; implementation still starts from the generated
`planned-task` issues, one issue at a time.

Product increment policy: at least one P0/P1 task must change Attestplane
SDK, verifier, proof-bundle, canonicalization, conformance, signing,
anchoring, CLI, or API behavior. Release/train/docs-only work is support
work and cannot satisfy this plan by itself.

Recent real commits considered:

- `f181c6d4af6d` fix: fetch opus planned issues after creation
- `28127b79a1aa` ci: proxy architecture audit runner network
- `b000b565c5ca` ci: use local python on opus runner
- `0cf46605f5b2` ci: run architecture planning on opus runner
- `a029c06e9c6c` test: cover opus planning levels
- `fd35d1057906` fix: consult opus for stable planning
- `84150013415a` fix: make stable train git proxy strategy explicit
- `6b3e59a3de3b` ci: ignore transient scorecard link failures
- `ccc1e42769e5` fix: reload planned issues from github
- `31aa211b069f` fix: include open issues in release planning

Open GitHub issues considered:

- none

**ISSUE 1 · [P1][sdk][verifier] Add a verifier-facing product increment for v1.6.2**
- Priority: P1
- Affected modules: Python SDK verifier, TypeScript SDK verifier, proof bundle fixtures
- Acceptance criteria:
  1. Implement one small verifier or proof-bundle behavior that is visible to SDK users.
  2. Keep the change backward compatible with the current stable proof bundle contract.
  3. Record the product-facing behavior and validation evidence on the task issue before close.
- Validation commands:
  - `sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'verifier or proof_bundle or conformance' -x`
  - `npm test --prefix sdk/typescript -- --runInBand`
  - `git diff --check`
- Rollout / migration notes: Daily work should land a real Attestplane product delta before any release-train-only task.

**ISSUE 2 · [P1][test][conformance] Pin cross-SDK coverage for the daily product change**
- Priority: P1
- Affected modules: Python SDK tests, TypeScript SDK tests, conformance fixtures
- Acceptance criteria:
  1. Add or update conformance coverage for the product behavior from issue 1.
  2. Confirm Python and TypeScript validation expectations stay aligned.
  3. Record the validation evidence on the task issue before close.
- Validation commands:
  - `sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'conformance or canonical or roundtrip' -x`
  - `npm test --prefix sdk/typescript -- --runInBand`
  - `git diff --check`
- Rollout / migration notes: Coverage must follow the product change, not release metadata churn.

**ISSUE 3 · [P2][docs][api] Document the user-visible product delta for v1.6.2**
- Priority: P2
- Affected modules: docs, SDK API docs, release notes
- Acceptance criteria:
  1. Document the verifier or proof-bundle behavior added by issue 1.
  2. Link the documentation to the source planning issue and task issues.
  3. Keep wording within claim boundaries and avoid secrets.
- Validation commands:
  - `git diff --check`
- Rollout / migration notes: Docs-only work cannot satisfy the daily plan unless issue 1 lands a product change.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{"anchor_tag":"v1.5.0","consultation_level":"diff","head_sha":"fa2ee99f9f893615ff9ae378342e7b882fa61c78","issues":[{"acceptance_criteria":["Implement one small verifier or proof-bundle behavior that is visible to SDK users.","Keep the change backward compatible with the current stable proof bundle contract.","Record the product-facing behavior and validation evidence on the task issue before close."],"modules":["Python SDK verifier","TypeScript SDK verifier","proof bundle fixtures"],"ordinal":1,"priority":"P1","rollout_notes":"Daily work should land a real Attestplane product delta before any release-train-only task.","title":"[P1][sdk][verifier] Add a verifier-facing product increment for v1.6.2","validation_commands":["sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'verifier or proof_bundle or conformance' -x","npm test --prefix sdk/typescript -- --runInBand","git diff --check"]},{"acceptance_criteria":["Add or update conformance coverage for the product behavior from issue 1.","Confirm Python and TypeScript validation expectations stay aligned.","Record the validation evidence on the task issue before close."],"modules":["Python SDK tests","TypeScript SDK tests","conformance fixtures"],"ordinal":2,"priority":"P1","rollout_notes":"Coverage must follow the product change, not release metadata churn.","title":"[P1][test][conformance] Pin cross-SDK coverage for the daily product change","validation_commands":["sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'conformance or canonical or roundtrip' -x","npm test --prefix sdk/typescript -- --runInBand","git diff --check"]},{"acceptance_criteria":["Document the verifier or proof-bundle behavior added by issue 1.","Link the documentation to the source planning issue and task issues.","Keep wording within claim boundaries and avoid secrets."],"modules":["docs","SDK API docs","release notes"],"ordinal":3,"priority":"P2","rollout_notes":"Docs-only work cannot satisfy the daily plan unless issue 1 lands a product change.","title":"[P2][docs][api] Document the user-visible product delta for v1.6.2","validation_commands":["git diff --check"]}],"milestone_tag":"v1.6.2","open_issues":[],"plan_id":"8ffcf15c3da1d588","plan_level":"daily","recent_real_commits":[{"author":"merchloubna70-dot","kind":"real","sha":"f181c6d4af6d6b792e53b17c8d5426cb2c9d805f","subject":"fix: fetch opus planned issues after creation","time":"2026-05-22T01:41:03+08:00"},{"author":"merchloubna70-dot","kind":"real","sha":"28127b79a1aad675bf2ca09e1f84cac34fd969d2","subject":"ci: proxy architecture audit runner network","time":"2026-05-22T01:35:05+08:00"},{"author":"merchloubna70-dot","kind":"real","sha":"b000b565c5ca5fe4c0c42f4ab4d66a5455c70076","subject":"ci: use local python on opus runner","time":"2026-05-22T01:26:27+08:00"},{"author":"merchloubna70-dot","kind":"real","sha":"0cf46605f5b293dd0b3b9e6c4aa5c9ab0bfb805f","subject":"ci: run architecture planning on opus runner","time":"2026-05-22T01:22:08+08:00"},{"author":"merchloubna70-dot","kind":"real","sha":"a029c06e9c6c79dce3d9adbb28a3540bdb9f9813","subject":"test: cover opus planning levels","time":"2026-05-22T01:13:00+08:00"},{"author":"merchloubna70-dot","kind":"real","sha":"fd35d105790643c32d8ea6afc21d194106cd888b","subject":"fix: consult opus for stable planning","time":"2026-05-22T01:04:27+08:00"},{"author":"merchloubna70-dot","kind":"real","sha":"84150013415a62cfee0b63a2e0c30a1f14237601","subject":"fix: make stable train git proxy strategy explicit","time":"2026-05-22T00:34:16+08:00"},{"author":"merchloubna70-dot","kind":"real","sha":"6b3e59a3de3bc902d768e741e460b10cbdca9bfd","subject":"ci: ignore transient scorecard link failures","time":"2026-05-21T23:28:24+08:00"},{"author":"merchloubna70-dot","kind":"real","sha":"ccc1e42769e52a45bab2014964216ce5bb97d673","subject":"fix: reload planned issues from github","time":"2026-05-21T23:18:42+08:00"},{"author":"merchloubna70-dot","kind":"real","sha":"31aa211b069f9fb789e45b07241614f37b2db741","subject":"fix: include open issues in release planning","time":"2026-05-21T23:15:10+08:00"},{"author":"merchloubna70-dot","kind":"real","sha":"dceefbd5ce256f8c1639ca95083471447b5d19ad","subject":"fix: fan out daily architecture plans","time":"2026-05-21T22:43:07+08:00"},{"author":"merchloubna70-dot","kind":"real","sha":"4c43d96800d9bfbb67bb61ce4cb1c8bffa8b88f7","subject":"fix: generate daily architecture audit plans","time":"2026-05-21T22:40:14+08:00"},{"author":"merchloubna70-dot","kind":"real","sha":"05c9cb26ddaeffe467f0f03e5cfb3b1266ef5eda","subject":"fix: make release planning scripts importable in CI","time":"2026-05-21T22:18:53+08:00"},{"author":"merchloubna70-dot","kind":"real","sha":"42119e46507c18da0baf86e074c9a39294a4d5eb","subject":"fix: satisfy markdownlint and plan parser test","time":"2026-05-21T22:09:49+08:00"},{"author":"merchloubna70-dot","kind":"real","sha":"ba569a9fa5f0d7e5edb77460852557b37c84d3b5","subject":"Add structured autodev train events","time":"2026-05-21T20:22:51+08:00"},{"author":"merchloubna70-dot","kind":"real","sha":"5b5ec86fe0d013b4092fb2806263e1c4918ce23f","subject":"Unify release planning schema and fanout","time":"2026-05-21T20:20:55+08:00"},{"author":"merchloubna70-dot","kind":"real","sha":"8167261632feb8466a8028aa66a09f789364bc9f","subject":"Unify plan issuance across release tiers","time":"2026-05-21T19:33:51+08:00"},{"author":"merchloubna70-dot","kind":"real","sha":"3af24b1757e65923eb11c6c47d9a7280e41ddb07","subject":"ci: auto-accept major architecture plans","time":"2026-05-21T18:44:24+08:00"},{"author":"merchloubna70-dot","kind":"real","sha":"5c238d3e01610e185b6982a0f370effb93a81c5f","subject":"ci: convert accepted plans into task issues","time":"2026-05-21T18:23:10+08:00"},{"author":"merchloubna70-dot","kind":"real","sha":"df1f06239d7e5c1ead8a0e0815bf73d13712ea95","subject":"fix(release): skip idle cadence before remote probe","time":"2026-05-21T17:56:17+08:00"}],"schema":"attestplane.plan.v1","schema_version":1}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
