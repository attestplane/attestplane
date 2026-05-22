# Issue 154 Implementation Plan

Plan ID: `e2e4a0599bd4718a`

## Scope

Cross-wire the canonicalization edge-case vectors into the signed-schema round-trip regression so the verifier no longer round-trips only `tests/fixtures/bundles/valid_signed_attestation.json`. The implementation should remain test/infra-only: reuse one shared vector manifest/loader, generate signed minimum bundles from each positive canonicalization vector, rebuild each bundle through the existing signed-schema round-trip helper, and fail with vector-id-tagged diagnostics when canonical JSON equivalence breaks.

This planning phase used only local repository files, local command output, and the issue text. The project-level Opus consultation requirement is not executed in this runner phase because the runner prompt explicitly forbids external advisory services.

## Current Local Findings

- `tests/verifier/test_signed_schema_roundtrip.py` currently hard-codes `SIGNED_FIXTURES = (ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json",)` and parametrizes only that fixture.
- The reusable round-trip core already exists in the same file as `rebuild_signed_schema_fixture(...)`, with JSON-pointer-style mismatch diagnostics from `first_json_diff(...)`.
- The canonicalization vectors added locally under `tests/conformance/vectors/canonicalization/` are four positive helper-emitted vectors and four negative hand-crafted vectors:
  - `canonicalization-positive-duplicate-json-keys-helper-control`
  - `canonicalization-positive-nfc-payload-string`
  - `canonicalization-positive-canonical-json-no-bom-trailing`
  - `canonicalization-positive-int64-boundary-timestamp-payload`
  - `canonicalization-negative-duplicate-json-keys-raw`
  - `canonicalization-negative-nfd-payload-string`
  - `canonicalization-negative-bom-trailing-bytes-raw`
  - `canonicalization-negative-int64-overflow-timestamp-payload`
- `tests/conformance/test_canonicalization_minimum_bundle_vectors.py` currently has its own directory constants and `_load_vectors(...)` helper. That is the closest existing SDK/conformance helper path, but it is not yet a shared manifest module.
- `tests/conformance/README.md` documents the canonicalization vector suite as additive opt-in downstream verifier vectors.
- `sdk/python/tests/conformance/FIXTURE_HASHES.lock` already locks all eight canonicalization vector JSON files. The preferred implementation should not churn fixture locks unless a new manifest file is intentionally added and lock policy requires it.

## Implementation Approach

1. Add or promote a single shared canonicalization vector manifest/loader.
   - Prefer a small Python helper under `tests/conformance/`, for example `tests/conformance/canonicalization_vectors.py`, that defines `VECTOR_ROOT`, `POSITIVE_DIR`, `NEGATIVE_DIR`, and typed loader functions such as `load_positive_canonicalization_vectors()` and `load_negative_canonicalization_vectors()`.
   - Move the existing glob-and-sort behavior from `tests/conformance/test_canonicalization_minimum_bundle_vectors.py` into that helper.
   - Keep vector ordering deterministic by sorting by path or `case_id`.
   - Do not duplicate a hard-coded vector id list in verifier tests.

2. Update the existing canonicalization conformance test to use the shared loader.
   - Replace local `VECTOR_ROOT`, `POSITIVE_DIR`, `NEGATIVE_DIR`, and `_load_vectors(...)` constants in `tests/conformance/test_canonicalization_minimum_bundle_vectors.py` with imports from the shared helper.
   - Preserve the current positive and negative test behavior exactly.
   - Keep all eight vector ids visible in pytest parametrization output.

3. Extend signed-schema round-trip coverage to generated canonicalization positive vectors.
   - In `tests/verifier/test_signed_schema_roundtrip.py`, import the shared positive canonicalization vector loader and the canonicalization bundle emitter path.
   - Avoid importing test modules just for helper behavior if possible; either move `_parse_utc`, `_signer`, and `_emit_positive_bundle` to the shared helper or add a dedicated helper function such as `emit_positive_minimum_bundle(vector)`.
   - Build signed minimum bundles from each positive vector through `ProofBundleBuilder.minimal(...)`, preserving `seed_hex`, `event_id`, `now`, `subject_digest`, and `extra_payload`.
   - Parametrize round-trip tests with ids that include the vector `case_id`, alongside the existing locked fixture id.
   - For each generated vector bundle, call `rebuild_signed_schema_fixture(...)`, compare JSON structure through `first_json_diff(...)`, compare canonical JSON bytes, and run strict `verify_proof_bundle(..., require_non_empty=True, require_signed_attestation=True)`.

4. Make failures loud and vector-specific.
   - Include `case_id` or fixture name in every assertion message, including the structural diff and canonical byte mismatch.
   - For canonical byte mismatches, report enough context to identify the vector, for example `"{case_id}: canonical JSON bytes differ after signed-schema round-trip"`.
   - Preserve or improve the existing JSON pointer diagnostic so regressions identify the specific field as well as the vector.

