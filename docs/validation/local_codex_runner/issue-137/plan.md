# Issue 137 Implementation Plan

Plan ID: `b90ec19045702353`

## Scope

Add canonicalization edge-case conformance coverage for the SDK minimum proof-bundle helper and strict verifier. This implementation should be additive: new vectors and tests only, with no mutation of existing v1.7.x fixture files or their locked hashes.

The local code currently exposes the minimum-bundle helper as `ProofBundleBuilder.minimal(...)` through `attestplane.sdk`; the issue text refers to `minimum_proof_bundle()`. Implementation should first confirm whether an alias exists or is expected by the accepted plan. If no such public helper exists in this repo, document the canonicalization invariants on the existing `ProofBundleBuilder.minimal` docstring and avoid adding a new public symbol unless required by the task issue.

## Files Likely To Change

- `sdk/python/src/attestplane/proof_bundle.py`
  - Expand the minimum helper docstring to say what the helper canonicalizes or constrains before emit, including lowercase 64-hex `subject_digest`, UTC microsecond timestamps generated through `chain_extend`, NFC-only payload strings enforced by canonicalization, sorted canonical event bytes, and signed event digest construction.
  - Document what remains verifier-rejected rather than helper-repaired, including duplicate raw JSON keys, BOM/trailing bytes around parsed JSON input, malformed hand-crafted signatures, NFD/non-NFC strings, unsafe integers, and metadata/signature closure drift.

- `sdk/python/src/attestplane/sdk/bundle.py`
  - Only if the accepted public API really contains `minimum_proof_bundle()`, add or document the SDK-facing helper/alias there. If the repo contract is only `ProofBundleBuilder.minimal`, leave API shape unchanged.

- `sdk/python/src/attestplane/sdk/examples/minimum_bundle.py`
  - Add if still absent, because the validation command expects `python -m attestplane.sdk.examples.minimum_bundle`.
  - Emit one strict-valid minimum bundle to stdout using deterministic test-safe signing material.

- `sdk/python/src/attestplane/sdk/examples/__init__.py`
  - Add if the examples package is introduced.

- `tests/conformance/README.md`
  - Add if still absent.
  - Reference the new additive canonicalization vector directories and describe downstream opt-in expectations.

- `tests/conformance/vectors/canonicalization/positive/*.json`
  - Add helper-emitted positive vectors for at least:
    - duplicate-key semantic control case, emitted through the helper with unique canonical object keys;
    - NFC payload string accepted case;
    - canonical JSON without BOM/trailing whitespace case;
    - integer-boundary timestamp/int64 accepted case.

- `tests/conformance/vectors/canonicalization/negative/*.json`
  - Add hand-crafted must-reject vectors for at least:
    - duplicate JSON keys in raw vector text or a raw JSON sidecar where parsing must use duplicate-key detection;
    - NFD payload string;
    - BOM and/or trailing non-whitespace bytes around canonical JSON;
    - integer field outside the signed 64-bit canonicalization boundary or timestamp field outside accepted strict shape.

- `tests/conformance/test_canonicalization_minimum_bundle_vectors.py`
  - Add a positive/negative vector replay test selected by `-k canonicalization`.
  - Include duplicate-key raw JSON loading with `object_pairs_hook` so the test can prove rejection before Python dict key collapse.

- `tests/conformance/test_negative_minimum_schema_vectors.py`
  - Extend or add parametrization so `-k minimum_bundle_negative` covers the new negative canonicalization vectors without changing existing negative vector expectations.

- `sdk/python/tests/conformance/FIXTURE_HASHES.lock`
  - Update via `./scripts/check-fixture-hashes.sh --update` after adding new vector files. Existing v1.7.x entries must remain unchanged; only new additive vector entries should appear.

## Implementation Steps

1. Inventory existing minimum-bundle and strict verifier behavior locally:
   - `ProofBundleBuilder.minimal` in `sdk/python/src/attestplane/proof_bundle.py`.
   - `verify_minimum_bundle` in `sdk/python/src/attestplane/sdk/bundle.py`.
   - strict verifier shape/canonical checks in `sdk/python/src/attestplane/verifier.py`.
   - current conformance fixtures under `tests/conformance/vectors/negative` and `sdk/python/tests/conformance/*.json`.

2. Add the new public conformance layout under `tests/conformance/vectors/canonicalization/` using additive subdirectories. Do not edit existing fixture JSON files.

3. Generate positive vectors through the SDK helper path rather than hand-writing successful bundles. Use deterministic inputs so fixture bytes and hash-lock output are stable.

4. Create negative vectors by hand-crafting malformed raw inputs. Keep these as explicit must-reject cases and assert the expected verifier or loader failure reason.

5. Add conformance tests that:
   - replay all positive vectors through `verify_proof_bundle(..., require_non_empty=True, require_signed_attestation=True)`;
   - reject all negative vectors;
   - detect duplicate raw JSON keys before normal `json.loads` collapses them;
   - keep selectors compatible with the issue validation commands: `-k canonicalization` and `-k minimum_bundle_negative`.

6. Add or update the SDK minimum-bundle example so the documented pipe command emits a valid bundle and the verifier accepts it in strict mode.

7. Update `tests/conformance/README.md` with the opt-in vector set description and the “additive only/no schema bump” migration note.

8. Refresh the fixture hash lock only after new vectors are present, then inspect the diff to confirm existing v1.7.x fixture hashes did not churn.

## Tests And Local Gates

Required issue validation:

- `pytest tests/conformance -k canonicalization -x`
- `pytest tests/conformance -k minimum_bundle_negative -x`
- `python -m attestplane.sdk.examples.minimum_bundle | python -m attestplane.verifier --strict`

Additional local checks:

- `pytest tests/sdk/test_bundle_builder.py tests/sdk/test_errors.py -q`
- `pytest tests/verifier/test_signed_schema_roundtrip.py tests/conformance -q`
- `./scripts/check-fixture-hashes.sh`
- `python -m pytest tests/verifier/test_conformance_fixtures.py -q`

If the implementation touches CLI/module entrypoints for `python -m attestplane.verifier`, also run a focused CLI smoke test for the strict verifier path.

## Risk Classification

Risk: Medium.

Reason: the change is additive, but conformance vectors and fixture hash locks are public compatibility surfaces. The main risks are accidentally changing existing locked fixture hashes, relying on Python dicts for duplicate-key cases after duplicates have already collapsed, or adding a public SDK symbol that conflicts with the existing `ProofBundleBuilder.minimal` API. Mitigation is additive directories, raw duplicate-key parsing in tests, deterministic fixture generation, and explicit fixture-hash diff review.

## Evidence Files To Update

- `docs/validation/local_codex_runner/issue-137/plan.md`
- `tests/conformance/README.md`
- `sdk/python/tests/conformance/FIXTURE_HASHES.lock`

Implementation evidence should also record validation command output under `docs/validation/local_codex_runner/issue-137/` if the runner phase for execution asks for it.

## Safety Confirmation

This task is plan-only in the current phase. It will not merge, tag, publish npm packages, publish PyPI packages, push to PyPI, push to any remote, weaken release gates, lower P0/P1 severity, remove failing tests to manufacture a pass, or loosen claim-safety policy.

This plan used only local repository files, local command output, and the provided issue text. It did not use web search, browser tools, external plugin/app connectors, external advisory services, or credential files.
