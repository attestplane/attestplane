# Issue 184 Code Evidence

Plan ID: `c9d0b702084eb09c`

## Summary

Implemented a versioned negative canonicalization corpus under `tests/conformance/vectors/canonicalization/negative/v1/`, a shared lightweight classifier/runner in `sdk/python/src/attestplane/conformance/`, and test coverage that asserts both `expected.reason_code` and `expected.pointer` for each vector.
Also updated the fixture hash gate so it can hash the unpaired-surrogate text fixture without crashing, then regenerated `sdk/python/tests/conformance/FIXTURE_HASHES.lock` to include the new `v1/` negative corpus entries.

## Files Changed

- `sdk/python/src/attestplane/conformance/__init__.py`
  - Added the conformance package namespace so `python -m attestplane.conformance.run` resolves locally.
  - Kept the package import surface lightweight to avoid pulling signing extras into the runner path.
- `sdk/python/src/attestplane/conformance/negative_vectors.py`
  - Added the shared negative-vector loader and classifier.
  - Classifies JSON and text canonicalization negatives, including duplicate keys, NFC violations, non-minimal numbers, leading-zero numbers, key-order mismatches, trailing whitespace, schema-version mismatch, embedded NULs, and unpaired surrogates.
- `sdk/python/src/attestplane/conformance/run.py`
  - Added the `--negative` local runner used by the issue validation command.
- `tests/conformance/vectors/canonicalization/negative/v1/*.json`
  - Added nine versioned negative vectors with stable `case_id`, `expected.reason_code`, and `expected.pointer`.
- `tests/conformance/test_negative_vectors.py`
  - Added the dedicated negative-vector harness that asserts the complete versioned corpus and verifies each vector’s reason code and pointer.
- `tests/canonicalization/test_canonicalization_properties.py`
  - Added a property-suite hook that references the negative corpus by `case_id` so named vectors show up in selector output.
- `tests/sdk/test_canonicalization_property.py`
  - Added a compatibility selector for the requested `tests/sdk/...` validation path.
- `tests/conformance/README.md`
  - Documented the versioned `negative/v1/` corpus and the reason-code/pointer assertions.
- `scripts/check-fixture-hashes.sh`
  - Switched the canonical JSON digest path to `surrogatepass` encoding so the lock gate can process the invalid-surrogate fixture deterministically.
- `sdk/python/tests/conformance/FIXTURE_HASHES.lock`
  - Regenerated the lock to include the versioned canonicalization negative fixtures in `tests/conformance/vectors/canonicalization/negative/v1/`.

## Scope Notes

- No runtime verifier logic changed.
- No release workflow, publishing workflow, tagging, or package metadata changed.
- Existing minimum-bundle canonicalization vectors and their harness remain intact.