5. Decide how to handle negative vectors explicitly.
   - The signed-schema byte-identical round-trip should only iterate positive helper-emitted vectors because negative vectors are intentionally malformed or must-reject mutations.
   - The shared manifest still needs to expose negative vectors for the existing conformance test, but verifier round-trip assertions should not manufacture passes by excluding positive cases.
   - If acceptance is interpreted to require enumerating all eight #150 vector ids in signed-schema output, add a separate negative-vector verifier test in the same module that loads negative vectors from the same manifest and asserts the expected rejection path with vector-id-tagged messages. Do not try to rebuild negative raw JSON through the signed-schema helper.

6. Keep fixture locks stable.
   - Do not rewrite existing vector JSON files or `valid_signed_attestation.json`.
   - If the implementation adds a JSON manifest file rather than a Python helper, add only that manifest entry to `sdk/python/tests/conformance/FIXTURE_HASHES.lock` if the local fixture lock gate requires it.
   - Preferred path is a Python shared loader to avoid public fixture hash churn.

## Files Likely To Change

- `tests/conformance/canonicalization_vectors.py` or equivalent shared helper module (new)
- `tests/conformance/test_canonicalization_minimum_bundle_vectors.py`
- `tests/verifier/test_signed_schema_roundtrip.py`
- `docs/validation/local_codex_runner/issue-154/code.md` in the implementation phase
- `docs/validation/local_codex_runner/issue-154/test.md` in the validation phase
- `docs/validation/local_codex_runner/issue-154/gate_report.md` / `.json` if a later gate phase records structured results

Files that should normally remain unchanged:

- `tests/conformance/vectors/canonicalization/**/*.json`
- `tests/fixtures/bundles/valid_signed_attestation.json`
- `sdk/python/tests/conformance/FIXTURE_HASHES.lock`, unless a new JSON manifest file is added and the lock gate requires one new entry
- Runtime SDK/verifier implementation files, unless the test exposes a real defect that is handled in a separate approved implementation phase
- Release artifacts and package manifests

## Tests And Local Gates

Focused issue validation:

```bash
PYTHONPATH=sdk/python/src pytest tests/verifier/test_signed_schema_roundtrip.py -vv
PYTHONPATH=sdk/python/src pytest tests/conformance/test_canonicalization_minimum_bundle_vectors.py -vv
git grep -n "canonicalization" tests/verifier
```

Full conformance validation:

```bash
PYTHONPATH=sdk/python/src pytest tests/conformance -q
python scripts/conformance/verify_fixture_lock.py
```

Related verifier regression checks:

```bash
PYTHONPATH=sdk/python/src pytest tests/verifier/test_proof_bundle_schema.py tests/verifier/test_conformance_fixtures.py -q
```

Repository/local gate before closure:

```bash
run_gate attestplane
```

If `run_gate attestplane` is unavailable in this checkout, record that in `test.md` and run the focused verifier/conformance commands above without weakening any required release gate.

## Risk Classification

P1, low-to-medium implementation risk.

The intended change is test-only and does not change public APIs, runtime verifier behavior, wire format, schemas, package artifacts, or release automation. The main risk is hidden drift between `ProofBundleBuilder.minimal(...)`, canonicalization vector generation, and the signed-schema rebuild helper. That is the intended regression signal; if found, the implementation should preserve the failing vector-id-tagged evidence rather than regenerating fixtures or weakening assertions.

A secondary risk is loader duplication. The mitigation is to move vector discovery into one shared helper and make both conformance and verifier tests import it, then confirm `git grep -n "canonicalization" tests/verifier` shows a single verifier-side manifest load site.

## Evidence Files To Update

- `docs/validation/local_codex_runner/issue-154/plan.md` for this planning phase.
- `docs/validation/local_codex_runner/issue-154/code.md` during implementation, listing exact files changed and the shared loader design chosen.
- `docs/validation/local_codex_runner/issue-154/test.md` during validation, with exact command lines and PASS/FAIL output summaries, including visible vector ids from the signed-schema round-trip test.
- `docs/validation/local_codex_runner/issue-154/gate_report.md` and `docs/validation/local_codex_runner/issue-154/gate_report.json` if a later local gate phase records structured gate evidence.
- `docs/validation/local_codex_runner/issue-154/pr_body.md` if a later PR packaging phase is run; it should reference #137, #139, and #150 as requested by the issue.

Do not update release assets, package manifests, schema files, or fixture locks for this pure test task unless the chosen shared manifest is a new locked fixture and the fixture-lock gate requires exactly that one new entry.

## Safety Confirmation

This task will not merge branches, create or move tags, publish npm packages, publish PyPI packages, push to PyPI, push to any remote, or weaken release gates. It will not lower P0/P1 severity, remove failing tests to manufacture a pass, loosen claim-safety policy, alter claim-safety gates, or read/log credentials files such as ChatGPT cookies, GitHub tokens, OpenAI tokens, private keys, `.pypirc`, or `.npmrc`.
