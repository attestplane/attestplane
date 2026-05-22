# Issue 139 Validation Evidence

Plan ID: `2e8af61f69ea41f4`

## Issue-Required Commands

`PYTHONPATH=sdk/python/src pytest tests/verifier/test_signed_schema_roundtrip.py -x -vv`

- Exit: 0
- Result: `2 passed in 0.04s`

`PYTHONPATH=sdk/python/src pytest tests/conformance -k signed_schema -x -vv`

- Exit: 0
- Result: `1 passed, 5 deselected in 0.04s`

## Focused Regression Commands

`PYTHONPATH=sdk/python/src pytest tests/verifier/test_proof_bundle_schema.py tests/verifier/test_conformance_fixtures.py -q`

- Exit: 0
- Result: `9 passed in 0.90s`

`PYTHONPATH=sdk/python/src pytest tests/conformance -q`

- Exit: 0
- Result: `6 passed in 0.03s`

`python scripts/conformance/verify_fixture_lock.py`

- Exit: 0
- Result: `Conformance fixtures: 16 files, all canonical hashes match ✓`

`./scripts/check-fixture-hashes.sh`

- Exit: 0
- Result: `Conformance fixtures: 16 files, all canonical hashes match ✓`

`PYTHONPATH=sdk/python/src pytest sdk/python/tests/signing/test_proof_bundle_signatures.py sdk/python/tests/signing/test_signature_vectors.py -q`

- Exit: 0
- Result: `16 passed, 1 skipped in 0.06s`
- Skip: local runner does not have `jsonschema`, so one schema-validation test in `test_proof_bundle_signatures.py` was skipped by its existing `pytest.importorskip("jsonschema")`.

`ruff check tests/verifier/test_signed_schema_roundtrip.py tests/conformance/test_signed_schema_roundtrip.py`

- Exit: 0
- Result: `All checks passed!`

## Local Gate

`run_gate attestplane`

- Exit: 65
- Result: unavailable in this checkout; helper resolved the project to `/Users/macworkers/attestplane`, which does not exist.

`run_gate Projects/attestplane`

- Exit: 0
- Result: `177 passed, 1 warning in 43.69s`
- Gate JSON: `{"project":"Projects/attestplane","mode":"fast","sha":"816c489","result":"PASS","duration_seconds":45,"report":""}`
- Warning: pytest cache could not write under `/Users/macworkers/Projects/attestplane/.pytest_cache` due to sandbox permissions; tests still passed.
