# Issue 122 Test Evidence

Plan ID: `9da990667c3e65a6`

## Required validation

```text
$ pytest tests/conformance -q
.....                                                                    [100%]
5 passed in 0.04s
```

```text
$ python scripts/conformance/verify_fixture_lock.py
Conformance fixtures: 16 files, all canonical hashes match ✓
```

## Additional focused validation

```text
$ PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance -q
............                                                             [100%]
12 passed in 0.04s
```

```text
$ PYTHONPATH=sdk/python/src pytest tests/verifier/test_conformance_fixtures.py tests/verifier/test_proof_bundle_schema.py -q
.........                                                                [100%]
9 passed in 0.57s
```

```text
$ ./scripts/check-fixture-hashes.sh
Conformance fixtures: 16 files, all canonical hashes match ✓
```

## Gate note

```text
$ run_gate attestplane
[run_gate] project dir not found: /Users/macworkers/attestplane
```

The repository is checked out at `/Users/macworkers/Projects/attestplane`.
Because the local `run_gate` helper resolves `attestplane` to a different
nonexistent path, the scoped local conformance and verifier gates above were
used as the concrete validation for this issue.
