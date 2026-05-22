# Issue 172 Implementation Plan

Plan ID: `89926bf04ae98019`

## Scope

Introduce a stable, SDK-public rejection reason-code taxonomy for `verify` failures, using namespaced additive-only string codes such as `att.verify.canonical_mismatch`. The implementation should thread exactly one primary reason code and zero or more secondary reason codes through verifier rejection results while preserving existing human-readable failure strings for one minor release.

This planning phase used only local repository files, local command output, and the issue text. The project-level Opus consultation requirement is not executed in this runner phase because the runner prompt explicitly forbids external advisory services.

## Current Local Findings

- `sdk/python/src/attestplane/reason_codes.py` and `sdk/typescript/src/reason_codes.ts` already define ADR-0010 `ReasonCodeV1`, but that surface uses uppercase chain/event/payload codes and explicitly says verifier return-shape threading is out of scope.
- `sdk/python/src/attestplane/verify_errors.py` and `sdk/typescript/src/verify_errors.ts` define a separate `VERIFY_*` CLI/verifier error taxonomy. This is not the requested issue taxonomy because the acceptance criteria require namespaced `att.verify.*` rejection reasons and `primary_reason` / `secondary_reasons`.
- `sdk/python/src/attestplane/verifier.py` currently returns `BundleVerificationResult.error_code` plus human strings such as `metadata_reason`, `policy_trace_refs_reason`, `retention_proofs_reason`, and `signed_attestation_schema_reason`.
- `attestplane verify --json` already exists in `sdk/python/src/attestplane/cli/main.py`; its JSON payload currently emits `error_code`, `chain_result.reason`, and specific human reason fields, but not `primary_reason` or `secondary_reasons`.
- Existing negative conformance coverage pins `expected_error_code` under `tests/conformance/vectors/negative/*.json` and `tests/conformance/test_negative_minimum_schema_vectors.py`. Issue #172 requires rejection paths to assert a specific reason code rather than only boolean/error-code status.
- Existing public API drift gates are present under `api/public/` and `sdk/python/tests/test_public_api_manifest.py`; adding SDK-public symbols will require intentional baseline updates.

## Proposed Taxonomy

Add a new verifier rejection taxonomy rather than repurposing ADR-0010 `ReasonCodeV1` or `VERIFY_*`.

Minimum v1 codes:

| Code | Intended primary use |
|---|---|
| `att.verify.canonical_mismatch` | Recomputed chain/canonical event hash mismatch, artifact hash mismatch, or verification report disagreement rooted in canonical bytes. |
| `att.verify.signature_invalid` | Cryptographic signature verification or DSSE signature check fails. |
| `att.verify.signature_missing` | Strict verification requires signature material but none is present. |
| `att.verify.schema_unknown` | Input declares an unknown schema or unsupported verification method namespace. |
| `att.verify.schema_invalid` | Input shape is malformed but the schema/version family is known. |
| `att.verify.schema_version_unsupported` | Bundle, payload, signature, or future schema version is recognized but unsupported by this verifier. |
| `att.verify.required_field_missing` | Required top-level, nested, signature, anchor, or verifier-envelope field is absent. |
| `att.verify.structure_invalid` | Structural relationship failure: metadata closure, policy refs, retention refs, duplicate refs, wrong array/object type, or malformed row. |
| `att.verify.anchor_invalid` | Anchor material is missing, malformed, unsupported, or fails anchor verification. |

The taxonomy should document additive-only evolution: adding a code is allowed with documentation and tests; removing or renaming a code is a breaking change that must be called out in `CHANGELOG.md`.

## Implementation Approach

1. Define the new public SDK taxonomy.
   - Prefer a dedicated module such as `sdk/python/src/attestplane/verify_reason_codes.py` to avoid confusing the new `att.verify.*` rejection reasons with ADR-0010 `ReasonCodeV1`.
   - Mirror the surface in TypeScript, for example `sdk/typescript/src/verify_reason_codes.ts`.
   - Expose constants/types for `VerifyReasonCodeV1`, `ALL_VERIFY_REASON_CODES_V1`, `VERIFY_REASON_CODE_DESCRIPTIONS`, `VERIFY_REASON_CODE_SCHEMA_VERSION`, and helper predicates.
   - Use a lowercase namespaced regex appropriate for these public codes, for example `^att\\.verify\\.[a-z][a-z0-9_]*$`.
   - Export the new symbols from `sdk/python/src/attestplane/__init__.py` and `sdk/typescript/src/index.ts` if the existing API policy expects public root exports.

