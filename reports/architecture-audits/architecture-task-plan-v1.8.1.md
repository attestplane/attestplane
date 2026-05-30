<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->
> Plan source: deterministic-template
> Opus consultation fallback reason: opus_command_not_configured

## Auto-Generated Daily Plan

Milestone: `v1.8.1`
Anchor: `v1.5.0`
Head SHA: `f61086a3dd18edcb1b2c37f38daf46a3031bc707`

This plan was generated after a diff-level Opus consultation. It creates
planning issues only; implementation still starts from the generated
`planned-task` issues, one issue at a time.

Product increment policy: at least one P0/P1 task must change Attestplane
SDK, verifier, proof-bundle, canonicalization, conformance, signing,
anchoring, CLI, or API behavior. Release/train/docs-only work is support
work and cannot satisfy this plan by itself.

Recent real commits considered:

- `60aadf014726` Fix #254: [P1][conformance] Pin `verify --explain` and `verify --json` to the single versioned reason-code taxonomy with a cross-surface parity vector (#264)
- `d828417e0b35` Fix #255: [P1][conformance] Bind landed negative canonicalization vectors to stable reason codes (#263)
- `8dfcafe4b257` Fix #244: [P1][conformance] Bind landed negative canonicalization vectors to stable reason codes (#251)
- `460a3c90334d` Fix #236: unify verify reason-code taxonomy
- `bb3dd5e1cc4c` Fix #227: [P1][cli] Implement `verify --explain` reason-code rationale output
- `921a60a38bd8` Fix #228: [P1][test] Close the #173 ↔ #184/#198 negative-conformance vector gap (#233)
- `b8164001c4e3` Fix #209: [P1][sdk] Validate proof-bundle `schema_version` with forward-compatible additive rules (#217)
- `9c29781eeb25` Fix #184: [P1][sdk] Land negative conformance vectors mirroring #150 canonicalization edges (#198)
- `7dce5fc1f036` Fix #172: [P1][verifier] Introduce stable rejection reason-code taxonomy for `verify` failures
- `67849e649247` Fix #137: [P1][sdk] Extend minimum-bundle helper with canonicalization edge-case conformance vectors (#150)

Open GitHub issues considered:

- #415 [P0][anchoring] Restore claim-safe FreeTSA live anchoring verification with quarantine path [priority-P0, planned-task]
- #412 [P1][cli] Pin the versioned `verify --json` output-contract fixture and deterministic exit-code contract for CI gating [priority:P1, area:conformance, planned-task]
- #410 [P1][verifier] Consolidate stable `taxonomy_version` surfacing across `verify --json`, `--explain`, and SDK result object [priority:P1, area:verifier, planned-task]
- #400 [P1][cli] Pin the versioned `verify --json` output-contract fixture and deterministic exit-code contract for CI gating [priority:P1, area:conformance, planned-task]
- #396 [P0][anchoring] Restore claim-safe FreeTSA live anchoring verification with quarantine path [priority-P0, planned-task]
- #366 [P1][verifier] Implement `--require-taxonomy-version` consumer pinning gate with negative conformance vector [priority:P1, area:verifier, planned-task]
- #358 [P1][conformance] Land the positive forward-compatible additive-optional-field acceptance vector under `schema_version` [priority:P1, area:conformance, planned-task]
- #349 [P1][cli] Pin a deterministic `verify` exit-code contract for CI gating [priority:P1, area:conformance, planned-task]

