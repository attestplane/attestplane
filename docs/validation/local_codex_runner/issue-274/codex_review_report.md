# Local Codex Runner Review

- Status: `FAIL`
- Issue: #274, `[P1][verifier] Add a consumer taxonomy_version pinning gate to verify (--require-taxonomy-version)`

## Blocking

- The new taxonomy pin check short-circuits before existing verifier checks in [`sdk/python/src/attestplane/cli/verify_json.py:593-601`](/Users/macworkers/Projects/attestplane-lane-p2-docs/sdk/python/src/attestplane/cli/verify_json.py#L593) and [`sdk/python/src/attestplane/cli/main.py:439-649`](/Users/macworkers/Projects/attestplane-lane-p2-docs/sdk/python/src/attestplane/cli/main.py#L439). A bundle that would normally fail with exit 2, such as `--strict-schema` on a bundle missing signatures, is downgraded to exit 1 when the taxonomy pin is wrong. That weakens the release gate and masks stricter verifier failures.

## Warnings

- The added tests cover pin mismatch on passing fixtures, but they do not cover the downgrade path where a stronger pre-existing verifier failure is masked by the pin check.

## Validation

- Ran `pytest -q tests/cli/test_verify_json.py tests/cli/test_verify_explain.py tests/conformance/test_signed_schema_conformance_roundtrip.py tests/verifier/test_verify_reason_codes.py -q` successfully.
- Reproduced the downgrade locally: `attestplane verify --json --strict-schema tests/fixtures/bundles/missing_signatures.json` returned exit 2, while adding `--require-taxonomy-version 0.0.0` returned exit 1 with `att.verify.taxonomy_version_mismatch`.

## Residual Risk

- If merged as-is, consumers can treat a structurally invalid bundle as a taxonomy-pin mismatch and lose the stronger diagnostic.

## Publish / Tag / PyPI

- `no_merge_tag_publish_pypi: true`