2. Add a structured rejection reason container.
   - Add a small frozen Python dataclass or typed fields on `BundleVerificationResult`: `primary_reason: VerifyReasonCodeV1 | None` and `secondary_reasons: tuple[VerifyReasonCodeV1, ...]`.
   - Add equivalent TypeScript fields to `BundleVerificationResult`.
   - Keep existing `error_code` and human reason strings for compatibility; mark the human strings as deprecated in docs rather than removing them.
   - For `ok=True`, set `primary_reason` to `None` and `secondary_reasons` to an empty tuple/list.

3. Centralize failure-to-reason mapping.
   - Add a helper near `verify_proof_bundle(...)` that collects all failed checks in deterministic priority order and returns exactly one primary reason plus secondary reasons for additional failed checks.
   - Preserve current `error_code` priority unless the issue requires only the new reason fields to change. The new reason-code priority should be explicit and tested.
   - Suggested priority for current verifier paths:
     - Chain recompute/report disagreement: `att.verify.canonical_mismatch`.
     - `require_non_empty` empty events or missing required shape fields: `att.verify.required_field_missing`.
     - Missing strict signed-attestation material: `att.verify.signature_missing`.
     - Malformed strict signed-attestation material: `att.verify.signature_invalid` when cryptographic/encoding signature material is present but unusable, otherwise `att.verify.structure_invalid` or `att.verify.required_field_missing`.
     - Metadata closure, policy refs, and retention proof relationship failures: `att.verify.structure_invalid`.
     - Unsupported bundle/schema/signature version: `att.verify.schema_version_unsupported`.
     - Unknown verification method or unknown top-level schema family: `att.verify.schema_unknown`.
     - Other malformed known schema input: `att.verify.schema_invalid`.
   - Avoid parsing arbitrary human strings wherever a typed branch can emit the reason directly. If string classification is unavoidable during this step, isolate it in one helper and cover it with tests.

4. Thread reasons into CLI JSON without blocking #155.
   - In `cmd_verify`, include `primary_reason` and `secondary_reasons` in `--json` output for verifier result failures.
   - For `BundleSchemaError` and `BundleVerificationError` exception paths, include `primary_reason` as `att.verify.schema_invalid`, `att.verify.schema_version_unsupported`, `att.verify.required_field_missing`, or `att.verify.structure_invalid` based on typed/local classification; include `secondary_reasons: []`.
   - Preserve existing `error_code` JSON keys during the migration window so consumers are not broken before #155 completes.

5. Update conformance fixtures and negative tests.
   - Extend `tests/conformance/vectors/negative/*.json` with `expected_primary_reason` and `expected_secondary_reasons` while keeping `expected_error_code`.
   - Update `tests/conformance/test_negative_minimum_schema_vectors.py` to assert the new fields.
   - Add focused reason-code tests under `tests/verifier`, with names matching `reason_code`, to satisfy `pytest tests/verifier -k reason_code`.
   - Cover each required minimum code either with a current fixture path or a focused unit fixture. If a required code is reserved for a path not implemented yet, document it as reserved and test taxonomy membership rather than manufacturing a false verifier path.

6. Mirror TypeScript and public API evidence.
   - Add TypeScript taxonomy tests mirroring the Python vector file or use one shared JSON vector to ensure byte-identical code sets.
   - Update `api/public/python_v1.json`, `api/public/typescript_v1.json`, and the allowlist only as required by the existing public API gate.
   - Keep schema hash locks unchanged unless a new schema file is intentionally added. A taxonomy JSON conformance vector may need fixture-lock handling if placed under locked conformance fixtures.

7. Documentation and changelog.
   - Add or update documentation, likely `docs/errors.md`, with the new `att.verify.*` table and the additive-only rule.
   - Update `CHANGELOG.md` with the new public SDK surface, the migration note that human strings remain for one minor release with deprecated status, and the breaking-change rule for removing/renaming a reason code.
   - If ADR-0010 remains the governing document for old reason codes, add a short note there or in a new ADR/docs section clarifying the distinction between ADR-0010 `ReasonCodeV1`, `VERIFY_*`, and Issue #172 `att.verify.*` verifier rejection reasons.

## Files Likely To Change

- `sdk/python/src/attestplane/verify_reason_codes.py` (new)
- `sdk/python/src/attestplane/verifier.py`
- `sdk/python/src/attestplane/cli/main.py`
- `sdk/python/src/attestplane/__init__.py`
- `sdk/typescript/src/verify_reason_codes.ts` (new)
- `sdk/typescript/src/verifier.ts`
- `sdk/typescript/src/index.ts`
- `sdk/python/tests/test_verify_reason_codes.py` or `sdk/python/tests/test_reason_codes.py`
- `sdk/typescript/test/verify_reason_codes.test.ts`
- `tests/verifier/test_verify_reason_codes.py` or equivalent `reason_code`-named verifier tests
- `tests/conformance/test_negative_minimum_schema_vectors.py`
- `tests/conformance/vectors/negative/*.json`
- `sdk/python/tests/conformance/reason_codes_vectors.json` or a new dedicated verify-reason-code vector file
- `sdk/python/tests/cli/test_verify_cli_deterministic_json.py`
- `tests/cli/test_verify_errors.py` and/or `sdk/python/tests/cli/test_verify_errors.py`
- `api/public/python_v1.json`
- `api/public/typescript_v1.json`
- `docs/errors.md`
- `docs/adr/0010-verification-reason-codes.md` or a new verifier-rejection taxonomy doc
- `CHANGELOG.md`
- Evidence files under `docs/validation/local_codex_runner/issue-172/`

