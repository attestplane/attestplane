<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Daily Development Plan for v1.7.5

## Concise Plan

- Keep this daily small-upgrade diff-level, anchored at `v1.5.0` with 63 real
  commits and 18 stable releases accumulated since the anchor.
- The main product increment is the **stable rejection reason-code taxonomy**
  for `verify` failures — introduce `VerifyReasonCodeV1` (`att.verify.*`)
  across the verifier, CLI JSON output, and SDK result surface, backed by
  conformance vectors.
- Close the signed-schema enforcement loop: add `verify --require-non-empty`,
  `--strict-schema` CLI flags, minimum-bundle SDK helper, signed-schema
  round-trip regression locking, and negative conformance vectors against
  malformed or empty input.
- Publish a P2 docs task that records the v1.7.5 user-visible delta
  (non-empty + minimum-schema bundle contract), without touching
  `CHANGELOG.md` or any release workflow.
- Reference the already-open issue set for each task instead of duplicating
  scope.

## P0 Issues

No standalone P0 product task is proposed for this daily plan. Verifier
rejection-reason parity is the primary product surface change, but there is no
active release-claim blocker that requires a P0 carve-out. Existing blocker
tracking remains in the open issue set and is handled as support/context work
only in this plan.

## P1 Issues

### ISSUE 1 · \[P1\]\[verifier\] Introduce stable rejection reason-code taxonomy for `verify` failures

Owner: verifier

Affected modules:

- Python SDK verifier (`verifier.py`)
- Python SDK reason-codes module (`verify_reason_codes.py`)
- Python `__init__.py` exports

Acceptance criteria:

1. Define `VerifyReasonCodeV1` with a stable set of `att.verify.*` codes
   (e.g. `schema_invalid`, `signature_missing`, `canonical_mismatch`,
   `structure_invalid`, `required_field_missing`, `anchor_invalid`,
   `schema_unknown`, `schema_version_missing`, `schema_version_unsupported`,
   `signature_invalid`).
2. Wire the taxonomy into `BundleVerificationResult.primary_reason` and
   `secondary_reasons` so that every rejected bundle carries a machine-readable
   reason code in addition to the existing human-readable failure string.
3. The taxonomy is versioned (`VERIFY_REASON_TAXONOMY_VERSION`) for future
   additive extensions and is exported from `attestplane/__init__.py`.
4. Existing `error_code`, `VerifyError`, and human-readable messages remain
   stable; the new taxonomy is an additive surface.

Validation commands:

- `python3.11 -m pytest tests/verifier -k 'reason_code' -q --tb=short`
- `python3.11 -m pytest sdk/python/tests -q --tb=short`
- `python3.11 -m mypy sdk/python/src/ --ignore-missing-imports`
- `git diff --check`

Rollout / migration notes:

- Additive change only; existing `VerifyError` / `error_code` consumers are
  unaffected.
- New `VerifyReasonCodeV1` enum is the single source of truth for CLI JSON
  `reason_code` output.

---

### ISSUE 2 · \[P1\]\[cli\] Expose `verify --require-non-empty` and `--strict-schema` flags

Owner: CLI

Affected modules:

- Python CLI (`cli/main.py`, `cli/verify_json.py`)
- Python SDK verifier interface

Acceptance criteria:

1. Add `--require-non-empty` flag: reject bundles with zero events in the
   chain.
2. Add `--strict-schema` flag: require a signed schema attestation in the
   proof bundle.
3. Both flags produce structured JSON output with the correct
   `att.verify.*` reason code on failure.
4. Exit codes follow the existing convention (0 = pass, 1 = verify failure,
   2 = gate failure, 3 = usage error).
5. No breaking changes to existing CLI flags or default behavior.

Validation commands:

- `python3.11 -m attestplane verify --require-non-empty --json < fixture`
- `python3.11 -m attestplane verify --strict-schema --json < fixture`
- `python3.11 -m pytest sdk/python/tests/cli -q --tb=short`
- `python3.11 -m ruff check sdk/python/src/attestplane/cli/`

Rollout / migration notes:

- Both flags default to `False`; existing pipelines are unaffected.
- JSON output test fixtures should be updated in a follow-up P2 docs task.

---

### ISSUE 3 · \[P1\]\[verifier\] Add signed-schema round-trip regression locking

