# Issue 184 Validation Evidence

Plan ID: `c9d0b702084eb09c`

## Commands

```bash
PYTHONPATH=sdk/python/src pytest tests/conformance/test_negative_vectors.py -q
PYTHONPATH=sdk/python/src pytest tests/sdk/test_canonicalization_property.py -q
PYTHONPATH=sdk/python/src python -m attestplane.conformance.run --negative
PYTHONPATH=sdk/python/src pytest tests/conformance/test_canonicalization_minimum_bundle_vectors.py -q
PYTHONPATH=sdk/python/src pytest tests/canonicalization/test_canonicalization_properties.py -q
./scripts/check-fixture-hashes.sh
env PYTHONPATH=sdk/python/src /Users/macworkers/Projects/attestplane/sdk/python/.venv/bin/pytest tests/verifier/test_proof_bundle_schema.py tests/verifier/test_conformance_fixtures.py -q
env PYTHONPATH=sdk/python/src /Users/macworkers/Projects/attestplane/sdk/python/.venv/bin/pytest sdk/python/tests/conformance/test_verifier_conformance.py -q
```

## Results

- `pytest tests/conformance/test_negative_vectors.py -q` → PASS
  - `11 passed in 0.07s`
- `pytest tests/sdk/test_canonicalization_property.py -q` → PASS
  - `82 passed in 0.10s`
- `python -m attestplane.conformance.run --negative` → PASS
  - Exit code `0`
  - Classified all nine versioned negative vectors:

```text
canonicalization-negative-duplicate-json-keys-v1: att.verify.structure_invalid /subject_digest
canonicalization-negative-embedded-nul-string-v1: att.verify.schema_invalid /
canonicalization-negative-invalid-surrogate-pair-string-v1: att.verify.schema_invalid /
canonicalization-negative-leading-zero-number-v1: att.verify.schema_invalid /value
canonicalization-negative-non-minimal-number-v1: att.verify.canonical_mismatch /value
canonicalization-negative-non-nfc-string-v1: att.verify.canonical_mismatch /payload_text
canonicalization-negative-non-sorted-object-keys-v1: att.verify.canonical_mismatch /
canonicalization-negative-schema-version-mismatch-v1: att.verify.schema_version_unsupported /schema_version
canonicalization-negative-trailing-whitespace-v1: att.verify.canonical_mismatch /
```

- `pytest tests/conformance/test_canonicalization_minimum_bundle_vectors.py -q` → PASS
  - `8 passed in 0.05s`
- `pytest tests/canonicalization/test_canonicalization_properties.py -q` → PASS
  - `82 passed in 0.11s`
- `./scripts/check-fixture-hashes.sh` → PASS
  - `Conformance fixtures: 33 files, all canonical hashes match ✓`
- `pytest tests/verifier/test_proof_bundle_schema.py tests/verifier/test_conformance_fixtures.py -q` → PASS
  - `9 passed in 0.52s`
- `pytest sdk/python/tests/conformance/test_verifier_conformance.py -q` → PASS
  - `12 passed in 0.12s`

## Notes

- The requested `tests/sdk/test_canonicalization_property.py` selector resolves through the compatibility wrapper.
- The new versioned corpus and the property-suite hook both reference vectors by `case_id`, which keeps failing examples named instead of anonymous.
