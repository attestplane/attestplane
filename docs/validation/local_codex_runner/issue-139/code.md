# Issue 139 Code Evidence

Plan ID: `2e8af61f69ea41f4`

## Files Changed

- `tests/verifier/test_signed_schema_roundtrip.py`
  - Added a signed-schema round-trip regression for `valid_signed_attestation.json`.
  - Rehydrates locked fixture events through the SDK JSONL event deserializer.
  - Rebuilds the bundle through `ProofBundleBuilder`, preserving the fixture's frozen `verified_at` and `verifier_version` metadata.
  - Replays the locked synthetic signature record through a deterministic test signer and SDK signature serialization.
  - Compares rebuilt vs locked JSON with field-level JSON-pointer diagnostics before asserting canonical byte equality.
  - Verifies the rebuilt bundle with `require_non_empty=True` and `require_signed_attestation=True`.

- `tests/conformance/test_signed_schema_conformance_roundtrip.py`
  - Added a positive `signed_schema` conformance selector so `pytest tests/conformance -k signed_schema -x` exercises the strict positive fixture path.
  - Renamed from the original same-basename selector to avoid pytest import-file mismatch when collected with `tests/verifier/test_signed_schema_roundtrip.py`.

## Scope Notes

- No runtime verifier or SDK production code changed.
- No fixture JSON, fixture hash lock, schema, release workflow, publish workflow, tag, or package manifest changed.
- The locked fixture's `verification_report.verifier_version` is frozen during rebuild for deterministic comparison because the current local package version differs from the historic fixture metadata.
