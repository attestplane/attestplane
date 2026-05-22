# Issue 139 Implementation Plan

Plan ID: `2e8af61f69ea41f4`

## Scope

Add a signed-schema round-trip regression that locks the Issue #126 / #121 minimum signed-attestation behavior against canonicalization drift. The implementation should be a pure test addition: load the locally locked signed fixture set, rebuild the same bundle through the Python SDK signing path with the deterministic test key/clock, serialize through the canonical bundle writer, and assert byte-identical JSON output against the locked fixture.

This runner phase used only local repository files, local command output, and the issue text. The project-level Opus consultation requirement is not executed in this phase because the runner prompt explicitly forbids external advisory services.

## Current Local Findings

- Strict signed-attestation enforcement already exists in `sdk/python/src/attestplane/verifier.py` and is covered by `tests/verifier/test_proof_bundle_schema.py`.
- Public negative signed-schema conformance vectors already exist under `tests/conformance/vectors/negative/` and are covered by `tests/conformance/test_negative_minimum_schema_vectors.py`.
- The fixture hash gate is `./scripts/check-fixture-hashes.sh`, wrapped by `scripts/conformance/verify_fixture_lock.py`; the current lock file is `sdk/python/tests/conformance/FIXTURE_HASHES.lock`.
- The reusable SDK pieces for this test are `ProofBundleBuilder`, `deserialize_signature_record`, `Signer`, and `InMemoryKeyProvider`.
- Existing deterministic signing vector tests live in `sdk/python/tests/signing/test_signature_vectors.py`; those tests lock signature payload recipes but do not assert byte-identical proof-bundle re-emission.
- `tests/fixtures/bundles/valid_signed_attestation.json` contains the current positive signed-schema bundle fixture. If this fixture cannot be reproduced from the SDK and deterministic test key without changing bytes, the implementation must stop and record a separate P0 drift issue rather than regenerating it.

## Implementation Approach

1. Add a focused round-trip regression test.
   - Create `tests/verifier/test_signed_schema_roundtrip.py`.
   - Discover signed positive bundle fixtures locally, starting with `tests/fixtures/bundles/valid_signed_attestation.json`.
   - Do not include malformed negative fixtures in the byte-identical re-sign loop; keep those covered by `tests/conformance -k signed_schema` / existing negative schema tests.

2. Rebuild each signed fixture through SDK primitives.
   - Parse the locked fixture as JSON with stable object ordering.
   - Rehydrate fixture events into `ChainedEvent` values using existing serialization/deserialization conventions already used by the verifier/hashchain tests.
   - Reconstruct a deterministic `Signer` with the fixture's test seed and frozen `signed_at` timestamp.
   - Re-sign the event or segment head according to `signature_mode`, add records through `ProofBundleBuilder.extend_signatures(...)`, and call `build(now=locked_verified_at)` so generated `verification_report.verified_at` remains fixed.
   - Serialize with the repository's canonical JSON convention used by fixture locks: sorted keys, compact separators, UTF-8, no network or wall-clock dependence.

3. Fail with field-level diagnostics.
   - Add a small recursive comparison helper in the test file that reports JSON pointer style paths such as `/signatures/0/signed_payload_b64` or `/chain_metadata/head_hash_hex`.
   - On mismatch, include both expected and actual values for the first divergent field.
   - Keep the existing fixture hash gate as a separate drift signal; the new test should fail on the exact field before falling back to a hash-only failure.

4. Guard the strict verifier behavior in the same test module.
   - After rebuilding each bundle, call `verify_proof_bundle(..., require_non_empty=True, require_signed_attestation=True)` or `verify_minimum_bundle(...)`.
   - Assert `ok is True`, `error_code == VERIFY_OK`, and `signed_attestation_schema_ok is True`.
   - This makes relaxed schema enforcement fail loudly even if byte output remains unchanged.