**ISSUE 1 · [P1][verifier][cli] Consolidate `taxonomy_version` surfacing across `verify --json`, `--explain`, and SDK result object**
- Priority: P1
- Affected modules: Python SDK verifier, Python CLI JSON serialization, TypeScript SDK verifier, SDK result object
- Acceptance criteria:
  1. Expose a stable `taxonomy_version` field on `verify --json` and `verify --explain` output (reference #267, #410).
  2. Surface the same `taxonomy_version` on the Python and TypeScript SDK result object without changing existing `error_code` or human-readable failure strings.
  3. Add a cross-surface parity conformance vector that locks the single versioned taxonomy across CLI JSON, CLI explain, and SDK object output.
  4. Link back to existing open issues (#267, #410, #410) instead of duplicating their scope.
- Validation commands:
  - `sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'verifier or conformance or taxonomy_version' -x -q`
  - `npm test --prefix sdk/typescript -- --runInBand`
  - `git diff --check`
- Rollout / migration notes: This product increment is the v1.8.1 mandatory product delta. Keep the current failure semantics stable during migration; do not remove or rename existing error fields.

**ISSUE 2 · [P1][conformance] Pin forward-compatible additive-optional-field acceptance under `schema_version` and CI output contract**
- Priority: P1
- Affected modules: Python conformance vectors, Verifier conformance tests, CLI output-contract fixture, fixture-lock maintenance
- Acceptance criteria:
  1. Add the positive forward-compatible vector for unknown additive-optional fields under `schema_version` (reference #358).
  2. Pin a stable `verify --json` output-contract fixture for CI consumers (reference #412, #400, #276).
  3. Keep the negative vectors rejecting malformed or non-forward-compatible shapes unchanged.
  4. Reference existing open conformance issues (#358, #412) rather than duplicating their scope.
- Validation commands:
  - `sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'conformance or negative or forward' -x -q`
  - `npm test --prefix sdk/typescript -- --runInBand`
  - `python scripts/conformance/verify_fixture_lock.py`
  - `git diff --check`
- Rollout / migration notes: Update locked fixture hashes only if the new vector is intentionally added. Do not regenerate unrelated fixtures.

**ISSUE 3 · [P2][docs][release] Document the v1.8.1 user-visible delta and taxonomy-version consumer-pinning guidance**
- Priority: P2
- Affected modules: docs, validation evidence, release notes
- Acceptance criteria:
  1. Document the v1.8.1 user-visible delta: `taxonomy_version` surfacing and forward-compatible `schema_version` acceptance.
  2. Record the consumer-pinning guidance for `--require-taxonomy-version` (reference #269, #274, #279).
  3. Keep wording within existing claim-safety boundaries and do not touch CHANGELOG.md.
- Validation commands:
  - `markdown-link-check docs/**/*.md`
  - `git diff --check`
- Rollout / migration notes: Docs-only support work. The product increment (issue 1) must land before or alongside this documentation task.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{"anchor_tag":"v1.5.0","consultation_level":"diff","head_sha":"f61086a3dd18edcb1b2c37f38daf46a3031bc707","issues":[{"acceptance_criteria":["Expose a stable `taxonomy_version` field on `verify --json` and `verify --explain` output (reference #267, #410).","Surface the same `taxonomy_version` on the Python and TypeScript SDK result object without changing existing `error_code` or human-readable failure strings.","Add a cross-surface parity conformance vector that locks the single versioned taxonomy across CLI JSON, CLI explain, and SDK object output.","Link back to existing open issues (#267, #410, #410) instead of duplicating their scope."],"modules":["Python SDK verifier","Python CLI JSON serialization","TypeScript SDK verifier","SDK result object"],"ordinal":1,"priority":"P1","rollout_notes":"This product increment is the v1.8.1 mandatory product delta. Keep the current failure semantics stable during migration; do not remove or rename existing error fields.","title":"[P1][verifier][cli] Consolidate `taxonomy_version` surfacing across `verify --json`, `--explain`, and SDK result object","validation_commands":["sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'verifier or conformance or taxonomy_version' -x -q","npm test --prefix sdk/typescript -- --runInBand","git diff --check"]},{"acceptance_criteria":["Add the positive forward-compatible vector for unknown additive-optional fields under `schema_version` (reference #358).","Pin a stable `verify --json` output-contract fixture for CI consumers (reference #412, #400, #276).","Keep the negative vectors rejecting malformed or non-forward-compatible shapes unchanged.","Reference existing open conformance issues (#358, #412) rather than duplicating their scope."],"modules":["Python conformance vectors","Verifier conformance tests","CLI output-contract fixture","fixture-lock maintenance"],"ordinal":2,"priority":"P1","rollout_notes":"Update locked fixture hashes only if the new vector is intentionally added. Do not regenerate unrelated fixtures.","title":"[P1][conformance] Pin forward-compatible additive-optional-field acceptance under `schema_version` and CI output contract","validation_commands":["sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'conformance or negative or forward' -x -q","npm test --prefix sdk/typescript -- --runInBand","python scripts/conformance/verify_fixture_lock.py","git diff --check"]},{"acceptance_criteria":["Document the v1.8.1 user-visible delta: `taxonomy_version` surfacing and forward-compatible `schema_version` acceptance.","Record the consumer-pinning guidance for `--require-taxonomy-version` (reference #269, #274, #279).","Keep wording within existing claim-safety boundaries and do not touch CHANGELOG.md."],"modules":["docs","validation evidence","release notes"],"ordinal":3,"priority":"P2","rollout_notes":"Docs-only support work. The product increment (issue 1) must land before or alongside this documentation task.","title":"[P2][docs][release] Document the v1.8.1 user-visible delta and taxonomy-version consumer-pinning guidance","validation_commands":["markdown-link-check docs/**/*.md","git diff --check"]}],"milestone_tag":"v1.8.1","open_issues":[{"labels":["priority-P0","planned-task"],"number":415,"title":"[P0][anchoring] Restore claim-safe FreeTSA live anchoring verification with quarantine path"},{"labels":["priority:P1","area:conformance","planned-task"],"number":412,"title":"[P1][cli] Pin the versioned `verify --json` output-contract fixture and deterministic exit-code contract for CI gating"},{"labels":["priority:P1","area:verifier","planned-task"],"number":410,"title":"[P1][verifier] Consolidate stable `taxonomy_version` surfacing across `verify --json`, `--explain`, and SDK result object"},{"labels":["priority:P1","area:conformance","planned-task"],"number":400,"title":"[P1][cli] Pin the versioned `verify --json` output-contract fixture and deterministic exit-code contract for CI gating"},{"labels":["priority-P0","planned-task"],"number":396,"title":"[P0][anchoring] Restore claim-safe FreeTSA live anchoring verification with quarantine path"},{"labels":["priority:P1","area:verifier","planned-task"],"number":366,"title":"[P1][verifier] Implement `--require-taxonomy-version` consumer pinning gate with negative conformance vector"},{"labels":["priority:P1","area:conformance","planned-task"],"number":358,"title":"[P1][conformance] Land the positive forward-compatible additive-optional-field acceptance vector under `schema_version`"},{"labels":["priority:P1","area:conformance","planned-task"],"number":349,"title":"[P1][cli] Pin a deterministic `verify` exit-code contract for CI gating"}],"plan_id":"273a41a194c84e1f","plan_level":"daily","recent_real_commits":[{"author":"merchloubna70-dot","sha":"60aadf01472602c61d719afc92d243b8f4c8c7c3","subject":"Fix #254: [P1][conformance] Pin `verify --explain` and `verify --json` to the single versioned reason-code taxonomy with a cross-surface parity vector (#264)","time":"2026-05-25T11:33:27+08:00"},{"author":"merchloubna70-dot","sha":"d828417e0b358b8c83b382d11c52a1c0ec5b42f6","subject":"Fix #255: [P1][conformance] Bind landed negative canonicalization vectors to stable reason codes (#263)","time":"2026-05-25T11:06:03+08:00"},{"author":"merchloubna70-dot","sha":"8dfcafe4b257f8f8003e584e75d41a996bd2a01c","subject":"Fix #244: [P1][conformance] Bind landed negative canonicalization vectors to stable reason codes (#251)","time":"2026-05-25T04:37:37+08:00"},{"author":"merchloubna70-dot","sha":"460a3c90334d250f69b06cd2518b611a8741cc90","subject":"Fix #236: unify verify reason-code taxonomy","time":"2026-05-25T04:19:00+08:00"},{"author":"merchloubna70-dot","sha":"bb3dd5e1cc4cbbc34a5c19144960652e16582e3f","subject":"Fix #227: [P1][cli] Implement `verify --explain` reason-code rationale output","time":"2026-05-25T02:33:32+08:00"},{"author":"merchloubna70-dot","sha":"921a60a38bd84aa31ac9e3cf8a3621d6a2d51d91","subject":"Fix #228: [P1][test] Close the #173 ↔ #184/#198 negative-conformance vector gap (#233)","time":"2026-05-25T02:05:10+08:00"},{"author":"merchloubna70-dot","sha":"b8164001c4e3145a49e802be6b95b8de6dce8027","subject":"Fix #209: [P1][sdk] Validate proof-bundle `schema_version` with forward-compatible additive rules (#217)","time":"2026-05-24T23:24:53+08:00"},{"author":"merchloubna70-dot","sha":"9c29781eeb25541e196be13e6d79055605f97d12","subject":"Fix #184: [P1][sdk] Land negative conformance vectors mirroring #150 canonicalization edges (#198)","time":"2026-05-24T14:22:28+08:00"},{"author":"merchloubna70-dot","sha":"7dce5fc1f0361f9d6539ef27d875cf08f1f2d5a2","subject":"Fix #172: [P1][verifier] Introduce stable rejection reason-code taxonomy for `verify` failures","time":"2026-05-22T20:07:47+08:00"},{"author":"merchloubna70-dot","sha":"67849e64924722e0523c0ba50653ce70c1fdf9c5","subject":"Fix #137: [P1][sdk] Extend minimum-bundle helper with canonicalization edge-case conformance vectors (#150)","time":"2026-05-22T17:01:14+08:00"}],"schema":"attestplane.plan.v1","schema_version":1}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
