# Issue 121 Test Evidence

Plan ID: `bcea17ac4c19edbd`

Required validation:

```text
$ pytest tests/verifier/test_proof_bundle_schema.py -q
.......                                                                  [100%]
7 passed in 0.04s
```

```text
$ pytest tests/verifier/test_conformance_fixtures.py -q
..                                                                       [100%]
2 passed in 0.49s
```

Combined rerun:

```text
$ pytest tests/verifier/test_proof_bundle_schema.py tests/verifier/test_conformance_fixtures.py -q
.........                                                                [100%]
9 passed in 0.53s
```

```text
$ python -m attestplane.cli verify --bundle tests/fixtures/bundles/empty_attestations.json
FAIL chain_id='p3-cli-proofbundle' events=1 first_bad_index=None reason=None agreement=True metadata_reason=None policy_trace_refs_reason=None retention_proofs_reason=None signed_attestation_schema_reason='signatures must contain at least one signed attestation' error_code=bundle.schema.incomplete
MODE: chain/report-oriented, not a full verifier. This command replays bundle events, compares the embedded verification_report with the recomputed chain result, and fails closed on malformed ProofBundle metadata and policy_trace_refs closure. It does not perform signature verification, anchor verification, or compliance certification.
```

Additional local checks:

```text
$ ruff check scripts/local_codex_runner/codex_driver.py scripts/local_codex_runner/run_issue.py sdk/python/src/attestplane/verifier.py sdk/python/src/attestplane/verify_errors.py sdk/python/src/attestplane/cli/main.py sdk/python/src/attestplane/cli/__main__.py sdk/python/src/attestplane/hashchain.py tests/verifier/test_proof_bundle_schema.py tests/verifier/test_conformance_fixtures.py attestplane/__init__.py
All checks passed!
```

```text
$ PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance/test_verifier_conformance.py -q
........                                                                 [100%]
8 passed in 0.04s
```

```text
$ PYTHONPATH=sdk/python/src pytest sdk/python/tests/cli/test_main.py sdk/python/tests/cli/test_verify_cli_deterministic_json.py sdk/python/tests/signing/test_verifier_ext.py sdk/python/tests/signing/test_proof_bundle_signatures.py -q
.................................                                        [100%]
SKIPPED [1] sdk/python/tests/signing/test_proof_bundle_signatures.py:24: could not import 'jsonschema': No module named 'jsonschema'
33 passed, 1 skipped in 0.09s
```

Blocked broader check:

```text
$ PYTHONPATH=sdk/python/src pytest sdk/python/tests/test_proof_bundle.py sdk/python/tests/cli/test_main.py sdk/python/tests/cli/test_verify_cli_deterministic_json.py sdk/python/tests/conformance/test_verifier_conformance.py -q
ERROR sdk/python/tests/test_proof_bundle.py
ModuleNotFoundError: No module named 'jsonschema'
```

Attempting to use `uv run` with cache redirected to `/tmp/uv-cache` could not fetch missing build/dev dependencies because network access is blocked in this runner:

```text
Failed to fetch: https://pypi.org/simple/hatchling/
Operation not permitted (os error 1)
```

Gate helper:

```text
$ run_gate attestplane
[run_gate] project dir not found: /Users/macworkers/attestplane
```
