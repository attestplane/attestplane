# Issue 280 Review

## Verdict

PASS.

The diff implements the requested forward-compatible path for known `schema_version` bundles carrying additive optional fields, and it keeps the fail-closed behavior for `proof_type` and `critical_*` fields intact. The Python verifier already used the same boundary, so the TS change aligns the SDKs instead of widening the policy beyond the existing shared rule.

## What I Checked

- Review used only local repository files, local command output, and the issue text.
- No release gate, publish, tag, merge, or PyPI path was modified.
- No secrets were added, printed, or logged by the reviewed diff.
- Key tests were added rather than removed.
- The new behavior is covered by both Python and TypeScript regression tests.

## Validation

- `sdk/python/.venv/bin/pytest tests/conformance/test_schema_version_vectors.py sdk/python/tests/test_issue209_schema_version_ci_coverage.py -q`
  - Result: `36 passed`
- `sdk/python/.venv/bin/python -m attestplane.cli.main verify fixtures/forward-compat/additive-optional.json`
  - Result: `exit 0`
- `cd sdk/typescript && npm run lint`
  - Result: `pass`
- `cd sdk/typescript && npm run typecheck`
  - Result: `pass`
- `cd sdk/typescript && npm test -- --run test/proof_bundle.test.ts`
  - Result: `31 passed`
- `cd sdk/typescript && npm test`
  - Result: `524 passed`
- `git diff --check`
  - Result: clean

## Warnings

1. The TS verifier now accepts all non-`ALLOWED_TOP_LEVEL` fields except the fail-closed `proof_type` and `critical_*` boundary. That is consistent with the Python verifier, but future additive field classes will still need explicit fixture coverage if they carry special semantics.
2. The signed-schema roundtrip test no longer asserts exact stdout equality between `verify --json` and `explain --json`. It still checks the important structured fields, but formatter drift in unasserted output would no longer be caught by that test alone.

## Residual Risks

- The forward-compat path is pinned by one positive fixture and one TS regression test, so new additive shapes should get their own fixtures before being treated as stable.
- The acceptance boundary depends on the shared `proof_type` / `critical_*` fail-closed rule staying unchanged.

## Release Safety

- `no_merge_tag_publish_pypi`: `true`
