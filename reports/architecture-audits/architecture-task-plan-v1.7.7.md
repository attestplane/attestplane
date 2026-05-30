<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Daily Development Plan for v1.7.7

## Concise Plan

- Keep this daily upgrade diff-level. The last product commit before v1.7.7
  (#209, `b8164001`) added forward-compatible additive `schema_version` validation
  with positive/negative fixture bundles under `tests/conformance/schema_version/`.
  These fixtures currently only run as pytest tests; extend the standalone
  conformance runner (`python -m attestplane.conformance.run`) to replay the
  schema_version vectors so CI can gate on the additive-optional boundary
  without the full pytest suite.
- Publish a small docs/update task that records the v1.7.7 user-visible delta
  (schema_version conformance runner integration plus the #209 surface) and
  cross-references the existing conformance documentation, without changing
  `CHANGELOG.md` or any release workflow.
- No P0 issues are proposed; the existing active release train handles the
  stable cut without a new claim-safety blocker.

## P0 Issues

No standalone P0 product task is proposed for this daily plan. The v1.7.7
release cut is a suffix-free stable package through the existing autodev
release workflow; no active claim-safety blocker remains unaddressed.

## P1 Issues

### ISSUE 1 · \[P1\]\[conformance\] Wire schema_version forward-compatible vectors into the standalone conformance runner

**Owner:** conformance

**Affected modules:**

- Python conformance runner (`sdk/python/src/attestplane/conformance/run.py`)
- Schema_version conformance vectors (`tests/conformance/schema_version/`)
- Fixture-lock maintenance

**Acceptance criteria:**

1. Extend `python -m attestplane.conformance.run` with a `--schema-version`
   flag that replays all schema_version vectors from `vectors.json` and asserts
   that each bundle produces the `expected_reason_code` (or `None` for pass
   cases).
2. The runner exits 0 when all schema_version vectors match their expected
   outcomes, and exits 1 with a diagnostic line per mismatch.
3. The existing pytest tests (`test_schema_version_vectors.py`) remain as the
   detailed unit test; the new runner path is a lightweight CI gate.
4. The additive-optional fixtures (`additive_minor_ok`,
   `additive_with_unknown_field_ok`) must verify as valid, and the negative
   fixtures (`missing`, `unknown_major`, `major_version_ahead`,
   `unknown_required_field`) must reject with the expected reason codes.
5. Backward compatibility: the existing `--negative` flag behavior is unchanged.

**Validation commands:**

- `PYTHONPATH=sdk/python/src python -m attestplane.conformance.run --schema-version`
- `PYTHONPATH=sdk/python/src pytest tests/conformance/test_schema_version_vectors.py -q`
- `python -m ruff check sdk/python/src/attestplane/conformance/run.py`
- `git diff --check`

**Rollout / migration notes:**

- The runner flag is additive; existing CI scripts that only call `--negative`
  are unaffected.
- The conformance README at `tests/conformance/README.md` should list the new
  `--schema-version` flag alongside `--negative`.

## P2 Issues

### ISSUE 2 · \[P2\]\[docs\]\[release\] Document the v1.7.7 user-visible delta with schema_version surface

**Owner:** docs/release

**Affected modules:**

- `docs/release-notes/v1.7.7.draft.md`
- `docs/release-notes/v1.7.x-delta.md` (if not already capturing the #209 surface)
- Conformance cross-reference

**Acceptance criteria:**

1. Update `v1.7.7.draft.md` to include the schema_version conformance runner
   integration and cross-reference the vector fixture set.
2. Update `v1.7.x-delta.md` if the #209 schema_version additive-optional
   surface is not already documented in the existing delta.
3. Record the conformance fixture lock path so release integrators can verify
   the gate locally.
4. Keep wording within the existing claim-safety boundaries and do not touch
   `CHANGELOG.md`.

**Validation commands:**

- `markdown-link-check docs/release-notes/v1.7.7.draft.md docs/release-notes/v1.7.x-delta.md`
- `git diff --check`

**Rollout / migration notes:**

- This is support work only and must not become a substitute for the product
  increment in Issue 1.
- Do not modify release tags, publish artifacts, or weaken gates.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{
  "anchor_tag": "v1.5.0",
  "consultation_level": "diff",
  "head_sha": "8208410f9f57548a26be80eb1e3270f573dafe04",
  "issues": [
    {
      "ordinal": 1,
      "priority": "P1",
      "title": "[P1][conformance] Wire schema_version forward-compatible vectors into the standalone conformance runner",
      "modules": [
        "Python conformance runner",
        "Schema_version conformance vectors",
        "Fixture-lock maintenance"
      ],
      "acceptance_criteria": [
        "Extend `python -m attestplane.conformance.run` with a `--schema-version` flag that replays all schema_version vectors from `vectors.json` and asserts that each bundle produces the expected_reason_code (or None for pass cases).",
        "The runner exits 0 when all schema_version vectors match their expected outcomes, and exits 1 with a diagnostic line per mismatch.",
        "The existing pytest tests (test_schema_version_vectors.py) remain as the detailed unit test; the new runner path is a lightweight CI gate.",
        "The additive-optional fixtures (additive_minor_ok, additive_with_unknown_field_ok) must verify as valid, and the negative fixtures (missing, unknown_major, major_version_ahead, unknown_required_field) must reject with the expected reason codes.",
        "Backward compatibility: the existing --negative flag behavior is unchanged."
      ],
      "validation_commands": [
        "PYTHONPATH=sdk/python/src python -m attestplane.conformance.run --schema-version",
        "PYTHONPATH=sdk/python/src pytest tests/conformance/test_schema_version_vectors.py -q",
        "python -m ruff check sdk/python/src/attestplane/conformance/run.py",
        "git diff --check"
      ],
      "rollout_notes": "The runner flag is additive; existing CI scripts that only call --negative are unaffected. The conformance README at tests/conformance/README.md should list the new --schema-version flag alongside --negative."
    },
    {
      "ordinal": 2,
      "priority": "P2",
      "title": "[P2][docs][release] Document the v1.7.7 user-visible delta with schema_version surface",
      "modules": [
        "docs/release-notes/v1.7.7.draft.md",
        "docs/release-notes/v1.7.x-delta.md",
        "Conformance cross-reference"
      ],
      "acceptance_criteria": [
        "Update v1.7.7.draft.md to include the schema_version conformance runner integration and cross-reference the vector fixture set.",
        "Update v1.7.x-delta.md if the #209 schema_version additive-optional surface is not already documented in the existing delta.",
        "Record the conformance fixture lock path so release integrators can verify the gate locally.",
        "Keep wording within the existing claim-safety boundaries and do not touch CHANGELOG.md."
      ],
      "validation_commands": [
        "markdown-link-check docs/release-notes/v1.7.7.draft.md docs/release-notes/v1.7.x-delta.md",
        "git diff --check"
      ],
      "rollout_notes": "This is support work only and must not become a substitute for the product increment in Issue 1. Do not modify release tags, publish artifacts, or weaken gates."
    }
  ],
  "milestone_tag": "v1.7.7",
  "plan_level": "daily",
  "schema": "attestplane.plan.v1",
  "schema_version": 1
}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
