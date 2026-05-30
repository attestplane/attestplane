<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Daily Development Plan for v1.7.8

## Concise Plan

- This daily upgrade stays on a diff-level plan and focuses the product increment on closing
  the remaining `reason_code` / `taxonomy_version` / `anchoring` parity gap between the
  `verify --json` output and the `verify-result-v1.json` schema, which was introduced by
  the `verify --json` CI-gating surface (Fix #220).
- Add the stable `VERIFY_REASON_TAXONOMY_VERSION` constant and `resolve_verify_taxonomy_version()` /
  `format_verify_taxonomy_version()` helpers to the verify reason-code module so every
  consumer-facing output path draws the same taxonomy version.
- Extend `BundleVerificationResult` with `primary_reason` and `secondary_reasons` fields so
  the JSON serialization path can populate the top-level `reason_code` without changing
  existing `error_code` behavior or human-readable failure strings.
- Pin a golden fixture for `verify --json` output to lock the CI-consumer contract.
- Update the v1.7.x user-visible delta docs to record the new fields and migration notes,
  without touching `CHANGELOG.md` or any release workflow.

## P0 Issues

### ISSUE 1 · \[P0\]\[verifier\]\[cli\] Close the `reason_code` / `taxonomy_version` / `anchoring` gap in verify --json output

Owner: verifier/CLI

Affected modules:

- Python SDK verifier
- Python CLI verify_json module
- verify-result-v1 JSON schema consumer

Acceptance criteria:

1. `verify --json` output payload includes **all** fields required by
   `schemas/cli/verify-result-v1.json`: `reason_code` (null on pass,
   `att.verify.*` string on failure), `taxonomy_version` (integer 1),
   and `anchoring` (object with `status` and `quarantined` booleans).
2. The `reason_code` field on a failure path mirrors `BundleVerificationResult.primary_reason`.
3. `taxonomy_version` is drawn from the shared `resolve_verify_taxonomy_version()` constant
   so that the CLI, SDK, and docs all agree on the same taxonomy version.
4. `anchoring.status` reflects the `BundleVerificationResult.anchoring_status` value
   ("verified" / "quarantined" / "absent") and `anchoring.quarantined` reflects
   `BundleVerificationResult.anchoring_quarantined`.
5. Existing `error_code`, `exit_code`, and human-readable `stderr_code` behavior is unchanged.
6. The golden fixture `fixtures/conformance/golden/verify_json_v1.7.8.json` is created and
   validated against the schema.

Validation commands:

- `PYTHONPATH=sdk/python/src python -c "from attestplane.cli.verify_json import build_verify_json_outcome; from pathlib import Path; o = build_verify_json_outcome(Path('fixtures/conformance/baseline.att'), require_non_empty=False, require_signed_attestation=False, explain=False); import json, jsonschema; jsonschema.validate(o.payload, json.loads(open('schemas/cli/verify-result-v1.json').read()))"`
- `PYTHONPATH=sdk/python/src pytest tests/cli/test_verify_json_contract.py -q --tb=short`
- `PYTHONPATH=sdk/python/src pytest tests/conformance/test_verify_json_schema.py -q --tb=short`
- `python scripts/conformance/verify_fixture_lock.py`
- `git diff --check`

Rollout / migration notes:

- The new fields are additive-only: no existing field is renamed or removed.
- Downstream CI consumers that parse `reasons[]` and `exit_code` are unaffected.
- Consumers switching from `reasons[]`-only to the top-level `reason_code` shortcut
  must handle `null` (pass) and `att.verify.*` (failure).

## P1 Issues

### ISSUE 2 · \[P1\]\[sdk\] Add `VERIFY_REASON_TAXONOMY_VERSION` and taxonomy helpers to verify_reason_codes

Owner: SDK

Affected modules:

- `sdk/python/src/attestplane/verify_reason_codes.py`
- `sdk/python/src/attestplane/__init__.py` (re-export surface)
- TypeScript SDK parity (if applicable)

Acceptance criteria:

1. `VERIFY_REASON_TAXONOMY_VERSION` constant is exported from `verify_reason_codes`
   with value `1`.
2. `resolve_verify_taxonomy_version() -> int` returns the canonical taxonomy version.
3. `format_verify_taxonomy_version(value: int | None = None) -> str` renders it for
   human-facing text output.
4. All three are re-exported from the top-level `attestplane.__init__` `__all__` list.
5. `is_known_verify_reason_code()`, `verify_reason_code_matches_format()`, and
   `verify_reason_code_explanation()` are unchanged.
6. Existing `VERIFY_REASON_CODE_SCHEMA_VERSION` is preserved and **not** renamed.

Validation commands:

- `PYTHONPATH=sdk/python/src python -c "from attestplane.verify_reason_codes import VERIFY_REASON_TAXONOMY_VERSION, resolve_verify_taxonomy_version, format_verify_taxonomy_version; assert VERIFY_REASON_TAXONOMY_VERSION == 1; assert resolve_verify_taxonomy_version() == 1; assert format_verify_taxonomy_version() == '1'"`
- `PYTHONPATH=sdk/python/src python -c "from attestplane import VERIFY_REASON_TAXONOMY_VERSION, resolve_verify_taxonomy_version, format_verify_taxonomy_version"`
- `PYTHONPATH=sdk/python/src pytest tests/verifier -k 'reason_code or taxonomy' -q --tb=short`
- `git diff --check`

Rollout / migration notes:

- This is a pure additive export: no existing function is changed or deprecated.
- The TypeScript SDK parity should be tracked separately as a follow-up if the
  taxonomy helpers are not yet ported.

### ISSUE 3 · \[P1\]\[conformance\] Create golden fixture and schema validation for verify --json output

Owner: conformance

Affected modules:

- `fixtures/conformance/golden/verify_json_v1.7.8.json` (new)
- `tests/conformance/test_verify_json_schema.py`
- `schemas/cli/verify-result-v1.json` (no change needed, used as validator)

Acceptance criteria:

1. A golden fixture is added for a pass-case `verify --json` output, validated
   against the `verify-result-v1.json` schema.
2. A golden fixture is added for a fail-case (canonicalization-edge) output,
   validated against the same schema.
3. `test_verify_json_schema.py` fixtures are updated to include the v1.7.8
   golden fixtures and assert they validate successfully.
4. Negative fixtures (malformed output) continue to be rejected by the schema.
5. Existing conformance tests are not broken.

Validation commands:

- `PYTHONPATH=sdk/python/src pytest tests/conformance/test_verify_json_schema.py -q --tb=short`
- `python scripts/conformance/verify_fixture_lock.py`
- `git diff --check`

Rollout / migration notes:

- Golden fixture hashes are locked; regeneration requires an intentional
  update to the fixture file and lock.
- Do not regenerate unrelated conformance fixtures.

## P2 Issues

### ISSUE 4 · \[P2\]\[docs\] Update v1.7.x user-visible delta with `reason_code` / `taxonomy_version` / `anchoring` surface

Owner: docs/release

Affected modules:

- `docs/release-notes/v1.7.x-delta.md`
- `docs/cli/verify-json.md` (if CLI docs reference the output shape)

Acceptance criteria:

1. `docs/release-notes/v1.7.x-delta.md` documents the new `reason_code`,
   `taxonomy_version`, and `anchoring` fields in the `verify --json` output.
2. The relationship between `verify --json` payload fields and the
   `schemas/cli/verify-result-v1.json` schema is described.
3. The migration note for CI consumers is updated: consumers may now branch
   on `.reason_code` (null / `att.verify.*`) in addition to the exit code.
4. No changes are made to `CHANGELOG.md`, release tags, or published packages.
5. `markdown-link-check docs/**/*.md` passes.

Validation commands:

- `markdown-link-check docs/release-notes/v1.7.x-delta.md docs/cli/verify-json.md`
- `git diff --check`

Rollout / migration notes:

- This is support work only and must not become a substitute for the product increment.
- Do not modify release tags, publish artifacts, or weaken gates.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{
  "anchor_tag": "v1.5.0",
  "consultation_level": "diff",
  "head_sha": "c9eb7c845211ea799a33f07450e358da45495a6d",
  "issues": [
    {
      "acceptance_criteria": [
        "verify --json output payload includes all fields required by schemas/cli/verify-result-v1.json: reason_code, taxonomy_version, and anchoring",
        "reason_code on failure mirrors BundleVerificationResult.primary_reason",
        "taxonomy_version is drawn from resolve_verify_taxonomy_version()",
        "anchoring.status reflects BundleVerificationResult.anchoring_status and anchoring.quarantined reflects anchoring_quarantined",
        "Existing error_code, exit_code, and stderr_code behavior is unchanged",
        "Golden fixture fixtures/conformance/golden/verify_json_v1.7.8.json created and validated"
      ],
      "modules": [
        "Python SDK verifier",
        "Python CLI verify_json module",
        "verify-result-v1 JSON schema"
      ],
      "ordinal": 1,
      "priority": "P0",
      "rollout_notes": "Additive-only: no existing field is renamed or removed. Downstream CI consumers that parse reasons[] and exit_code are unaffected.",
      "title": "[P0][verifier][cli] Close the reason_code / taxonomy_version / anchoring gap in verify --json output",
      "validation_commands": [
        "PYTHONPATH=sdk/python/src pytest tests/cli/test_verify_json_contract.py -q --tb=short",
        "PYTHONPATH=sdk/python/src pytest tests/conformance/test_verify_json_schema.py -q --tb=short",
        "python scripts/conformance/verify_fixture_lock.py",
        "git diff --check"
      ]
    },
    {
      "acceptance_criteria": [
        "VERIFY_REASON_TAXONOMY_VERSION constant exported with value 1",
        "resolve_verify_taxonomy_version() -> int returns canonical taxonomy version",
        "format_verify_taxonomy_version(value: int | None = None) -> str renders for text output",
        "All three re-exported from attestplane.__init__ __all__ list",
        "Existing functions unchanged"
      ],
      "modules": [
        "sdk/python/src/attestplane/verify_reason_codes.py",
        "sdk/python/src/attestplane/__init__.py"
      ],
      "ordinal": 2,
      "priority": "P1",
      "rollout_notes": "Pure additive export. No existing function is changed or deprecated.",
      "title": "[P1][sdk] Add VERIFY_REASON_TAXONOMY_VERSION and taxonomy helpers to verify_reason_codes",
      "validation_commands": [
        "PYTHONPATH=sdk/python/src python -c \"from attestplane import VERIFY_REASON_TAXONOMY_VERSION\"",
        "PYTHONPATH=sdk/python/src pytest tests/verifier -k 'reason_code or taxonomy' -q --tb=short",
        "git diff --check"
      ]
    },
    {
      "acceptance_criteria": [
        "Golden fixture for pass-case verify --json output validated against verify-result-v1.json schema",
        "Golden fixture for fail-case (canonicalization-edge) validated against schema",
        "test_verify_json_schema.py fixtures updated to include v1.7.8 golden fixtures",
        "Negative fixtures continue to reject",
        "Existing conformance tests not broken"
      ],
      "modules": [
        "fixtures/conformance/golden/",
        "tests/conformance/test_verify_json_schema.py"
      ],
      "ordinal": 3,
      "priority": "P1",
      "rollout_notes": "Golden fixture hashes are locked; regeneration requires intentional update to fixture file and lock.",
      "title": "[P1][conformance] Create golden fixture and schema validation for verify --json output",
      "validation_commands": [
        "PYTHONPATH=sdk/python/src pytest tests/conformance/test_verify_json_schema.py -q --tb=short",
        "python scripts/conformance/verify_fixture_lock.py",
        "git diff --check"
      ]
    },
    {
      "acceptance_criteria": [
        "docs/release-notes/v1.7.x-delta.md documents the new reason_code, taxonomy_version, and anchoring fields",
        "Relationship between verify --json payload and verify-result-v1.json schema described",
        "Migration note updated: consumers may branch on .reason_code in addition to exit code",
        "No changes to CHANGELOG.md, release tags, or published packages",
        "markdown-link-check passes"
      ],
      "modules": [
        "docs/release-notes/v1.7.x-delta.md",
        "docs/cli/verify-json.md"
      ],
      "ordinal": 4,
      "priority": "P2",
      "rollout_notes": "Support work only. Must not become a substitute for the product increment. Do not modify release tags or publish artifacts.",
      "title": "[P2][docs] Update v1.7.x user-visible delta with reason_code / taxonomy_version / anchoring surface",
      "validation_commands": [
        "markdown-link-check docs/release-notes/v1.7.x-delta.md docs/cli/verify-json.md",
        "git diff --check"
      ]
    }
  ],
  "milestone_tag": "v1.7.8",
  "plan_level": "daily",
  "schema": "attestplane.plan.v1",
  "schema_version": 1
}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