5. Wire a conformance marker for the required `-k signed_schema` command.
   - Prefer adding a small positive signed-schema conformance test under `tests/conformance/`, for example `tests/conformance/test_signed_schema_roundtrip.py`, that imports/reuses the top-level round-trip helper or exercises the same fixture through the strict verifier.
   - Ensure test names include `signed_schema` so `pytest tests/conformance -k signed_schema -x` selects meaningful coverage.
   - Avoid editing public JSON vector fixtures or `FIXTURE_HASHES.lock` unless the implementation adds a new public conformance fixture. The preferred implementation should not update fixture locks.

6. Drift handling rule.
   - If the round-trip exposes pre-existing drift in the v1.7.0 locked fixture, do not rewrite the fixture and do not update the lock.
   - Record the exact divergent field(s) in implementation evidence and open/escalate a separate P0 issue in the normal workflow.

## Files Likely To Change

- `tests/verifier/test_signed_schema_roundtrip.py` (new)
- `tests/conformance/test_signed_schema_roundtrip.py` or equivalent `signed_schema`-named conformance test (new)
- `docs/validation/local_codex_runner/issue-139/code.md` in the implementation phase
- `docs/validation/local_codex_runner/issue-139/test.md` in the validation phase
- `docs/validation/local_codex_runner/issue-139/review.md` if a later review phase is run

Files that should normally remain unchanged:

- `tests/fixtures/bundles/valid_signed_attestation.json`
- `tests/conformance/vectors/negative/*.json`
- `sdk/python/tests/conformance/FIXTURE_HASHES.lock`
- `schemas/v1/proof_bundle.schema.json`
- Runtime verifier and SDK implementation files, unless the new test reveals a real defect that must be handled in a separate code phase.

## Tests And Local Gates

Issue-required validation:

```bash
PYTHONPATH=sdk/python/src pytest tests/verifier/test_signed_schema_roundtrip.py -x -vv
PYTHONPATH=sdk/python/src pytest tests/conformance -k signed_schema -x
```

Existing focused checks to keep green:

```bash
PYTHONPATH=sdk/python/src pytest tests/verifier/test_proof_bundle_schema.py tests/verifier/test_conformance_fixtures.py -q
PYTHONPATH=sdk/python/src pytest tests/conformance -q
python scripts/conformance/verify_fixture_lock.py
./scripts/check-fixture-hashes.sh
```

Related SDK signing checks:

```bash
PYTHONPATH=sdk/python/src pytest sdk/python/tests/signing/test_proof_bundle_signatures.py sdk/python/tests/signing/test_signature_vectors.py -q
```

Local gate before closure:

```bash
run_gate attestplane
```

If `run_gate attestplane` is unavailable in this checkout, record the failure in `test.md` and run the closest local verifier/conformance gates above without weakening the required release gates.

## Risk Classification

P1, low-to-medium risk.

The intended change is test-only, so runtime and published artifact risk should be low. The main risk is discovering that the current positive signed fixture is not reproducible from the SDK/test key path. That is exactly the failure mode this issue is meant to expose; the mitigation is to fail with field-level diagnostics and escalate as a separate P0 rather than silently regenerating fixtures.

There is a secondary fixture-selection risk because local files include both positive signed-schema bundle fixtures and negative malformed signed-schema vectors. The byte-identical re-sign regression should target only reproducible positive signed fixtures, while negative fixtures remain covered by strict verifier conformance tests.

## Evidence Files To Update

- `docs/validation/local_codex_runner/issue-139/plan.md` for this planning phase.
- `docs/validation/local_codex_runner/issue-139/code.md` in the implementation phase, listing exact test files added and any helper logic.
- `docs/validation/local_codex_runner/issue-139/test.md` in the validation phase, with exact outputs from the issue-required commands, fixture-lock checks, and any unavailable gate notes.
- `docs/validation/local_codex_runner/issue-139/review.md` if review is run.

Do not update release assets, package manifests, fixture lock files, or schema hash locks for this pure test task unless a separately approved issue changes the conformance fixture set.

## Safety Confirmation

This task will not merge branches, create or move tags, publish npm packages, publish PyPI packages, push to PyPI, push to any remote, or weaken release gates. It will not lower P1 severity, remove failing tests to manufacture a pass, loosen claim-safety policy, or read/log credentials files such as ChatGPT cookies, GitHub tokens, OpenAI tokens, private keys, `.pypirc`, or `.npmrc`.
