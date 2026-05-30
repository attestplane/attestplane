<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Daily Development Plan for v1.8.4

## Concise Plan

This is a diff-level daily plan anchored at v1.5.0 with head `a04510c9`.
Since v1.5.0, 113 real commits and 34 release-prep commits have landed.
The v1.8.4 release encompasses the landed `taxonomy_version` cross-surface
parity (Fix #268), `verify --explain` reason-code rationale (Fix #227,
Fix #174), unified reason-code taxonomy (Fix #236), and `schema_version`
forward-compatible additive rules (Fix #156, Fix #272). The release gate
and local runner changes are also included.

Despite the breadth of recent product work, two gaps remain and require
follow-up to make v1.8.4 fully shippable with a stable CI contract:

1. The TypeScript SDK verifier exposes `taxonomy_version` in the result
   struct but has no cross-surface parity test equivalent to the Python
   `test_taxonomy_surface.py` regression. The verify output-contract
   fixture for TypeScript consumers is unpinned.

2. The positive forward-compatible conformance vectors for additive-optional
   fields (Fix #272 SDK validation) exist as fixture bundles but are not
   yet locked into CI output-contract golden fixtures or the conformance
   fixture hash lock.

Product increment is delivered via Issue 1 (taxonomy_version parity
extension to the TypeScript SDK surface) and Issue 2 (conformance vector
and output-contract pinning).

## P0 Issues

No standalone P0 issue is proposed for this daily plan. The active release
gate is already stabilized by commit `2aa72226`. The remaining product gaps
are P1—there is no unaddressed security, compliance, or migration blocker.

## P1 Issues

### ISSUE 1 · [P1][sdk][cli] Add TypeScript SDK cross-surface `taxonomy_version` parity regression and pin the verify output-contract fixture

**Owner:** sdk/typescript + conformance

**Affected modules:**

- TypeScript SDK verifier (`sdk/typescript/src/verifier.ts`)
- TypeScript SDK verify tests (`sdk/typescript/test/`)
- CLI output-contract golden fixtures (`tests/conformance/fixtures/`)
- Fixture-lock maintenance

**Acceptance criteria:**

1. A new TypeScript cross-surface regression test verifies that the SDK
   result `taxonomy_version`, CLI `verify --json` output's `taxonomy_version`,
   and `resolve_verify_taxonomy_version()` return the same value for the
   same proof bundle — mirroring the Python `test_taxonomy_surface.py` contract.
2. The `verify_json_pass.golden` and `verify_json_fail.golden` fixtures in
   `tests/conformance/fixtures/` are updated to reflect the current
   `taxonomy_version` field shape.
3. The existing Python cross-surface test remains unchanged; the TypeScript
   regression is additive only.
4. No existing `error_code`, `reason_code`, or human-readable failure string
   is altered.

**Validation commands:**

- `cd sdk/typescript && npm test -- --runInBand`
- `PYTHONPATH=sdk/python/src pytest tests/conformance/fixtures/ -q --tb=short`
- `PYTHONPATH=sdk/python/src pytest tests/verifier/test_taxonomy_surface.py -q --tb=short`
- `python scripts/conformance/verify_fixture_lock.py`
- `git diff --check`

**Rollout / migration notes:**

- Keep the existing SDK result struct shape; add fields rather than reordering.
- Do not regenerate unrelated fixtures—only update `verify_json_pass.golden`
  and `verify_json_fail.golden` if the current baseline no longer matches.
- Golden fixture updates must be reviewed for semantic correctness, not just
  hash freshness.

### ISSUE 2 · [P1][conformance] Pin forward-compatible additive-optional acceptance vectors and the CI output-contract lock

**Owner:** conformance

**Affected modules:**

- Python conformance vectors (`tests/conformance/schema_version/`)
- Verifier conformance tests (`tests/conformance/`)
- CLI output-contract fixture (`tests/conformance/fixtures/`)
- SDK conformance fixture-hash lock (`sdk/python/tests/conformance/FIXTURE_HASHES.lock`)

**Acceptance criteria:**

1. Add or update the positive forward-compatible conformance vector for
   unknown additive-optional fields at the `chain_metadata`,
   `verification_report`, `framework_mappings`, and `signatures` levels
   (beyond the existing `additive_with_unknown_field_ok` bundle-level test).
2. Verify that `verify --json` and `verify --explain` accept the new vectors
   without false rejection, producing `result=pass` and `reason_code=null`.
3. Pin a stable `verify --json` output-contract fixture for CI consumers
   that includes the `taxonomy_version` field.
4. Keep the existing negative vectors (malformed, unsupported, missing
   required) unchanged.
5. Update `FIXTURE_HASHES.lock` only for intentionally added vectors; do not
   regenerate unrelated fixture hashes.

**Validation commands:**

- `PYTHONPATH=sdk/python/src pytest tests/conformance -k 'negative or forward' -q --tb=short`
- `PYTHONPATH=sdk/python/src pytest tests/conformance/test_schema_version_vectors.py -q --tb=short`
- `PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance/ -q --tb=short`
- `python scripts/conformance/verify_fixture_lock.py`
- `git diff --check`

**Rollout / migration notes:**

- The `FIXTURE_HASHES.lock` update is a single atomic commit;
  regenerate only when new vectors are explicitly added.
- Do not regenerate `canonicalization_golden_fixture.canonical.json` or
  other unrelated golden files.
- New vectors should reference the existing Fix #272 / #156 commit as
  their origin.

## P2 Issues

### ISSUE 3 · [P2][test][release] Expand release-gate product-delta regression coverage

**Owner:** release

**Affected modules:**

- Release gate (`scripts/release/release_gate.py`)
- Release gate tests (`tests/release/test_release_gate.py`)

**Acceptance criteria:**

1. Add regression tests for mixed product + support delta classification.
2. Add a test case for product delta bypass via `ATTESTPLANE_PRODUCT_DELTA_BYPASS`
   environment variable.
3. Add a test case for `VERSION_ONLY_FILES` classification.
4. Add a test case for product delta with `PRODUCT_IMPLEMENTATION_PREFIXES`
   matching (e.g., `sdk/python/src/attestplane/verifier.py`).
5. All existing release gate tests continue to pass.

**Validation commands:**

- `PYTHONPATH=sdk/python/src pytest tests/release/test_release_gate.py -q --tb=short`
- `git diff --check`

**Rollout / migration notes:**

- This is support work only; it must not gate or block the product increment.
- New tests should be added to the existing `test_release_gate.py` file;
  do not create a new test module.

### ISSUE 4 · [P2][docs] Document the v1.8.4 user-visible delta and claim-safety boundary

**Owner:** docs

**Affected modules:**

- `docs/release-notes/v1.8.4.draft.md`
- Validation evidence under `docs/validation/`

**Acceptance criteria:**

1. Complete `docs/release-notes/v1.8.4.draft.md` with the user-visible delta
   covering: unified reason-code taxonomy, `verify --explain` / `--json`
   output, `schema_version` forward-compatible additive rules, negative
   conformance vectors, `taxonomy_version` cross-surface parity, and local
   runner improvements.
2. Record the release gate stabilization fix (commit `2aa72226`) context.
3. Keep wording within existing claim-safety boundaries; do not touch
   `CHANGELOG.md`.
4. Markdown-link-check passes on changed documentation files.

**Validation commands:**

- `markdown-link-check docs/release-notes/v1.8.4.draft.md`
- `git diff --check`

**Rollout / migration notes:**

- This is support work only and must not become a substitute for the product
   increment.
- Do not modify release tags, publish artifacts, or weaken gates.
- Do not modify `CHANGELOG.md` or `.github/workflows/`.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{
  "anchor_tag": "v1.5.0",
  "consultation_level": "diff",
  "head_sha": "a04510c97ce41c1528b1732c3b072a0e74623341",
  "milestone_tag": "v1.8.4",
  "plan_level": "daily",
  "schema": "attestplane.plan.v1",
  "schema_version": 1,
  "issues": [
    {
      "ordinal": 1,
      "priority": "P1",
      "title": "[P1][sdk][cli] Add TypeScript SDK cross-surface taxonomy_version parity regression and pin the verify output-contract fixture",
      "modules": [
        "TypeScript SDK verifier",
        "TypeScript SDK verify tests",
        "CLI output-contract golden fixtures",
        "Fixture-lock maintenance"
      ],
      "acceptance_criteria": [
        "A new TypeScript cross-surface regression test verifies that SDK result taxonomy_version, CLI verify --json taxonomy_version, and resolve_verify_taxonomy_version() return the same value for the same proof bundle.",
        "The verify_json_pass.golden and verify_json_fail.golden fixtures are updated to reflect the current taxonomy_version field shape.",
        "The existing Python cross-surface test remains unchanged; the TypeScript regression is additive only.",
        "No existing error_code, reason_code, or human-readable failure string is altered."
      ],
      "validation_commands": [
        "cd sdk/typescript && npm test -- --runInBand",
        "PYTHONPATH=sdk/python/src pytest tests/conformance/fixtures/ -q --tb=short",
        "PYTHONPATH=sdk/python/src pytest tests/verifier/test_taxonomy_surface.py -q --tb=short",
        "python scripts/conformance/verify_fixture_lock.py",
        "git diff --check"
      ],
      "rollout_notes": "Keep the existing SDK result struct shape; add fields rather than reordering. Do not regenerate unrelated fixtures."
    },
    {
      "ordinal": 2,
      "priority": "P1",
      "title": "[P1][conformance] Pin forward-compatible additive-optional acceptance vectors and the CI output-contract lock",
      "modules": [
        "Python conformance vectors",
        "Verifier conformance tests",
        "CLI output-contract fixture",
        "SDK conformance fixture-hash lock"
      ],
      "acceptance_criteria": [
        "Add or update the positive forward-compatible conformance vector for unknown additive-optional fields at chain_metadata, verification_report, framework_mappings, and signatures levels.",
        "Verify that verify --json and verify --explain accept the new vectors without false rejection.",
        "Pin a stable verify --json output-contract fixture for CI consumers that includes the taxonomy_version field.",
        "Keep the existing negative vectors unchanged.",
        "Update FIXTURE_HASHES.lock only for intentionally added vectors."
      ],
      "validation_commands": [
        "PYTHONPATH=sdk/python/src pytest tests/conformance -k 'negative or forward' -q --tb=short",
        "PYTHONPATH=sdk/python/src pytest tests/conformance/test_schema_version_vectors.py -q --tb=short",
        "PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance/ -q --tb=short",
        "python scripts/conformance/verify_fixture_lock.py",
        "git diff --check"
      ],
      "rollout_notes": "FIXTURE_HASHES.lock update is a single atomic commit. Do not regenerate unrelated golden files."
    },
    {
      "ordinal": 3,
      "priority": "P2",
      "title": "[P2][test][release] Expand release-gate product-delta regression coverage",
      "modules": [
        "Release gate script",
        "Release gate tests"
      ],
      "acceptance_criteria": [
        "Add regression tests for mixed product + support delta classification.",
        "Add a test case for product delta bypass via ATTESTPLANE_PRODUCT_DELTA_BYPASS.",
        "Add a test case for VERSION_ONLY_FILES classification.",
        "Add a test case for PRODUCT_IMPLEMENTATION_PREFIXES matching.",
        "All existing release gate tests continue to pass."
      ],
      "validation_commands": [
        "PYTHONPATH=sdk/python/src pytest tests/release/test_release_gate.py -q --tb=short",
        "git diff --check"
      ],
      "rollout_notes": "Support work only. New tests must not gate or block the product increment."
    },
    {
      "ordinal": 4,
      "priority": "P2",
      "title": "[P2][docs] Document the v1.8.4 user-visible delta and claim-safety boundary",
      "modules": [
        "docs",
        "validation evidence"
      ],
      "acceptance_criteria": [
        "Complete docs/release-notes/v1.8.4.draft.md with the user-visible delta covering all landed features.",
        "Record the release gate stabilization fix context.",
        "Keep wording within existing claim-safety boundaries; do not touch CHANGELOG.md.",
        "Markdown-link-check passes on changed documentation files."
      ],
      "validation_commands": [
        "markdown-link-check docs/release-notes/v1.8.4.draft.md",
        "git diff --check"
      ],
      "rollout_notes": "Support work only. Do not modify release tags, publish artifacts, or weaken gates."
    }
  ]
}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
