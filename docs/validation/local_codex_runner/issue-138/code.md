# Issue 138 Code Evidence

Plan ID: `ea2324f7e1effb2e`

## Summary

Implemented the local-only runner phase for Issue #138.

- Added `attestplane verify --require-non-empty` and `--strict-schema` in `sdk/python/src/attestplane/cli/main.py`.
- Preserved existing default `attestplane verify <bundle>` behavior and retained compatibility for `--require-events` and `--bundle`.
- Documented `verify` exit codes in `--help`: `0` success, `2` proof-bundle contract schema/non-empty violation, and `1` cryptographic/integrity/I/O or other verifier failure.
- Mapped schema/non-empty verifier failures (`VERIFY_REQUIRED_FIELDS_MISSING`, `bundle.schema.incomplete`, malformed bundle schema/JSON) to exit `2`.
- Added JSON payload fields `require_non_empty` and `strict_schema` while preserving existing `require_events` and `strict_proof_bundle_schema`.
- Added issue-named validation fixtures:
  - `tests/fixtures/empty_bundle.json`
  - `tests/fixtures/v1.7.0_signed.json`
- Added focused integration tests in `tests/cli/test_verify_flags.py`.
- Added root npm workspace metadata so the local runner's
  `npm run test --workspace sdk/typescript -- ...` gate command resolves
  the TypeScript SDK package from this checkout.
- Mirrored the Python verifier's opt-in strict signed-attestation schema
  gate in `sdk/typescript/src/verifier.ts`.
- Added `sdk/typescript/test/verifier.test.ts` for the issue-relevant
  TypeScript strict-schema behavior and the runner's test selector.
- Updated existing CLI/verifier expectations for strict schema/non-empty paths to return `2`.
- Added the CHANGELOG rollout note that downstream automation can opt into the flags before a future `x.0.0` default change.

## Files Changed

- `sdk/python/src/attestplane/cli/main.py`
- `tests/cli/test_verify_flags.py`
- `tests/fixtures/empty_bundle.json`
- `tests/fixtures/v1.7.0_signed.json`
- `tests/cli/test_verify_errors.py`
- `sdk/python/tests/cli/test_verify_errors.py`
- `sdk/python/tests/cli/test_main.py`
- `tests/verifier/test_proof_bundle_schema.py`
- `CHANGELOG.md`
- `package.json`
- `sdk/typescript/src/verifier.ts`
- `sdk/typescript/src/verify_errors.ts`
- `sdk/typescript/test/verifier.test.ts`

## Safety Notes

This phase used only local repository files, local command output, and the issue text. It did not use web search, browser tools, external plugin/app connectors, or external advisory services. It did not merge branches, create or move tags, publish packages, push PyPI, push remotes, lower P0/P1 severity, weaken release gates, or read/log credentials.
