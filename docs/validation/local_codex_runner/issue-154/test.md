# Issue 154 Test Evidence

Plan ID: `e2e4a0599bd4718a`

## Focused Verifier Round Trip

Command:

```bash
PYTHONPATH=sdk/python/src pytest tests/verifier/test_signed_schema_roundtrip.py -vv
```

Result: PASS, `14 passed in 0.06s`.

Visible vector IDs in output:

- `canonicalization-positive-canonical-json-no-bom-trailing`
- `canonicalization-positive-duplicate-json-keys-helper-control`
- `canonicalization-positive-int64-boundary-timestamp-payload`
- `canonicalization-positive-nfc-payload-string`
- `canonicalization-negative-bom-trailing-bytes-raw`
- `canonicalization-negative-duplicate-json-keys-raw`
- `canonicalization-negative-int64-overflow-timestamp-payload`
- `canonicalization-negative-nfd-payload-string`

The original locked fixture remains covered as `valid_signed_attestation.json`.

## Focused Canonicalization Conformance

Command:

```bash
PYTHONPATH=sdk/python/src pytest tests/conformance/test_canonicalization_minimum_bundle_vectors.py -vv
```

Result: PASS, `8 passed in 0.05s`.

## Full Local Conformance Directory

Command:

```bash
PYTHONPATH=sdk/python/src pytest tests/conformance -q
```

Result: PASS, `14 passed in 0.06s`.

## Fixture Lock

Command:

```bash
python scripts/conformance/verify_fixture_lock.py
```

Result: PASS, `Conformance fixtures: 24 files, all canonical hashes match`.

## Related Verifier Regressions

Command:

```bash
PYTHONPATH=sdk/python/src pytest tests/verifier/test_proof_bundle_schema.py tests/verifier/test_conformance_fixtures.py -q
```

Result: PASS, `9 passed in 0.63s`.

## Manifest Grep

Command:

```bash
git grep -n "canonicalization" tests/verifier
```

Result:

```text
tests/verifier/test_signed_schema_roundtrip.py:32:from tests.conformance import canonicalization_vectors as vector_manifest
```

This leaves one verifier-side manifest import site.

## Repository Gate

Command:

```bash
run_gate attestplane
```

Result: FAIL before tests started.

```text
[run_gate] project dir not found: /Users/macworkers/attestplane
```

The gate wrapper exists at `/Users/macworkers/.local/bin/run_gate`, but its `attestplane` project mapping points outside this local runner checkout. The focused verifier/conformance commands above were run instead without weakening any gate or skipping any failing test.
