# Issue 172 Test Evidence

Plan ID: `89926bf04ae98019`

## Required / Focused Commands

- `env PYTHONPATH=sdk/python/src pytest tests/verifier -k reason_code -q`
  - PASS: `13 passed, 23 deselected`
- `env PYTHONPATH=sdk/python/src pytest tests/conformance -k negative -q`
  - PASS: `9 passed, 5 deselected`
- `env PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance/test_verifier_conformance.py -q`
  - PASS: `12 passed`
- `env PYTHONPATH=sdk/python/src pytest tests/verifier/test_proof_bundle_schema.py tests/verifier/test_conformance_fixtures.py -q`
  - PASS: `9 passed`
- `env PYTHONPATH=sdk/python/src pytest tests/cli/test_verify_errors.py tests/cli/test_verify_flags.py sdk/python/tests/cli/test_verify_errors.py sdk/python/tests/cli/test_verify_cli_deterministic_json.py -q`
  - PASS: `10 passed`
- `env PYTHONPATH=sdk/python/src pytest sdk/python/tests/test_public_api_manifest.py -q`
  - PASS: `5 passed`
- `env PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance/test_verifier_conformance.py tests/conformance/test_negative_minimum_schema_vectors.py -q`
  - PASS: `17 passed`
- `npm test -- --run verify_reason_codes verifier`
  - PASS: `5 passed` test files, `40 passed` tests.
  - Note: the local shell printed a non-test warning about being unable to
    open a starship session log under `/Users/macworkers/.cache`; Vitest still
    exited 0.
- `./scripts/check-public-api.sh`
  - PASS: `python=156 symbols, typescript=221 exports, allowlist=157 asymmetries`
- `python scripts/conformance/verify_fixture_lock.py`
  - PASS: `Conformance fixtures: 24 files, all canonical hashes match`
- `./scripts/check-fixture-hashes.sh`
  - PASS: `Conformance fixtures: 24 files, all canonical hashes match`
- `ruff check sdk/python/src/attestplane/verify_reason_codes.py sdk/python/src/attestplane/verifier.py tests/verifier/test_verify_reason_codes.py`
  - PASS: `All checks passed!`
- `git diff --check`
  - PASS

## `verify --json` Negative-Vector Smoke

The issue text lists:

```sh
python -m attestplane.cli verify --json fixtures/conformance/negative/*.json
```

This checkout does not have `fixtures/conformance/negative/*.json`, and the
local public negative fixtures are wrapper vectors under
`tests/conformance/vectors/negative/*.json`. Passing multiple wrapper-vector
paths directly to the current CLI also exits 2 because `attestplane verify`
accepts one proof-bundle path at a time.

Per the plan's stub/internal-helper allowance, I ran an internal helper that:

1. Loaded each local negative wrapper vector.
2. Wrote the embedded `bundle` to a temporary proof-bundle JSON file.
3. Invoked `attestplane.cli.main(["verify", "--json", ...])` with the vector's
   local verification options.
4. Asserted `ok`, `error_code`, `primary_reason`, and `secondary_reasons`.

Command:

```sh
env PYTHONPATH=sdk/python/src python - <<'PY'
...
PY
```

PASS summary:

```json
[
  {
    "case_id": "attestation-missing-signature",
    "primary_reason": "att.verify.required_field_missing",
    "rc": 2
  },
  {
    "case_id": "attestation-missing-subject-digest",
    "primary_reason": "att.verify.required_field_missing",
    "rc": 2
  },
  {
    "case_id": "attestations-array-empty",
    "primary_reason": "att.verify.signature_missing",
    "rc": 2
  },
  {
    "case_id": "empty-bundle",
    "primary_reason": "att.verify.required_field_missing",
    "rc": 2
  }
]
```

## Local Gate Probe

- `run_gate attestplane`
  - BLOCKED in this runner checkout: `[run_gate] project dir not found: /Users/macworkers/attestplane`
  - No release gate was weakened or bypassed; focused verifier, conformance,
    CLI, public API, TypeScript, and fixture-lock checks above were run.
