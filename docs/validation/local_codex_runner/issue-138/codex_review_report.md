# Issue 138 Codex Review Report

Status: **PASS**

## Blocking Reasons

None.

## Warnings

None.

## Checklist

- Local-only review: PASS. Used only local repository files, local command output, and the issue text supplied in the prompt.
- Release gate weakening: PASS. No release gate was weakened.
- Severity lowering: PASS. No severity metadata was changed.
- Secret leakage: PASS. No secrets were read, printed, or logged.
- Publish/tag logic: PASS. No publish or tag logic was modified.
- Key test deletion: PASS. No key tests were deleted.
- Tests/evidence: PASS. New behavior has focused tests and local validation evidence.
- External dependencies: PASS. No uncertain external dependency was introduced.
- Merge/tag/publish/PyPI avoidance: PASS. No merge, tag, package publish, PyPI push, or remote push was performed.

## Review Notes

The Python CLI change in `sdk/python/src/attestplane/cli/main.py` exposes `--require-non-empty` and `--strict-schema`, preserves default `attestplane verify <bundle>` behavior, keeps backward compatibility for `--require-events` and `--bundle`, and maps proof-bundle contract failures to exit `2`.

The TypeScript verifier change mirrors the existing Python strict signed-attestation schema contract behind opt-in options and adds the `bundle.schema.incomplete` error code. The new root `package.json` is private workspace metadata only; it does not add dependencies or publish scripts.

## Validation

- `env PYTHONPATH=sdk/python/src pytest tests/cli/test_verify_flags.py sdk/python/tests/cli/test_verify_errors.py tests/cli/test_verify_errors.py tests/verifier/test_proof_bundle_schema.py -q` -> `16 passed`
- `npm run test --workspace sdk/typescript -- verifier.test.ts` -> `2 files passed, 21 tests passed`
- `npm run typecheck --workspace sdk/typescript` -> passed
- `git diff --check` -> passed
- `env PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance/test_verifier_conformance.py -q` -> `12 passed`
- Local source equivalent for `attestplane verify tests/fixtures/empty_bundle.json --require-non-empty` -> exit `2`, `VERIFY_REQUIRED_FIELDS_MISSING`
- Local source equivalent for `attestplane verify tests/fixtures/v1.7.0_signed.json --strict-schema` -> exit `0`

## Residual Risks

- `run_gate attestplane` is not configured for this checkout path, as already recorded in local validation evidence. Focused issue validation and conformance checks passed.
- This review did not use external Opus consultation because the requested runner checklist requires local-only inputs.

## Safety

`no_merge_tag_publish_pypi`: `true`
