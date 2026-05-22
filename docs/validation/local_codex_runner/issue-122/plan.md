# Issue 122 Implementation Plan

Plan ID: `9da990667c3e65a6`

## Scope

Add negative verifier conformance vectors for the strict proof-bundle minimum schema contract introduced by the Issue 1 verifier work. The new vectors must cover empty bundle shape, empty attestations/signatures collection, missing signature data, and missing subject digest data, and each case must pin the strict verifier error code `bundle.schema.incomplete`.

This runner phase used only local repository files, local command output, and the issue text. The project-level Opus consultation requirement is not executed in this phase because the runner prompt explicitly forbids external advisory services.

## Current Local Findings

- The local strict verifier error code already exists as `VERIFY_BUNDLE_SCHEMA_INCOMPLETE = "bundle.schema.incomplete"` in `sdk/python/src/attestplane/verify_errors.py`.
- Existing verifier conformance coverage lives under `sdk/python/tests/conformance/`, with the current harness in `sdk/python/tests/conformance/test_verifier_conformance.py` and vector metadata in `sdk/python/tests/conformance/verifier_conformance_vectors.json`.
- Existing negative substrate fixtures live under `sdk/python/tests/conformance/negative/`, but these are broken-chain fixtures, not proof-bundle minimum-schema vectors.
- The fixture hash lock is `sdk/python/tests/conformance/FIXTURE_HASHES.lock`; the local verifier is `./scripts/check-fixture-hashes.sh`. The issue-requested `scripts/conformance/verify_fixture_lock.py` path is not present in this checkout.
- The issue-requested top-level `tests/conformance/` path is not present in this checkout. Top-level verifier compatibility tests currently live under `tests/verifier/`, and proof-bundle JSON fixtures live under `tests/fixtures/bundles/`.
- Existing strict bundle fixtures already cover similar malformed bundle shapes under `tests/fixtures/bundles/`, but Issue #122 requires public conformance vectors and lock registration rather than only unit fixtures.

## Implementation Approach

1. Add a public negative proof-bundle conformance vector set.
   - Prefer the issue-requested path `tests/conformance/vectors/negative/` if the accepted runner contract requires that exact public layout.
   - Also wire the vectors into the existing local conformance harness under `sdk/python/tests/conformance/` so current repository gates continue to discover them.
   - Keep positive vector files unchanged, especially `sdk/python/tests/conformance/vectors.json` and existing positive verifier cases.

2. Define four additive negative cases.
   - `empty-bundle`: a bundle with no proof events/attestations where strict verification must reject with `bundle.schema.incomplete` unless the existing zero-event non-empty error contract applies first.
   - `attestations-array-empty`: a bundle with events but no minimum signed-attestation/signature records.
   - `attestation-missing-signature`: an attestation/signature entry missing the signature payload or otherwise syntactically incomplete.
   - `attestation-missing-subject-digest`: an attestation/signature entry missing the digest field the strict schema checker requires for canonical subject binding.
   - If the local schema continues to name the collection `signatures` rather than `attestations`, encode the fixtures using the current repository shape but preserve the issue case IDs and descriptions.

3. Register the new cases in the verifier conformance harness.
   - Extend `sdk/python/tests/conformance/test_verifier_conformance.py` only enough to load/replay the new negative file(s).
   - Assert `result.ok is False` and `result.error_code == "bundle.schema.incomplete"` for each new case.
   - Avoid mutating existing positive case generation or `_base_bundle()` behavior.

4. Update the fixture lock additively.
   - Update `sdk/python/tests/conformance/FIXTURE_HASHES.lock` with entries only for new conformance JSON files.
   - Do not change existing locked hashes unless the implementation deliberately edits an existing conformance JSON file; the preferred path is to add new files and keep current entries byte-for-byte unchanged.
   - If a top-level `tests/conformance/vectors/negative/` tree is added, add or extend the requested lock verifier `scripts/conformance/verify_fixture_lock.py` so it validates that public tree without weakening `./scripts/check-fixture-hashes.sh`.