Files that should normally remain unchanged:

- Release artifacts under `release/artifacts/`
- Package publish configuration and package metadata, except public export metadata if required by tests
- Existing positive conformance fixtures, unless the implementation adds expected reason metadata to negative vectors only
- Release gate scripts and claim-safety policy

## Tests And Local Gates

Issue-required focused validation:

```bash
PYTHONPATH=sdk/python/src pytest tests/verifier -k reason_code -q
PYTHONPATH=sdk/python/src pytest tests/conformance -k negative -q
PYTHONPATH=sdk/python/src python -m attestplane.cli verify --json fixtures/conformance/negative/*.json
```

The last command may need the issue-approved stub/internal-helper variant because local negative fixtures currently live under `tests/conformance/vectors/negative/` and `sdk/python/tests/conformance/negative/`, not `fixtures/conformance/negative/`, and #155 may still be incomplete.

Focused compatibility checks:

```bash
PYTHONPATH=sdk/python/src pytest tests/verifier/test_proof_bundle_schema.py tests/verifier/test_conformance_fixtures.py -q
PYTHONPATH=sdk/python/src pytest tests/cli/test_verify_errors.py tests/cli/test_verify_flags.py -q
PYTHONPATH=sdk/python/src pytest sdk/python/tests/cli/test_verify_cli_deterministic_json.py -q
PYTHONPATH=sdk/python/src pytest sdk/python/tests/test_public_api_manifest.py -q
```

Cross-SDK checks if TypeScript mirror files change:

```bash
cd sdk/typescript && npm test -- --run reason_codes
./scripts/check-public-api.sh
```

Fixture and conformance checks:

```bash
python scripts/conformance/verify_fixture_lock.py
./scripts/check-fixture-hashes.sh
PYTHONPATH=sdk/python/src pytest tests/conformance -q
PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance/test_verifier_conformance.py -q
```

Local gate before closure:

```bash
run_gate attestplane
```

If `run_gate attestplane` is unavailable in this checkout, record that in `test.md` and run the focused verifier, conformance, public API, and fixture-lock commands above without weakening any required release gate.

## Risk Classification

P1, medium risk.

The change touches public SDK types, CLI JSON shape, verifier result shape, conformance vectors, and TypeScript/Python cross-SDK parity. The main compatibility risk is confusing three nearby surfaces: ADR-0010 `ReasonCodeV1`, `VERIFY_*` error codes, and the new `att.verify.*` rejection reasons. The mitigation is to implement the new taxonomy as a distinct module, document the relationship, and keep existing `error_code` and human strings during the migration window.

The main behavioral risk is assigning unstable or ambiguous primary reasons when multiple verifier checks fail. The mitigation is a deterministic priority helper that returns one primary reason plus secondary reasons, with tests that intentionally create multiple simultaneous failures and assert ordering.

There is a conformance-fixture risk if adding expected reason metadata changes locked fixture hashes. If fixture locks require updates, update only the relevant locked negative-vector entries and record the exact reason in implementation evidence; do not regenerate positive vectors or unrelated locks.

## Evidence Files To Update

- `docs/validation/local_codex_runner/issue-172/plan.md` for this planning phase.
- `docs/validation/local_codex_runner/issue-172/code.md` during implementation, listing exact runtime, SDK, doc, and conformance files changed.
- `docs/validation/local_codex_runner/issue-172/test.md` during validation, with exact command lines and PASS/FAIL summaries for required commands and any stubbed #155 smoke command.
- `docs/validation/local_codex_runner/issue-172/gate_report.md` and `docs/validation/local_codex_runner/issue-172/gate_report.json` if a later local gate phase records structured gate evidence.
- `docs/validation/local_codex_runner/issue-172/review.md` or `codex_review_report.*` if a later review phase is run.

## Safety Confirmation

This task will not merge branches, create or move tags, publish npm packages, publish PyPI packages, push to PyPI, push to any remote, or weaken release gates. It will not lower P0/P1 severity, remove failing tests to manufacture a pass, loosen release gates, loosen claim-safety policy, or read/log credentials files such as ChatGPT cookies, GitHub tokens, OpenAI tokens, private keys, `.pypirc`, or `.npmrc`.
