# Issue 139 Codex Review Report

Status: **FAIL**

## Blocking Reasons

- The current diff adds both `tests/verifier/test_signed_schema_roundtrip.py` and `tests/conformance/test_signed_schema_roundtrip.py` with the same module basename. A combined local pytest collection run fails before executing tests:

  ```text
  PYTHONPATH=sdk/python/src pytest tests/verifier/test_signed_schema_roundtrip.py tests/conformance/test_signed_schema_roundtrip.py -q
  ```

  Result: exit `2`, pytest import file mismatch. Pytest imports the verifier module as `test_signed_schema_roundtrip`, then rejects the conformance file with the same module name. This blocks safe collection when verifier and conformance tests are selected together.

## Warnings

- `docs/validation/local_codex_runner/issue-139/test.md` records passing evidence for the two new test files when run in separate pytest invocations, but that evidence does not cover combined collection.

## Checklist

| Check | Result | Notes |
|---|---:|---|
| 0. Review used only local repository files, local command output, and issue text | PASS | No external lookup was used. |
| 1. Diff weakened any release gate | PASS | No release gate files were changed; however, the same-basename test collision blocks combined pytest collection. |
| 2. Lowered severity | PASS | No severity mapping or issue labels were changed. |
| 3. Leaked or logged secrets | PASS | Added tests and validation docs do not expose secrets. Fixture values are synthetic local test material. |
| 4. Modified publish/tag logic | PASS | No publish, tag, release, or package-publish logic was changed. |
| 5. Deleted key tests | PASS | The change is additive; no existing tests were deleted. |
| 6. Implemented behavior without tests or evidence | PASS | The change is test-only and local evidence exists, but combined collection currently fails. |
| 7. Introduced uncertain external dependencies | PASS | No new dependency was added. |
| 8. Avoided merge, tag, package publish, and PyPI push | PASS | No merge, tag, package publish, or PyPI push was performed. |

## Validation

- `git status --short` showed untracked additions under `docs/validation/local_codex_runner/issue-139/`, `tests/conformance/test_signed_schema_roundtrip.py`, and `tests/verifier/test_signed_schema_roundtrip.py`.
- `git diff --stat` and `git diff --name-only` were empty because the relevant files are untracked.
- Inspected the new verifier and conformance tests directly.
- Inspected existing local context in `tests/verifier/test_proof_bundle_schema.py`, `tests/sdk/test_bundle_builder.py`, and `tests/fixtures/bundles/valid_signed_attestation.json`.
- Ran `PYTHONPATH=sdk/python/src pytest tests/verifier/test_signed_schema_roundtrip.py tests/conformance/test_signed_schema_roundtrip.py -q`: FAIL, exit `2`, pytest import file mismatch.
- Reviewed existing local evidence in `docs/validation/local_codex_runner/issue-139/test.md`, which reports separate issue-required runs, focused regressions, fixture hash checks, signing tests, ruff, and local fast gate as passing.

## Residual Risks

- After renaming one of the same-basename test files or otherwise making test module names unique, combined verifier and conformance collection should be re-run.
- Because the reviewed changes are untracked, a staged or committed diff should be rechecked before merge.

`no_merge_tag_publish_pypi`: `true`