5. Add the v1.7.0 changelog note.
   - Add a short `CHANGELOG.md` entry under the active v1.7.0 conformance additions section once the repository's current release-note location is confirmed in the implementation phase.
   - State that the addition is conformance-only and downstream verifiers consuming the public vector set should re-run their suites.

## Files Likely To Change

- `tests/conformance/vectors/negative/empty-bundle.json` (new, if using issue-requested public path)
- `tests/conformance/vectors/negative/attestations-array-empty.json` (new)
- `tests/conformance/vectors/negative/attestation-missing-signature.json` (new)
- `tests/conformance/vectors/negative/attestation-missing-subject-digest.json` (new)
- `sdk/python/tests/conformance/proof_bundle_minimum_schema_negative_vectors.json` or equivalent additive vector file (new)
- `sdk/python/tests/conformance/test_verifier_conformance.py`
- `sdk/python/tests/conformance/FIXTURE_HASHES.lock`
- `scripts/conformance/verify_fixture_lock.py` (new compatibility verifier if the issue-required command must exist)
- `tests/conformance/test_negative_minimum_schema_vectors.py` or equivalent top-level test harness (new if adopting top-level public path)
- `tests/verifier/test_conformance_fixtures.py` if the top-level lock verifier needs to be included in existing compatibility tests
- `CHANGELOG.md`
- `docs/validation/local_codex_runner/issue-122/code.md` and `test.md` in later phases

## Tests And Local Gates

Issue-required validation commands:

```bash
pytest tests/conformance -q
python scripts/conformance/verify_fixture_lock.py
```

Existing local conformance checks to keep green:

```bash
pytest sdk/python/tests/conformance -q
pytest tests/verifier/test_conformance_fixtures.py -q
./scripts/check-fixture-hashes.sh
```

Focused verifier checks:

```bash
pytest sdk/python/tests/conformance/test_verifier_conformance.py -q
pytest tests/verifier/test_proof_bundle_schema.py -q
```

Local gate before implementation closure:

```bash
run_gate attestplane
```

If `run_gate attestplane` is unavailable in this checkout, record that fact in the test evidence and run the closest local conformance/Python gate without weakening the required release gates.

## Risk Classification

P1, low-to-medium implementation risk.

The intended change is conformance-only and additive, so runtime behavior should not change. The main risk is fixture-lock drift: updating an existing positive fixture or changing an existing locked digest would violate the issue acceptance criteria. The mitigation is to add new vector files, update lock entries only for those files, and run both the issue-requested lock verifier and the existing `./scripts/check-fixture-hashes.sh` gate.

There is a secondary schema-name risk because the issue text uses `attestations`, while the current local strict verifier and fixtures use `signatures` for signed-attestation schema data. The implementation should preserve the current repository wire shape while naming the cases according to the accepted issue criteria.

## Evidence Files To Update

- `docs/validation/local_codex_runner/issue-122/plan.md` for this planning phase.
- `docs/validation/local_codex_runner/issue-122/code.md` in the implementation phase, listing exact new vector files, harness changes, and lock updates.
- `docs/validation/local_codex_runner/issue-122/test.md` in the validation phase, with exact outputs from the required commands and local gates.
- `docs/validation/local_codex_runner/issue-122/review.md` if a later review phase is run.
- `CHANGELOG.md` for the v1.7.0 conformance addition note.

## Safety Confirmation

This task will not merge branches, create or move tags, publish npm packages, publish PyPI packages, push to PyPI, push to any remote, or weaken release gates. It will not lower P1 severity, remove failing tests to manufacture a pass, loosen claim-safety policy, or read/log credentials files such as ChatGPT cookies, GitHub tokens, OpenAI tokens, private keys, `.pypirc`, or `.npmrc`.
