# Issue 280 Review

Status: PASS

## Finding Summary

No blocking issues found in the current diff.

The change is limited to:

- new conformance vectors and frozen bundle fixtures for `schema_version_additive_positive` and `schema_version_unknown_required`
- a CLI smoke test for the checked-in forward-compatibility fixture
- SDK coverage tests that exercise the new selectors
- README documentation for the new selectors and fixture path

## Validation

- Reviewed the local diff for:
  - [`sdk/python/tests/test_issue209_schema_version_ci_coverage.py`](../../../../sdk/python/tests/test_issue209_schema_version_ci_coverage.py)
  - [`tests/cli/test_verify_flags.py`](../../../../tests/cli/test_verify_flags.py)
  - [`tests/conformance/README.md`](../../../../tests/conformance/README.md)
  - [`tests/conformance/schema_version/vectors.json`](../../../../tests/conformance/schema_version/vectors.json)
  - [`tests/conformance/test_schema_version_vectors.py`](../../../../tests/conformance/test_schema_version_vectors.py)
- Added the missing issue-280 evidence files:
  - [`docs/validation/local_codex_runner/issue-280/code.md`](code.md)
  - [`docs/validation/local_codex_runner/issue-280/test.md`](test.md)
  - [`docs/validation/local_codex_runner/issue-280/gate_report.md`](gate_report.md)
  - [`docs/validation/local_codex_runner/issue-280/gate_report.json`](gate_report.json)
- Inspected the new fixture and bundle files:
  - [`fixtures/forward-compat/additive-optional.json`](../../../../fixtures/forward-compat/additive-optional.json)
  - [`tests/conformance/schema_version/schema_version_additive_positive/bundle.json`](../../../../tests/conformance/schema_version/schema_version_additive_positive/bundle.json)
  - [`tests/conformance/schema_version/schema_version_unknown_required/bundle.json`](../../../../tests/conformance/schema_version/schema_version_unknown_required/bundle.json)
- Ran:
  - `pytest -q sdk/python/tests/test_issue209_schema_version_ci_coverage.py tests/cli/test_verify_flags.py tests/conformance/test_schema_version_vectors.py`
  - Result: `48 passed`
  - `PYTHONPATH=sdk/python/src python -m attestplane.cli.main verify --json fixtures/forward-compat/additive-optional.json`
  - Result: exit `0`, `att.verify.schema_unknown` absent
  - `PYTHONPATH=sdk/python/src python -m attestplane.cli.main verify --json tests/conformance/schema_version/schema_version_unknown_required/bundle.json`
  - Result: exit `1`, stable reason code `att.verify.schema_unknown`
  - `cd sdk/typescript && npm test`
  - Result: `32 passed`, `523 passed`
- Read the local gate artifact:
  - [`docs/validation/local_codex_runner/issue-280/gate_report.json`](gate_report.json)
  - Result: `area:verifier` PASS
- Attempted the mandated Opus reviewer helper:
  - `ask_opus.sh reviewer ...`
  - Result: `Not logged in`

## Checklist

- No release gate was weakened.
- No severity was lowered.
- No secrets were leaked or logged.
- No publish, tag, merge, or PyPI push logic was modified.
- No key tests were deleted.
- The behavior is supported by tests and fixtures.
- No uncertain external dependency was introduced.
- The diff does not perform merge/tag/package publish/PyPI push actions.

## Residual Risks

- The change does not alter verifier runtime code; it pins the intended behavior through tests and fixtures, so correctness still depends on the existing verifier implementation.
- The local broader conformance sweep already records one unrelated existing failure in `tests/conformance/test_signed_schema_conformance_roundtrip.py::test_signed_schema_taxonomy_version_is_stable_across_verify_json_and_explain`.
- The repository does not expose a root-level `npm run test:conformance` script, so the issue selector behavior was validated through the pytest selectors and CLI smoke checks that exercise the same frozen fixtures.
