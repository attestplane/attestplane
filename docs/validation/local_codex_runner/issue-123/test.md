# Issue 123 Test Evidence

Plan ID: `459c5d0725bd7460`

## Required Validation

```text
$ pytest tests/sdk/test_bundle_builder.py tests/sdk/test_errors.py -q
........                                                                 [100%]
8 passed in 0.11s
```

```text
$ pytest tests/cli/test_verify_errors.py -q
..                                                                       [100%]
2 passed in 0.10s
```

```text
python -c "from attestplane.sdk import ProofBundleBuilder; ProofBundleBuilder.minimal.__doc__"
```

Exit status: `0`.

## Existing Local Coverage

```text
$ PYTHONPATH=sdk/python/src pytest sdk/python/tests/cli/test_main.py sdk/python/tests/test_import_surface.py sdk/python/tests/signing/test_signer.py -q
.............................................                            [100%]
45 passed in 0.19s
```

```text
$ PYTHONPATH=sdk/python/src pytest sdk/python/tests/test_sdk_bundle.py sdk/python/tests/cli/test_verify_errors.py -q
..........                                                               [100%]
10 passed
```

```text
$ cd sdk/python && uv run ruff check src tests
All checks passed!
```

```text
$ cd sdk/python && uv run mypy
Success: no issues found in 51 source files
```

```text
$ cd sdk/python && uv run pytest --cov --cov-report=term --cov-fail-under=87
985 passed in 19.95s
Required test coverage of 87% reached. Total coverage: 87.20%
```

```text
$ npx markdownlint-cli2 "docs/validation/local_codex_runner/issue-123/*.md" "!.github/**"
Summary: 0 error(s)
```

```text
$ scripts/check-public-api.sh
Public API manifest check PASS: python=141 symbols, typescript=206 exports, allowlist=153 asymmetries
```

```text
$ run_gate Projects/attestplane
[run_gate] Projects/attestplane / fast: pytest -q tests/
160 passed in 9.37s
{"project":"Projects/attestplane","mode":"fast","sha":"7ce21f0","result":"PASS","duration_seconds":9,"report":""}
```

## Runner Recovery Validation

The first automated runner pass exposed a local gate-matrix parser/configuration bug before PR creation:

- fallback YAML parsing did not support label keys containing `:`, such as `area:verifier:`;
- the local `area:verifier` gate matrix pointed at stale test paths.

Both were corrected and validated:

```text
$ pytest tests/local_codex_runner/test_config.py tests/local_codex_runner/test_gate_runner.py -q
..........                                                               [100%]
10 passed in 0.03s
```

```text
$ GateRunner(...).run(["area:verifier"], ...)
PASS: gate=area:verifier
- env PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance/test_verifier_conformance.py -q: exit=0
- env PYTHONPATH=sdk/python/src pytest tests/verifier/test_proof_bundle_schema.py tests/verifier/test_conformance_fixtures.py -q: exit=0
```

## Environment Notes

The bare runner interpreter does not have `jsonschema` installed, so broader tests that import `sdk/python/tests/test_proof_bundle.py` directly fail during collection before executing this issue's code path. The issue-required tests avoid that external dependency and validate strict proof-bundle acceptance through the local verifier. `run_gate attestplane` resolved to `/Users/macworkers/attestplane` and failed before execution; `run_gate Projects/attestplane` is the working local gate path for this checkout.
