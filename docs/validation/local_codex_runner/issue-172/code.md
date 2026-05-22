# Issue 172 Code Evidence

Plan ID: `89926bf04ae98019`

Implemented locally without web search, external advisory services, publishing,
tagging, merging, or remote pushes.

## Runtime / SDK Changes

- Added Python public verifier rejection taxonomy:
  `sdk/python/src/attestplane/verify_reason_codes.py`.
- Added TypeScript public verifier rejection taxonomy:
  `sdk/typescript/src/verify_reason_codes.ts`.
- Threaded `primary_reason` and `secondary_reasons` through:
  - `sdk/python/src/attestplane/verifier.py`
  - `sdk/typescript/src/verifier.ts`
- Added `primary_reason` and `secondary_reasons` to
  `attestplane verify --json` output while preserving existing `error_code`
  and human-readable reason fields.
- Exported the new SDK taxonomy from:
  - `sdk/python/src/attestplane/__init__.py`
  - `sdk/typescript/src/index.ts`

## Conformance / Tests

- Added focused verifier reason-code coverage:
  `tests/verifier/test_verify_reason_codes.py`.
- Added TypeScript taxonomy coverage:
  `sdk/typescript/test/verify_reason_codes.test.ts`.
- Updated strict negative conformance vectors under
  `tests/conformance/vectors/negative/` with:
  - `expected_primary_reason`
  - `expected_secondary_reasons`
  - schema version bumped from
    `attestplane.proof_bundle.minimum_schema.negative.v1` to
    `attestplane.proof_bundle.minimum_schema.negative.v2`
- Updated
  `sdk/python/tests/conformance/proof_bundle_minimum_schema_negative_vectors.json`
  to mirror the reason expectations.
- Updated verifier, CLI, and conformance tests to assert the new reason fields.

## Public API / Docs

- Regenerated `api/public/python_v1.json` and
  `api/public/typescript_v1.json` for the intentional additive public SDK
  surface.
- Updated `api/public/py_ts_allowlist_v1.json` for Python snake_case vs
  TypeScript camelCase helper naming.
- Updated `docs/errors.md` with the `att.verify.*` table and additive-only
  compatibility rule.
- Updated `CHANGELOG.md` with the new public reason-code surface and migration
  note.
- Updated `sdk/python/tests/conformance/FIXTURE_HASHES.lock` for the
  intentional negative-vector metadata changes.
