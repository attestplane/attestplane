<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Daily Development Plan for v1.8.2

## Concise Plan

- The v1.8.2 release shipped three product changes: `verify --explain`, `taxonomy_version` parity, and negative canonicalization vectors bound to reason codes. The diff-level gap audit (architecture-gap-audit-v1.8.2.md) identifies four remaining gaps: TS SDK CLI absence, schema_version forward-compatible conformance gate, conformance fixture-lock automation, and v1.8.x delta documentation.
- Pin the forward-compatible `schema_version` additive-optional conformance gate as the P0 product increment — the logic landed in Fix #209 but the positive acceptance vector is not locked in CI, creating a regression risk.
- Surface reason-code taxonomy in the TypeScript SDK `BundleVerificationResult` (cross-SDK parity — Python exposes it through `--explain` and `result.reason_codes`; TS has the type but not the wire-up).
- Publish a small docs task that consolidates the v1.8.x user-visible delta into a single reference document, without modifying `CHANGELOG.md` or any release workflow.
- Reference the already-open taxonomy/version and conformance issues instead of duplicating their scope.
- Autodev infrastructure, CI, runner, and observability work remains support-only and is not proposed as product tasks in this plan.

## P0 Issues

### ISSUE 1 · \[P0\]\[conformance\]\[verifier\] Pin `schema_version` forward-compatible additive-optional acceptance in CI conformance gate

Owner: conformance / verifier

Affected modules:

- Python conformance vectors (`sdk/python/tests/conformance/`)
- Verifier negative/positive vector fixtures (`fixtures/conformance/`)
- CI conformance gate configuration
- Scripts (`scripts/conformance/verify_fixture_lock.py`)

Acceptance criteria:

1. A positive forward-compatible vector exists that passes `verify_metadata_closure()` with an unknown additive-optional field under `schema_version` (e.g. `"schema_version": {"base": 1, "extensions": {"future_optional_key": "value"}}`).
2. The existing negative vector for unknown-required-field rejection under `schema_version` remains unchanged and continues to reject.
3. CI blocks on conformance fixture-lock drift: the `verify_fixture_lock.py` script (or equivalent) runs in CI and fails if locked fixture hashes diverge from the on-disk state.
4. The new vector is linked back to the already-closed Fix #209 and does not duplicate its scope.

Validation commands:

- `PYTHONPATH=sdk/python/src pytest tests/conformance -k 'schema_version or forward' -q`
- `PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance -k 'schema_version or forward' -q`
- `python scripts/conformance/verify_fixture_lock.py`
- `git diff --check`

Rollout / migration notes:

- This is solely a conformance-gate change. No verifier runtime logic is being modified.
- Update locked fixture hashes only if the new vector is intentionally added. Do not regenerate unrelated fixtures.
- Do not modify `CHANGELOG.md` or release workflow files.

## P1 Issues

### ISSUE 2 · \[P1\]\[sdk\]\[typescript\] Surface `reasonCode` taxonomy in TypeScript `BundleVerificationResult`

Owner: TypeScript SDK

Affected modules:

- TypeScript SDK verifier (`sdk/typescript/src/verifier.ts`)
- TypeScript SDK result types (`sdk/typescript/src/types.ts`)
- Cross-SDK conformance vectors for reason-code parity
- SDK tests

Acceptance criteria:

1. The TypeScript `BundleVerificationResult` type carries a typed `reasonCodes` field (mirroring the Python SDK's `BundleVerificationResult.reason_codes`) containing the stable `VerifyReasonCodeV1` values for each rejection path.
2. Every rejection path in the TS verifier that produces a reason code populates `reasonCodes` in the result object.
3. Existing Python→TypeScript conformance vectors for reason-code parity pass without modification.
4. `VerifyErrorCode` behavior and human-readable error strings are not changed.

Validation commands:

- `cd sdk/typescript && npm test -- --runInBand 2>&1 | tail -30`
- `PYTHONPATH=sdk/python/src pytest tests/conformance -k 'reason_code or parity' -q`
- `cd sdk/typescript && npx tsc --noEmit`
- `git diff --check`

Rollout / migration notes:

- Keep existing TS SDK error fields stable during the migration window.
- Do not rename or remove `VerifyErrorCode` constants.
- The `reasonCodes` field is additive — consumers that do not read it are unaffected.

### ISSUE 3 · \[P1\]\[conformance\] Bind conformance fixture-lock automation into CI blocking path

Owner: conformance / CI

Affected modules:

- `scripts/conformance/verify_fixture_lock.py`
- CI gate configuration
- Fixture-lock maintenance

Acceptance criteria:

1. The `verify_fixture_lock.py` script exits non-zero when on-disk fixture hashes do not match the locked `SCHEMA_HASHES.lock`.
2. The check runs as a blocking step in CI on every PR that touches `fixtures/` or `sdk/python/tests/conformance/`.
3. The script does not block unrelated PRs (no fixture change → no lock check).
4. The existing lock file is accurate for the current state of fixtures.

Validation commands:

- `python scripts/conformance/verify_fixture_lock.py`
- `git diff --check`

Rollout / migration notes:

- This is a safety gate, not a product change. It documents conformance stability alongside the P0 conformance gate.
- Do not modify `.github/workflows/` files — use `autodev` issue-driven CI edits if workflow changes are needed.
- Do not modify `CHANGELOG.md`.

## P2 Issues

### ISSUE 4 · \[P2\]\[docs\]\[release\] Consolidate v1.8.x user-visible delta into a single reference document

Owner: docs / release

Affected modules:

- docs
- validation evidence

Acceptance criteria:

1. A consolidated `docs/release-notes/v1.8.x-delta.md` document captures the user-visible changes since v1.7.x: `verify --explain`, taxonomy version stability, reason-code taxonomy finalization, negative canonicalization vectors bound to reason codes.
2. The document does not duplicate existing issue-tracker content or `CHANGELOG.md`.
3. All links are valid and references are within the existing claim-safety boundaries.
4. The wording does not imply EU AI Act compliance, GDPR compliance, or GA/production readiness.

Validation commands:

- `markdown-link-check docs/release-notes/v1.8.x-delta.md`
- `git diff --check`

Rollout / migration notes:

- This is support work only and must not become a substitute for the product increment.
- Do not modify release tags, publish artifacts, or weaken gates.
- Do not modify `CHANGELOG.md`.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{
  "schema": "attestplane.plan.v1",
  "schema_version": 1,
  "anchor_tag": "v1.5.0",
  "consultation_level": "diff",
  "head_sha": "7b9bdb7f374e4d05d21cdf28cf5b7199d6e7f02a",
  "milestone_tag": "v1.8.2",
  "plan_level": "daily",
  "issues": [
    {
      "ordinal": 1,
      "priority": "P0",
      "title": "[P0][conformance][verifier] Pin `schema_version` forward-compatible additive-optional acceptance in CI conformance gate",
      "modules": [
        "Python conformance vectors",
        "Verifier fixture vectors",
        "CI conformance gate configuration",
        "verify_fixture_lock.py script"
      ],
      "acceptance_criteria": [
        "A positive forward-compatible vector exists that passes `verify_metadata_closure()` with an unknown additive-optional field under `schema_version`.",
        "The existing negative vector for unknown-required-field rejection under `schema_version` remains unchanged and continues to reject.",
        "CI blocks on conformance fixture-lock drift when locked fixture hashes diverge from the on-disk state.",
        "The new vector is linked back to the already-closed Fix #209 and does not duplicate its scope."
      ],
      "validation_commands": [
        "PYTHONPATH=sdk/python/src pytest tests/conformance -k 'schema_version or forward' -q",
        "PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance -k 'schema_version or forward' -q",
        "python scripts/conformance/verify_fixture_lock.py",
        "git diff --check"
      ],
      "rollout_notes": "This is solely a conformance-gate change. No verifier runtime logic is being modified. Update locked fixture hashes only if the new vector is intentionally added. Do not regenerate unrelated fixtures. Do not modify CHANGELOG.md or release workflow files."
    },
    {
      "ordinal": 2,
      "priority": "P1",
      "title": "[P1][sdk][typescript] Surface `reasonCode` taxonomy in TypeScript `BundleVerificationResult`",
      "modules": [
        "TypeScript SDK verifier",
        "TypeScript SDK result types",
        "Cross-SDK conformance vectors",
        "SDK tests"
      ],
      "acceptance_criteria": [
        "The TypeScript `BundleVerificationResult` type carries a typed `reasonCodes` field mirroring the Python SDK's `BundleVerificationResult.reason_codes`.",
        "Every rejection path in the TS verifier that produces a reason code populates `reasonCodes` in the result object.",
        "Existing Python to TypeScript conformance vectors for reason-code parity pass without modification.",
        "`VerifyErrorCode` behavior and human-readable error strings are not changed."
      ],
      "validation_commands": [
        "cd sdk/typescript && npm test -- --runInBand 2>&1 | tail -30",
        "PYTHONPATH=sdk/python/src pytest tests/conformance -k 'reason_code or parity' -q",
        "cd sdk/typescript && npx tsc --noEmit",
        "git diff --check"
      ],
      "rollout_notes": "Keep existing TS SDK error fields stable during the migration window. Do not rename or remove VerifyErrorCode constants. The reasonCodes field is additive — consumers that do not read it are unaffected."
    },
    {
      "ordinal": 3,
      "priority": "P1",
      "title": "[P1][conformance] Bind conformance fixture-lock automation into CI blocking path",
      "modules": [
        "scripts/conformance/verify_fixture_lock.py",
        "CI gate configuration",
        "Fixture-lock maintenance"
      ],
      "acceptance_criteria": [
        "The verify_fixture_lock.py script exits non-zero when on-disk fixture hashes do not match the locked SCHEMA_HASHES.lock.",
        "The check runs as a blocking step in CI on every PR that touches fixtures/ or sdk/python/tests/conformance/.",
        "The script does not block unrelated PRs (no fixture change -> no lock check).",
        "The existing lock file is accurate for the current state of fixtures."
      ],
      "validation_commands": [
        "python scripts/conformance/verify_fixture_lock.py",
        "git diff --check"
      ],
      "rollout_notes": "This is a safety gate, not a product change. Do not modify .github/workflows/ files — use autodev issue-driven CI edits if workflow changes are needed. Do not modify CHANGELOG.md."
    },
    {
      "ordinal": 4,
      "priority": "P2",
      "title": "[P2][docs][release] Consolidate v1.8.x user-visible delta into a single reference document",
      "modules": [
        "docs",
        "validation evidence"
      ],
      "acceptance_criteria": [
        "A consolidated docs/release-notes/v1.8.x-delta.md document captures the user-visible changes since v1.7.x: verify --explain, taxonomy version stability, reason-code taxonomy finalization, negative canonicalization vectors bound to reason codes.",
        "The document does not duplicate existing issue-tracker content or CHANGELOG.md.",
        "All links are valid and references are within the existing claim-safety boundaries.",
        "The wording does not imply EU AI Act compliance, GDPR compliance, or GA/production readiness."
      ],
      "validation_commands": [
        "markdown-link-check docs/release-notes/v1.8.x-delta.md",
        "git diff --check"
      ],
      "rollout_notes": "This is support work only and must not become a substitute for the product increment. Do not modify release tags, publish artifacts, or weaken gates. Do not modify CHANGELOG.md."
    }
  ]
}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
