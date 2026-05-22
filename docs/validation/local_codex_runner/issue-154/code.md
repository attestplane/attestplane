# Issue 154 Code Evidence

Plan ID: `e2e4a0599bd4718a`

## Summary

Implemented the signed-schema round-trip regression expansion using a shared local test helper for the canonicalization vector manifest.

## Files Changed

- `tests/conformance/canonicalization_vectors.py`
  - Added the shared canonicalization vector loader for positive and negative vectors.
  - Added deterministic minimum-bundle emission for positive vectors.
  - Added shared negative-vector materialization and duplicate-key rejection helpers.
- `tests/conformance/test_canonicalization_minimum_bundle_vectors.py`
  - Replaced local vector directory constants, JSON globbing, signer setup, positive bundle emission, and negative mutation materialization with the shared helper.
  - Preserved the existing positive and negative behavior and vector-id parametrization.
- `tests/verifier/test_signed_schema_roundtrip.py`
  - Added generated positive canonicalization vector bundles to the signed-schema byte-identical round-trip cases.
  - Added vector-id-tagged assertion messages for structural, canonical JSON byte, and strict verifier contract failures.
  - Added negative canonicalization vectors as verifier-side strict reject cases so `-vv` output enumerates all eight issue #150 vector IDs without treating malformed inputs as round-trip fixtures.

## Scope Notes

- No runtime SDK/verifier implementation files changed.
- No release workflow, publish workflow, tag, package manifest, or fixture JSON file changed.
- No fixture lock churn was introduced; the shared manifest is Python test infrastructure, not a new locked JSON fixture.

## Manifest Loading

The verifier now imports the shared manifest once:

```text
tests/verifier/test_signed_schema_roundtrip.py:32:from tests.conformance import canonicalization_vectors as vector_manifest
```

The conformance test and verifier test both consume `tests/conformance/canonicalization_vectors.py`; there is no parallel hard-coded vector-id list in the verifier.
