# Issue 185 Test Evidence

Plan ID: `961921d4a1b1325d`

## Required / Focused Commands

- `env PYTHONPATH=sdk/python/src /Users/macworkers/Projects/attestplane/sdk/python/.venv/bin/pytest sdk/python/tests/conformance/test_verifier_conformance.py -q`
  - PASS: `12 passed`

- `env PYTHONPATH=sdk/python/src /Users/macworkers/Projects/attestplane/sdk/python/.venv/bin/pytest tests/verifier/test_proof_bundle_schema.py tests/verifier/test_conformance_fixtures.py -q`
  - PASS: `9 passed`

- `PYTHONPATH=sdk/python/src /Users/macworkers/Projects/attestplane/sdk/python/.venv/bin/pytest tests/conformance/test_schema_version_matrix.py sdk/python/tests/test_schema_version_policy.py -q`
  - PASS: `17 passed`

- `./scripts/check-fixture-hashes.sh`
  - PASS: `27 files, all canonical hashes match`

## Sanity Check

- `git diff --check -- <touched files>`
  - PASS

## Validation Summary

The verifier/CLI policy tests pass, the schema-version conformance matrix is
green, and the fixture hash lock is consistent with the edited bundles.
