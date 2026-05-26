# Issue #294 Local Codex Runner Review

Status: PASS

## Summary

The diff pins the `attestplane verify --json` contract with checked-in pass/fail snapshots, adds matching conformance coverage, and updates docs to describe the stable exit-code split and snapshot-backed CI gating. I did not find any release-gate weakening, secret leakage, publish/tag logic changes, or test deletions.

## Key Checks

- [sdk/python/tests/cli/test_verify_json_contract.py](/Users/macworkers/Projects/attestplane-lane-p1-1/sdk/python/tests/cli/test_verify_json_contract.py:29) adds exact snapshot equality checks for the pass and fail `verify --json` payloads.
- [tests/conformance/vectors/verify_json/v1/pass.json](/Users/macworkers/Projects/attestplane-lane-p1-1/tests/conformance/vectors/verify_json/v1/pass.json) and [tests/conformance/vectors/verify_json/v1/fail.json](/Users/macworkers/Projects/attestplane-lane-p1-1/tests/conformance/vectors/verify_json/v1/fail.json) pin the structured JSON output contract.
- [sdk/typescript/test/cli-json-contract.test.ts](/Users/macworkers/Projects/attestplane-lane-p1-1/sdk/typescript/test/cli-json-contract.test.ts:1) adds a local selector test that exercises the same snapshots from Vitest.
- [sdk/python/src/attestplane/verifier.py](/Users/macworkers/Projects/attestplane-lane-p1-1/sdk/python/src/attestplane/verifier.py:461) only normalizes a schema-version error string; it does not change the exit-code contract.
- [docs/cli/verify-json.md](/Users/macworkers/Projects/attestplane-lane-p1-1/docs/cli/verify-json.md:26) and [docs/schema/verify-json.md](/Users/macworkers/Projects/attestplane-lane-p1-1/docs/schema/verify-json.md:13) document the stable `0 / 1 / 2` split and the snapshot pin.

## Validation

- `npm test -- cli-json-contract` in `sdk/typescript` passed.
- `python -m pytest sdk/python/tests/cli/test_verify_json_contract.py -q` could not run because `pytest` is not installed in this environment.
- Review was based only on local repository files, local command output, and the issue text.

## Verdict

No hard red-line violations found.

`no_merge_tag_publish_pypi`: `true`
