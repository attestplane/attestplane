<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Daily Development Plan for v1.8.7

## Concise Plan

- Keep this daily upgrade diff-level, but make the product increment real: surface `taxonomy_version` in the SDK `BundleVerificationResult.short_summary()` output so downstream consumers can read the version without parsing JSON.
- Align the CLI `verify --explain` output to also display `taxonomy_version` inline, matching the `--json` output contract.
- Pin the forward-compatible conformance path for `taxonomy_version` exposure across the SDK result and CLI surfaces.
- Publish a small docs/update task that explains the v1.8.7 user-visible delta and records the validation evidence, without changing `CHANGELOG.md` or any release workflow.

## P1 Issues

### ISSUE 1 · [P1][sdk][verifier] Surface `taxonomy_version` in `BundleVerificationResult.short_summary()`

Owner: sdk/verifier

Affected modules:

- Python SDK verifier (`verifier.py`)
- `BundleVerificationResult` result object

Acceptance criteria:

1. `BundleVerificationResult.short_summary()` includes the `taxonomy_version` field in its output when the field is present.
2. The output is backward compatible: existing parsers that match on "OK chain_id=" or "FAIL chain_id=" prefixes are unaffected.
3. When `taxonomy_version` is `None` (legacy bundles without the field), the short_summary omits the version or renders `taxonomy_version=unknown`.

Validation commands:

- `cd sdk/python && python3.11 -m pytest tests/ -k 'verifier' -q --tb=short 2>&1 | tail -20`
- `cd sdk/python && python3.11 -m pytest sdk/python/tests/ -k 'proof_bundle or cli' -q --tb=short 2>&1 | tail -20`
- `git diff --check`

Rollout / migration notes:

- Keep the current `short_summary()` format stable for the prefix match; only append `taxonomy_version=…` after the existing fields.
- Do not change `BundleVerificationResult` field names or remove existing fields.

### ISSUE 2 · [P1][cli][conformance] Pin `taxonomy_version` in `verify --explain` output and CI fixture

Owner: cli/conformance

Affected modules:

- Python CLI `verify --explain` human-readable output
- CLI output-contract fixture
- Fixture-lock maintenance

Acceptance criteria:

1. `verify --explain` includes `taxonomy_version=…` in its inline summary for bundles that declare `chain_metadata.evidence_taxonomy_version`.
2. A positive conformance vector confirms that `verify --explain` and `verify --json` produce the same `taxonomy_version` for the same bundle.
3. The `verify --json` output contract fixture is updated to include the `taxonomy_version` field.
4. Keep the negative vectors rejecting malformed or non-forward-compatible shapes unchanged.

Validation commands:

- `cd sdk/python && python3.11 -m pytest tests/verifier -k 'reason_code or taxonomy_version' -q --tb=short 2>&1 | tail -20`
- `cd sdk/python && python3.11 -m pytest sdk/python/tests/cli -q --tb=short 2>&1 | tail -20`
- `cd sdk/python && python3.11 -m pytest tests/conformance -k 'negative or forward' -q --tb=short 2>&1 | tail -20`
- `git diff --check`

Rollout / migration notes:

- Update locked fixture hashes only if the new vector is intentionally added.
- Do not regenerate unrelated fixtures.

## P2 Issues

### ISSUE 3 · [P2][docs][release] Document the v1.8.7 user-visible delta and verifier output contract

Owner: docs/release

Affected modules:

- docs
- validation evidence

Acceptance criteria:

1. Document the v1.8.7 user-visible delta: `BundleVerificationResult.short_summary()` now surfaces `taxonomy_version`.
2. Record the output-contract alignment evidence (`--explain` and `--json` convergence).
3. Keep the wording within the existing claim-safety boundaries and do not touch `CHANGELOG.md`.

Validation commands:

- `markdown-link-check docs/**/*.md`
- `git diff --check`

Rollout / migration notes:

- This is support work only and must not become a substitute for the product increment.
- Do not modify release tags, publish artifacts, or weaken gates.

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{"anchor_tag":"v1.5.0","consultation_level":"diff","head_sha":"febce07ff1a78637cfb4cfe0bcddab841a8bd189","issues":[{"acceptance_criteria":["BundleVerificationResult.short_summary() includes the taxonomy_version field in its output when the field is present.","The output is backward compatible: existing parsers that match on OK chain_id= or FAIL chain_id= prefixes are unaffected.","When taxonomy_version is None (legacy bundles without the field), the short_summary omits the version or renders taxonomy_version=unknown."],"modules":["Python SDK verifier (verifier.py)","BundleVerificationResult result object"],"ordinal":1,"priority":"P1","rollout_notes":"Keep the current short_summary() format stable for the prefix match; only append taxonomy_version=... after the existing fields. Do not change BundleVerificationResult field names or remove existing fields.","title":"[P1][sdk][verifier] Surface taxonomy_version in BundleVerificationResult.short_summary()","validation_commands":["cd sdk/python && python3.11 -m pytest tests/ -k 'verifier' -q --tb=short 2>&1 | tail -20","cd sdk/python && python3.11 -m pytest sdk/python/tests/ -k 'proof_bundle or cli' -q --tb=short 2>&1 | tail -20","git diff --check"]},{"acceptance_criteria":["verify --explain includes taxonomy_version=... in its inline summary for bundles that declare chain_metadata.evidence_taxonomy_version.","A positive conformance vector confirms that verify --explain and verify --json produce the same taxonomy_version for the same bundle.","The verify --json output contract fixture is updated to include the taxonomy_version field.","Keep the negative vectors rejecting malformed or non-forward-compatible shapes unchanged."],"modules":["Python CLI verify --explain human-readable output","CLI output-contract fixture","Fixture-lock maintenance"],"ordinal":2,"priority":"P1","rollout_notes":"Update locked fixture hashes only if the new vector is intentionally added. Do not regenerate unrelated fixtures.","title":"[P1][cli][conformance] Pin taxonomy_version in verify --explain output and CI fixture","validation_commands":["cd sdk/python && python3.11 -m pytest tests/verifier -k 'reason_code or taxonomy_version' -q --tb=short 2>&1 | tail -20","cd sdk/python && python3.11 -m pytest sdk/python/tests/cli -q --tb=short 2>&1 | tail -20","cd sdk/python && python3.11 -m pytest tests/conformance -k 'negative or forward' -q --tb=short 2>&1 | tail -20","git diff --check"]},{"acceptance_criteria":["Document the v1.8.7 user-visible delta: BundleVerificationResult.short_summary() now surfaces taxonomy_version.","Record the output-contract alignment evidence (--explain and --json convergence).","Keep the wording within the existing claim-safety boundaries and do not touch CHANGELOG.md."],"modules":["docs","validation evidence"],"ordinal":3,"priority":"P2","rollout_notes":"This is support work only and must not become a substitute for the product increment. Do not modify release tags, publish artifacts, or weaken gates.","title":"[P2][docs][release] Document the v1.8.7 user-visible delta and verifier output contract","validation_commands":["markdown-link-check docs/**/*.md","git diff --check"]}],"milestone_tag":"v1.8.7","plan_level":"daily","schema":"attestplane.plan.v1","schema_version":1}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
