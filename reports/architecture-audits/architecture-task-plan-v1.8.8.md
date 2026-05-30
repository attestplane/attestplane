<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Daily Development Plan for v1.8.8

## Concise Plan

- Keep this daily upgrade diff-level. The v1.8.8 release ships autodev/auto-loop CI stability fixes, version bump, and release artifact generation — all support work. The product increment must come from the Loop 3 active targets: FreeTSA anchoring conformance, exit-code contract hardening for `verify --json`, and taxonomy pinning across the SDK/CLI surface.
- Pin FreeTSA anchoring vectors and add positive/negative conformance coverage for the `free_tsa_anchored_bundle` and `free_tsa_quarantined_bundle` fixture shapes.
- Lock the `verify --json` exit-code contract so that CLI consumers can rely on stable `exit_code`/`error_code` values across minor patches.
- Reference the already-open taxonomy, anchoring, and exit-code issues instead of duplicating their scope.

## P0 Issues

No standalone P0 product task is proposed for this daily plan. The active medium-upgrade anchor (v1.5.0 → v1.10.0) and the architectural boundary work (v1.10.0, then v2.0.0) are tracked in their own milestone planning issues. This daily plan stays at diff level and focuses on incremental product hardening.

## P1 Issues

### ISSUE 1 · \[P1\]\[anchoring\]\[conformance\] Pin FreeTSA anchoring conformance vectors and verifier acceptance

Owner: anchoring/conformance

Affected modules:

- Python SDK anchoring verifier
- FreeTSA anchor vectors (positive + negative)
- Verifier conformance test runner
- TypeScript SDK anchoring verifier

Acceptance criteria:

1. FreeTSA-anchored bundles (happy path) and quarantined bundles (expired/missing certificate chain) are covered by explicit conformance vectors under `tests/conformance/`.
2. The Python and TypeScript verifiers agree on the verification result (`CHAIN_OK` vs `ANCHOR_INVALID` or `ANCHOR_EXPIRED`) for the same fixture.
3. Existing `free_tsa_anchored_bundle.json` and `free_tsa_quarantined_bundle.json` are referenced but not duplicated; new vectors are additive only.
4. The conformance test runner (`tests/conformance/test_anchoring_freetsa.py` or equivalent) passes in both SDK environments.

Validation commands:

- `PYTHONPATH=sdk/python/src python -m pytest tests/conformance -k 'anchoring or freetsa' -q --tb=short`
- `PYTHONPATH=sdk/python/src python -m pytest sdk/python/tests/anchoring -q --tb=short`
- `cd sdk/typescript && npm test -- --runInBand`
- `git diff --check`

Rollout / migration notes:

- FreeTSA is an optional anchoring provider; do not make existing TSA-anchored bundles invalid.
- Keep the current verifier behavior for non-FreeTSA anchors unchanged.

### ISSUE 2 · \[P1\]\[verifier\]\[cli\] Lock the `verify --json` exit-code contract for consumer stability

Owner: verifier/CLI

Affected modules:

- Python CLI `verify_json.py`
- Python verifier result dataclass
- TypeScript verifier result interface
- CLI output schema (`schemas/cli/verify-result-v1.json`)

Acceptance criteria:

1. `verify --json` produces a stable `exit_code` value for each `VerifyErrorCode` (VERIFY_OK, VERIFY_IO_ERROR, VERIFY_REJECTED, etc.) across Python SDK patches and the corresponding TypeScript SDK.
2. The `verify-result-v1.json` CLI output schema documents the `exit_code` field contract, including which values are reserved for future use.
3. Existing human-readable failure strings are not changed.
4. CLI conformance tests in `tests/cli/test_verify_errors.py` remain green without modification.

Validation commands:

- `PYTHONPATH=sdk/python/src python -m pytest tests/cli -q --tb=short`
- `PYTHONPATH=sdk/python/src python -m pytest sdk/python/tests/cli -q --tb=short`
- `cd sdk/typescript && npm test -- --runInBand`
- `git diff --check`

Rollout / migration notes:

- This is a forward-compatible contract lock: do not rename or remove existing `exit_code` values.
- Consumers that switch to the locked contract will not break on future v1.8.x or v1.9.x patches.

## P2 Issues

### ISSUE 3 · \[P2\]\[docs\]\[release\] Document the v1.8.8 user-visible delta and anchoring/exit-code migration guide

Owner: docs/release

Affected modules:

- docs
- validation evidence
- release notes (draft)

Acceptance criteria:

1. Document the FreeTSA anchoring conformance changes and the `verify --json` exit-code contract lock as the v1.8.8 user-visible delta.
2. Include migration notes for CLI consumers who parse `exit_code` from JSON output.
3. Link back to the product P1 issues and the active Loop 3 planning issue.
4. Do not modify `CHANGELOG.md`, release tags, or published packages.

