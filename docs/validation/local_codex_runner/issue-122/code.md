# Issue 122 Code Evidence

Plan ID: `9da990667c3e65a6`

## Scope implemented

- Added four public negative proof-bundle vectors under
  `tests/conformance/vectors/negative/`:
  - `empty-bundle.json`
  - `attestations-array-empty.json`
  - `attestation-missing-signature.json`
  - `attestation-missing-subject-digest.json`
- Each vector includes a full bundle payload, `expected_ok: false`,
  `expected_error_code: "bundle.schema.incomplete"`, and
  `verify_options.require_signed_attestation: true`.
- Added
  `sdk/python/tests/conformance/proof_bundle_minimum_schema_negative_vectors.json`
  to register the public vector files in the SDK conformance corpus without
  changing existing positive vectors.
- Extended `sdk/python/tests/conformance/test_verifier_conformance.py` with an
  additive replay test for the new minimum-schema negative corpus.
- Added `tests/conformance/test_negative_minimum_schema_vectors.py` for the
  issue-required top-level `pytest tests/conformance -q` command.
- Extended `scripts/check-fixture-hashes.sh` to hash both existing
  `sdk/python/tests/conformance/*.json` fixtures and public
  `tests/conformance/vectors/**/*.json` fixtures.
- Added `scripts/conformance/verify_fixture_lock.py` as the issue-required
  wrapper around the existing fixture hash gate.
- Updated `sdk/python/tests/conformance/FIXTURE_HASHES.lock` additively:
  existing digest lines are unchanged; new entries cover the new SDK metadata
  file and four public negative vector files.
- Added the requested `CHANGELOG.md` note under `Unreleased / Conformance`.

## Safety notes

- No verifier runtime behavior was changed.
- No positive vector files were edited.
- No publish, tag, merge, or remote push operation was performed.
- This runner phase used local repository files and local command output only.