Owner: verifier

Affected modules:

- Python SDK verifier (`verifier.py`)
- Proof bundle builder (`proof_bundle.py`)
- Conformance tests

Acceptance criteria:

1. Add a conformance test that builds a signed proof bundle, serializes,
   round-trips through the verifier, and asserts the signed schema is
   preserved and correctly validated.
2. The test locks the `att.verify.*` reason code that the verifier emits
   when the schema is missing or tampered.
3. Existing positive and negative signed-schema matrices remain green.

Validation commands:

- `python3.11 -m pytest tests/conformance -k 'signed_schema or roundtrip' -q --tb=short`
- `python3.11 -m ruff check sdk/python/src/attestplane/`
- `git diff --check`

Rollout / migration notes:

- Lock in `tests/conformance/` as a permanent regression guard.
- Fixture hashes are updated only when a new vector is intentionally added.

---

### ISSUE 4 · \[P1\]\[sdk\] Add minimum proof bundle SDK helper

Owner: SDK

Affected modules:

- Python SDK (`sdk/bundle.py`)
- Python SDK exports (`sdk/__init__.py`)
- Python SDK examples (`sdk/examples/minimum_bundle.py`)

Acceptance criteria:

1. Expose `verify_minimum_bundle()` and `verify_minimum_bundle_file()` SDK
   helper functions.
2. The helper validates: chain non-empty, existence of at least one signature,
   presence of an anchoring timestamp, and a valid schema.
3. Raise `EmptyProofBundleError` / `IncompleteProofBundleError` with clear
   messages on failure.
4. Provide a CLI-pipeable example (`python -m attestplane.sdk.examples.minimum_bundle`).

Validation commands:

- `python3.11 -m pytest sdk/python/tests/sdk -q --tb=short`
- `python3.11 -m pytest tests/conformance -k 'minimum_bundle' -q --tb=short`
- `python3.11 -m attestplane.sdk.examples.minimum_bundle | python3.11 -m attestplane.sdk.verify_minimum_bundle`

Rollout / migration notes:

- New public API surface; existing SDK consumers are unaffected.
- Document in the P2 docs task.

---

### ISSUE 5 · \[P1\]\[conformance\] Add negative conformance vectors

Owner: conformance

Affected modules:

- Python conformance vector loader (`conformance/negative_vectors.py`)
- Conformance test runner (`conformance/run.py`)
- Negative vector JSON fixtures
- Verifier conformance tests

Acceptance criteria:

1. Define at least 5 negative canonicalization vectors (empty bundle, empty
   attestation array, missing subject digest, missing signature, malformed
   payload).
2. Each vector maps to exactly one `att.verify.*` reason code.
3. The conformance runner (`conformance/run.py`) classifies and asserts each
   vector through the shared `classify_negative_vector()` helper.
4. Both the top-level `tests/conformance/` and `sdk/python/tests/conformance/`
   test suites load and pass the new vectors.

Validation commands:

- `python3.11 -m pytest tests/conformance -k 'negative' -q --tb=short`
- `python3.11 -m pytest sdk/python/tests/conformance -q --tb=short`
- `python3.11 -c 'from attestplane.conformance.negative_vectors import classify_negative_vector; print("OK")'`
- `git diff --check`

Rollout / migration notes:

- Vectors are JSON fixtures under `tests/conformance/vectors/negative/`.
- Attach a conformance-matrix lock document parallel to
  `canonicalization_negative_matrix.md`.

---

### ISSUE 6 · \[P1\]\[verifier\] Enforce proof bundle signed schema

Owner: verifier

Affected modules:

- Python SDK verifier (`verifier.py`)
- Proof bundle schema validation (`proof_bundle.py`)
- Verifier conformance tests

Acceptance criteria:

1. The verifier rejects proof bundles whose `signed_schema` field is
   missing, malformed, or references an unknown schema version.
2. The rejection emits the appropriate `att.verify.schema_*` reason code.
3. Existing positive vectors (bundles with valid signed schemas) continue to
   pass.
4. The enforcement is optional by default and gated behind
   `require_signed_attestation` in the `BundleVerificationOptions`.

Validation commands:

- `python3.11 -m pytest tests/verifier -k 'signed_schema or schema_' -q --tb=short`
- `python3.11 -m pytest tests/conformance -k 'signed_schema' -q --tb=short`
- `git diff --check`

Rollout / migration notes:

- Gated enforcement: opt-in through `BundleVerificationOptions`; no existing
  caller breaks.
- Round-trip regression (Issue 3) covers the full cycle.

## P2 Issues

### ISSUE 7 · \[P2\]\[docs\]\[release\] Summarize the v1.7.5 user-visible delta

Owner: docs/release

Affected modules:

- docs
- release notes
- validation evidence

Acceptance criteria:

1. Document the user-visible delta for the v1.7.5 milestone: reason-code
   taxonomy, `--require-non-empty` and `--strict-schema` CLI flags,
   minimum-bundle SDK helper, signed-schema enforcement, and new conformance
   vectors.
2. Record the non-empty + minimum-schema bundle contract boundary.
3. Keep wording within the existing claim-safety boundaries; do not touch
   `CHANGELOG.md`.

Validation commands:

- `markdown-link-check docs/**/*.md`
- `git diff --check`

Rollout / migration notes:

- Support work only; must not substitute for the product increment tasks.
- Do not modify release tags, publish artifacts, or weaken gates.
- Reference the P1 issue list rather than duplicating acceptance details.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{
  "anchor_tag": "v1.5.0",
  "consultation_level": "diff",
  "head_sha": "d9749109fbbe3c650eb84e46f291711274d919ef",
  "issues": [
    {
      "acceptance_criteria": [
        "Define `VerifyReasonCodeV1` with a stable set of `att.verify.*` codes",
        "Wire the taxonomy into `BundleVerificationResult.primary_reason` and `secondary_reasons`",
        "The taxonomy is versioned and exported from `attestplane/__init__.py`",
        "Existing `error_code`, `VerifyError`, and human-readable messages remain stable"
      ],
      "modules": [
        "Python SDK verifier",
        "Python SDK reason-codes module",
        "Python __init__.py exports"
      ],
      "ordinal": 1,
      "priority": "P1",
      "rollout_notes": "Additive change only; existing VerifyError / error_code consumers are unaffected.",
      "title": "[P1][verifier] Introduce stable rejection reason-code taxonomy for verify failures",
      "validation_commands": [
        "python3.11 -m pytest tests/verifier -k 'reason_code' -q --tb=short",
        "python3.11 -m pytest sdk/python/tests -q --tb=short",
        "python3.11 -m mypy sdk/python/src/ --ignore-missing-imports",
        "git diff --check"
      ]
    },
    {
      "acceptance_criteria": [
        "Add --require-non-empty flag: reject bundles with zero events",
        "Add --strict-schema flag: require a signed schema attestation",
        "Both flags produce structured JSON output with correct att.verify.* reason code",
        "Exit codes follow existing convention (0=pass, 1=fail, 2=gate, 3=usage)",
        "No breaking changes to existing CLI flags or default behavior"
      ],
      "modules": [
        "Python CLI (main.py, verify_json.py)",
        "Python SDK verifier interface"
      ],
      "ordinal": 2,
      "priority": "P1",
      "rollout_notes": "Both flags default to False; existing pipelines are unaffected.",
      "title": "[P1][cli] Expose verify --require-non-empty and --strict-schema flags",
      "validation_commands": [
        "python3.11 -m attestplane verify --require-non-empty --json < fixture",
        "python3.11 -m attestplane verify --strict-schema --json < fixture",
        "python3.11 -m pytest sdk/python/tests/cli -q --tb=short",
        "python3.11 -m ruff check sdk/python/src/attestplane/cli/"
      ]
    },
    {
      "acceptance_criteria": [
        "Build signed proof bundle, serialize, round-trip through verifier, assert schema preserved",
        "Test locks the att.verify.* reason code for missing/tampered schema",
        "Existing positive and negative signed-schema matrices remain green"
      ],
      "modules": [
        "Python SDK verifier (verifier.py)",
        "Proof bundle builder (proof_bundle.py)",
        "Conformance tests"
      ],
      "ordinal": 3,
      "priority": "P1",
      "rollout_notes": "Lock in tests/conformance/ as a permanent regression guard.",
      "title": "[P1][verifier] Add signed-schema round-trip regression locking",
      "validation_commands": [
        "python3.11 -m pytest tests/conformance -k 'signed_schema or roundtrip' -q --tb=short",
        "python3.11 -m ruff check sdk/python/src/attestplane/",
        "git diff --check"
      ]
    },
    {
      "acceptance_criteria": [
        "Expose verify_minimum_bundle() and verify_minimum_bundle_file() SDK helpers",
        "Validate: chain non-empty, at least one signature, anchoring timestamp, valid schema",
        "Raise EmptyProofBundleError / IncompleteProofBundleError on failure",
        "Provide CLI-pipeable example (python -m attestplane.sdk.examples.minimum_bundle)"
      ],
      "modules": [
        "Python SDK (sdk/bundle.py)",
        "Python SDK exports (sdk/__init__.py)",
        "Python SDK examples"
      ],
      "ordinal": 4,
      "priority": "P1",
      "rollout_notes": "New public API surface; existing SDK consumers are unaffected.",
      "title": "[P1][sdk] Add minimum proof bundle SDK helper",
      "validation_commands": [
        "python3.11 -m pytest sdk/python/tests/sdk -q --tb=short",
        "python3.11 -m pytest tests/conformance -k 'minimum_bundle' -q --tb=short",
        "python3.11 -m attestplane.sdk.examples.minimum_bundle | python3.11 -m attestplane.sdk.verify_minimum_bundle"
      ]
    },
    {
      "acceptance_criteria": [
        "Define at least 5 negative canonicalization vectors (empty bundle, empty attestation array, missing subject digest, missing signature, malformed payload)",
        "Each vector maps to exactly one att.verify.* reason code",
        "Both top-level and SDK conformance test suites load and pass new vectors"
      ],
      "modules": [
        "Python conformance vector loader (negative_vectors.py)",
        "Conformance test runner (run.py)",
        "Negative vector JSON fixtures",
        "Verifier conformance tests"
      ],
      "ordinal": 5,
      "priority": "P1",
      "rollout_notes": "Vectors are JSON fixtures under tests/conformance/vectors/negative/.",
      "title": "[P1][conformance] Add negative conformance vectors",
      "validation_commands": [
        "python3.11 -m pytest tests/conformance -k 'negative' -q --tb=short",
        "python3.11 -m pytest sdk/python/tests/conformance -q --tb=short",
        "git diff --check"
      ]
    },
    {
      "acceptance_criteria": [
        "Verifier rejects bundles with missing/malformed/unknown signed_schema",
        "Rejection emits appropriate att.verify.schema_* reason code",
        "Existing positive vectors continue to pass",
        "Gated behind require_signed_attestation in BundleVerificationOptions"
      ],
      "modules": [
        "Python SDK verifier (verifier.py)",
        "Proof bundle schema validation (proof_bundle.py)",
        "Verifier conformance tests"
      ],
      "ordinal": 6,
      "priority": "P1",
      "rollout_notes": "Gated enforcement: opt-in through BundleVerificationOptions; no existing caller breaks.",
      "title": "[P1][verifier] Enforce proof bundle signed schema",
      "validation_commands": [
        "python3.11 -m pytest tests/verifier -k 'signed_schema or schema_' -q --tb=short",
        "python3.11 -m pytest tests/conformance -k 'signed_schema' -q --tb=short",
        "git diff --check"
      ]
    },
    {
      "acceptance_criteria": [
        "Document user-visible delta: reason-code taxonomy, CLI flags, minimum-bundle helper, signed-schema enforcement, conformance vectors",
        "Record non-empty + minimum-schema bundle contract boundary",
        "Keep wording within existing claim-safety boundaries; do not touch CHANGELOG.md"
      ],
      "modules": [
        "docs",
        "release notes",
        "validation evidence"
      ],
      "ordinal": 7,
      "priority": "P2",
      "rollout_notes": "Support work only; must not substitute for product increment tasks.",
      "title": "[P2][docs][release] Summarize the v1.7.5 user-visible delta",
      "validation_commands": [
        "markdown-link-check docs/**/*.md",
        "git diff --check"
      ]
    }
  ],
  "milestone_tag": "v1.7.5",
  "plan_level": "daily",
  "schema": "attestplane.plan.v1",
  "schema_version": 1
}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
