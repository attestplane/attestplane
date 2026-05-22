# Issue 121 Implementation Plan

Plan ID: `bcea17ac4c19edbd`

## Scope

Implement the P0 verifier tightening for proof bundles that are non-empty at the event level but incomplete as signed proof bundles. The verifier must reject bundles that lack at least one signed attestation with a well-formed signature block and a canonical subject digest, using a stable error code distinct from the existing non-empty failure.

This runner phase used only local repository files, local command output, and the issue text. The project-level Opus consultation requirement is not executed in this phase because the runner prompt explicitly forbids external advisory services.

## Current Local Findings

- `sdk/python/src/attestplane/verifier.py` already has `_validate_shape(...)`, `require_non_empty`, and the existing empty-event failure path that returns `VERIFY_REQUIRED_FIELDS_MISSING`.
- Signature records are serialized/deserialized in `sdk/python/src/attestplane/proof_bundle.py` and verified in `sdk/python/src/attestplane/signing/verifier_ext.py`.
- `schemas/v1/proof_bundle.schema.json` defines optional `signatures` records and currently allows legacy bundles to omit them.
- Existing Python tests live under `sdk/python/tests/...`; the issue-requested `tests/verifier/test_proof_bundle_schema.py` and `tests/verifier/test_conformance_fixtures.py` are not present in this checkout.
- The current CLI shape is `python -m attestplane.cli verify <bundle>` with optional `--require-events`; the issue validation command uses `--bundle`.

## Implementation Approach

1. Add a verifier-level minimum signed-attestation schema gate.
   - Introduce a focused helper in `sdk/python/src/attestplane/verifier.py`, likely named `_validate_minimum_signed_attestation_schema(...)`.
   - Run it after `_validate_shape(bundle)` and before any future cryptographic signature verification path.
   - Require `signatures` to be present, be a non-empty list, and contain at least one syntactically valid signature record.
   - Require the signature subject digest field (`signed_event_hash_hex`) to be lowercase 64-hex, point at an event in the bundle, and match the canonical event hash produced by the existing event rehydration/canonicalization path.
   - Do not change canonicalization recipes or reserialize previously-valid bundles differently.

2. Add a stable incomplete-bundle error code.
   - Extend `sdk/python/src/attestplane/verify_errors.py` with a distinct code for this condition.
   - The issue suggests `bundle.schema.incomplete`; preserve that literal for CLI/user-facing output if the existing `VERIFY_*` taxonomy cannot safely use dotted strings.
   - Keep the existing empty-event error distinct from the new signed-attestation incompleteness error.

3. Preserve compatibility boundaries deliberately.
   - Do not change `ProofBundleBuilder` default serialization unless tests require a new fixture helper; existing builder tests currently assert bundles without signatures omit the `signatures` key for backward compatibility.
   - Avoid changing `schemas/v1/proof_bundle.schema.json` from optional to required unless the accepted v1.7.0 contract explicitly requires schema-level breaking behavior. Prefer verifier-level enforcement for the CLI/verifier path.
   - If schema text is updated, document it as verifier acceptance criteria rather than changing canonical bundle digest input.

4. Add fixtures for each negative failure mode.
   - Add `tests/fixtures/bundles/empty_attestations.json` for the required CLI validation case, or add a compatibility copy/symlink-equivalent fixture path if the project keeps canonical fixtures elsewhere.
   - Add one negative fixture per failure mode: missing `signatures`, empty `signatures`, malformed signature block, and signature digest that does not correspond to a canonical event hash.
   - Keep fixture-locked valid bundle digests unchanged.

5. Align CLI behavior with the issue validation command.
   - Update `sdk/python/src/attestplane/cli/main.py` only if needed to accept `verify --bundle <path>` while retaining the existing positional argument for compatibility.
   - Ensure non-zero exit and output include the stable incomplete-bundle error code.

## Files Likely To Change

- `sdk/python/src/attestplane/verifier.py`
- `sdk/python/src/attestplane/verify_errors.py`
- `sdk/python/src/attestplane/cli/main.py`
- `sdk/python/tests/test_proof_bundle.py`
- `sdk/python/tests/conformance/verifier_conformance_vectors.json`
- `sdk/python/tests/conformance/test_verifier_conformance.py`
- `sdk/python/tests/signing/test_proof_bundle_signatures.py`
- `tests/verifier/test_proof_bundle_schema.py` if the issue-required path is added
- `tests/verifier/test_conformance_fixtures.py` if the issue-required path is added
- `tests/fixtures/bundles/*.json` for new negative fixtures
- Possibly `schemas/v1/proof_bundle.schema.json` only for descriptive clarification, not for digest-breaking re-canonicalization

## Tests And Local Gates

Required targeted validation:

```bash
pytest tests/verifier/test_proof_bundle_schema.py -q
pytest tests/verifier/test_conformance_fixtures.py -q
python -m attestplane.cli verify --bundle tests/fixtures/bundles/empty_attestations.json
```

Existing local test coverage to keep green:

```bash
pytest sdk/python/tests/test_proof_bundle.py -q
pytest sdk/python/tests/signing/test_proof_bundle_signatures.py -q
pytest sdk/python/tests/signing/test_verifier_ext.py -q
pytest sdk/python/tests/conformance/test_verifier_conformance.py -q
pytest sdk/python/tests/test_conformance.py -q
```

Local gate before closure:

```bash
run_gate attestplane
```

If `run_gate attestplane` is unavailable for this repo, record the failure and run the closest local Python package gate from the project configuration without weakening the required release gates.

## Risk Classification

P0, medium implementation risk.

The behavioral change intentionally tightens verifier acceptance, so the main risk is rejecting legacy unsigned bundles in code paths that still expect chain/report-only verification. Mitigate by scoping the new minimum signed-attestation check to the issue’s intended verifier/CLI mode, keeping existing non-empty semantics distinct, and locking valid fixture digests byte-for-byte.

Canonicalization risk is high-impact but should remain low-likelihood if the implementation only compares existing canonical event hashes and does not alter `attestplane.canonical`, `hashchain.hash_event`, or signature payload construction.

## Evidence Files To Update

- `docs/validation/local_codex_runner/issue-121/plan.md` for this phase.
- Later implementation phases should add code/test evidence under `docs/validation/local_codex_runner/issue-121/`, for example `code.md`, `test.md`, and `review.md`, matching the runner flow.
- If conformance vectors or fixture locks are updated, include the exact commands and before/after digest confirmation in the phase evidence.

## Safety Confirmation

This task will not merge branches, move tags, create tags, publish npm packages, publish PyPI packages, push to PyPI, push to any remote, or weaken release gates. It will not lower P0/P1 severity, remove failing tests to manufacture a pass, loosen claim-safety policy, or read/log credentials files such as cookies, GitHub tokens, OpenAI tokens, private keys, `.pypirc`, or `.npmrc`.