Validation commands:

- `git diff --check`

Rollout / migration notes:

- This is support work only and must not substitute for the product increment.
- Keep wording within the existing claim-safety boundaries.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{
  "anchor_tag": "v1.5.0",
  "consultation_level": "diff",
  "generated_at": "2026-05-30T16:46:00+08:00",
  "head_sha": "7ab7e53abdb51defd702156955188f5303c02bf1",
  "issues": [
    {
      "ordinal": 1,
      "title": "[P1][anchoring][conformance] Pin FreeTSA anchoring conformance vectors and verifier acceptance",
      "priority": "P1",
      "modules": [
        "Python SDK anchoring verifier",
        "FreeTSA anchor vectors (positive + negative)",
        "Verifier conformance test runner",
        "TypeScript SDK anchoring verifier"
      ],
      "acceptance_criteria": [
        "FreeTSA-anchored bundles (happy path) and quarantined bundles (expired/missing certificate chain) are covered by explicit conformance vectors under tests/conformance/.",
        "The Python and TypeScript verifiers agree on the verification result (CHAIN_OK vs ANCHOR_INVALID or ANCHOR_EXPIRED) for the same fixture.",
        "Existing free_tsa_anchored_bundle.json and free_tsa_quarantined_bundle.json are referenced but not duplicated; new vectors are additive only.",
        "The conformance test runner (tests/conformance/test_anchoring_freetsa.py or equivalent) passes in both SDK environments."
      ],
      "validation_commands": [
        "PYTHONPATH=sdk/python/src python -m pytest tests/conformance -k 'anchoring or freetsa' -q --tb=short",
        "PYTHONPATH=sdk/python/src python -m pytest sdk/python/tests/anchoring -q --tb=short",
        "cd sdk/typescript && npm test -- --runInBand",
        "git diff --check"
      ],
      "rollout_notes": "FreeTSA is an optional anchoring provider; do not make existing TSA-anchored bundles invalid. Keep the current verifier behavior for non-FreeTSA anchors unchanged."
    },
    {
      "ordinal": 2,
      "title": "[P1][verifier][cli] Lock the verify --json exit-code contract for consumer stability",
      "priority": "P1",
      "modules": [
        "Python CLI verify_json.py",
        "Python verifier result dataclass",
        "TypeScript verifier result interface",
        "CLI output schema (schemas/cli/verify-result-v1.json)"
      ],
      "acceptance_criteria": [
        "verify --json produces a stable exit_code value for each VerifyErrorCode (VERIFY_OK, VERIFY_IO_ERROR, VERIFY_REJECTED, etc.) across Python SDK patches and the corresponding TypeScript SDK.",
        "The verify-result-v1.json CLI output schema documents the exit_code field contract, including which values are reserved for future use.",
        "Existing human-readable failure strings are not changed.",
        "CLI conformance tests in tests/cli/test_verify_errors.py remain green without modification."
      ],
      "validation_commands": [
        "PYTHONPATH=sdk/python/src python -m pytest tests/cli -q --tb=short",
        "PYTHONPATH=sdk/python/src python -m pytest sdk/python/tests/cli -q --tb=short",
        "cd sdk/typescript && npm test -- --runInBand",
        "git diff --check"
      ],
      "rollout_notes": "This is a forward-compatible contract lock: do not rename or remove existing exit_code values. Consumers that switch to the locked contract will not break on future v1.8.x or v1.9.x patches."
    },
    {
      "ordinal": 3,
      "title": "[P2][docs][release] Document the v1.8.8 user-visible delta and anchoring/exit-code migration guide",
      "priority": "P2",
      "modules": [
        "docs",
        "validation evidence",
        "release notes (draft)"
      ],
      "acceptance_criteria": [
        "Document the FreeTSA anchoring conformance changes and the verify --json exit-code contract lock as the v1.8.8 user-visible delta.",
        "Include migration notes for CLI consumers who parse exit_code from JSON output.",
        "Link back to the product P1 issues and the active Loop 3 planning issue.",
        "Do not modify CHANGELOG.md, release tags, or published packages."
      ],
      "validation_commands": [
        "git diff --check"
      ],
      "rollout_notes": "This is support work only and must not substitute for the product increment. Keep wording within the existing claim-safety boundaries."
    }
  ],
  "milestone_tag": "v1.8.8",
  "plan_id": "plan-v1.8.8-187a4f3e",
  "plan_level": "daily",
  "schema": "attestplane.plan.v1",
  "schema_version": 1
}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
