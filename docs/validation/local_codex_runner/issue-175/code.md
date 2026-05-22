# Issue 175 Code Evidence

Plan ID: `e1a00e102aecf1fc`

## Changes

- Added `tests/canonicalization/test_canonicalization_properties.py`.
- Kept runtime canonicalization code unchanged.
- Kept verifier round-trip tests unchanged because `pytest tests/verifier -k round_trip` already selects the intended signed-schema regression tests.

## Coverage Added

- Positive conformance-vector idempotency: each emitted minimum bundle is canonicalized, reparsed from canonical JSON bytes, and canonicalized again.
- Table-driven idempotency over the documented accepted domain, including:
  - `None`, booleans, signed 64-bit integer boundaries, NFC strings with escaping, bytes, UTC datetimes, lists, nested dicts, tuples, and `SubjectRef`.
- Deterministic generated-domain idempotency without adding Hypothesis as a new dependency in this runner environment.
- Commutativity coverage for independent normalization stages:
  - recursive key sorting,
  - Unicode NFC validation,
  - number profile validation.
- Negative guards confirming non-NFC strings, out-of-range integers, and floats still raise `CanonicalizationError`.

## Idempotency Interpretation

`canonicalize()` returns `bytes`, and `bytes` are themselves a documented accepted input type that canonicalize as base64url JSON strings. Therefore direct `canonicalize(canonicalize(x)) == canonicalize(x)` would test payload bytes, not already-canonical JSON.

The implemented invariant is the closed canonical JSON form:

```python
first = canonicalize(x)
reparsed = json.loads(first.decode("utf-8"))
assert canonicalize(reparsed) == first
```

This preserves the issue intent while respecting the existing API contract.

## Scope Confirmation

No release workflow, publishing, tag, fixture-lock, schema-lock, or runtime canonicalization files were changed.
