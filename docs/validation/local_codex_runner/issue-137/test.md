# Issue 137 Local Validation

Date: 2026-05-22

Commands run:

- `env PYTHONPATH=sdk/python/src pytest tests/conformance -k canonicalization -x`
  - Result: PASS, 8 passed / 6 deselected.
- `env PYTHONPATH=sdk/python/src pytest tests/conformance -k minimum_bundle_negative -x`
  - Result: PASS, 4 passed / 10 deselected.
- `env PYTHONPATH=sdk/python/src python -m attestplane.sdk.examples.minimum_bundle | env PYTHONPATH=sdk/python/src python -m attestplane.verifier --strict`
  - Result: PASS, exit 0. Output included `OK chain_id='attestplane-sdk-minimum-example' events=1`.
  - Note: Python emitted the pre-existing runpy warning caused by package init importing `attestplane.verifier` before `python -m attestplane.verifier` executes the module.
- `./scripts/check-fixture-hashes.sh`
  - Result: PASS, `Conformance fixtures: 24 files, all canonical hashes match`.
- `env PYTHONPATH=sdk/python/src pytest tests/conformance -q`
  - Result: PASS, 14 passed.
- `env PYTHONPATH=sdk/python/src pytest tests/verifier/test_signed_schema_roundtrip.py tests/conformance -q`
  - Result: PASS, 16 passed.
- `env PYTHONPATH=sdk/python/src pytest tests/verifier/test_conformance_fixtures.py -q`
  - Result: PASS, 2 passed.
- `env PYTHONPATH=sdk/python/src pytest tests/sdk/test_bundle_builder.py tests/sdk/test_errors.py -q`
  - Result: PASS, 8 passed.
- `env PYTHONPATH=sdk/python/src pytest tests/sdk/test_bundle_builder.py sdk/python/tests/test_sdk_bundle.py -q`
  - Result: PASS, 14 passed.
- `cd sdk/python && ruff check src tests`
  - Result: PASS.
- `cd sdk/python && mypy`
  - Result: PASS, 53 source files.
- `git diff --check`
  - Result: PASS.
- Local Markdown sanity scan for changed files
  - Result: PASS for repeated blank lines, list-start spacing, and heading-level jumps.

Fixture lock review:

- `sdk/python/tests/conformance/FIXTURE_HASHES.lock` only gained the eight new
  `tests/conformance/vectors/canonicalization/{positive,negative}/*.json`
  entries. Existing v1.7.x fixture hashes did not change.
