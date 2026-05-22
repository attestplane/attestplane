# Issue 123 Code Evidence

Plan ID: `459c5d0725bd7460`

## Changed Files

- `sdk/python/src/attestplane/proof_bundle.py`
  - Added `ProofBundleError`, `EmptyProofBundleError`, and `IncompleteProofBundleError`.
  - Added `ProofBundleBuilder.minimal(subject_digest, signer)`.
  - Exported the new public symbols from module `__all__`.
- `sdk/python/src/attestplane/sdk/__init__.py`
  - Added the public SDK convenience namespace.
- `sdk/python/src/attestplane/sdk/bundle.py`
  - Added strict SDK verification helpers that raise typed proof-bundle errors.
- `sdk/python/src/attestplane/__init__.py`
  - Re-exported the typed proof-bundle errors from the root Python package.
- `sdk/python/src/attestplane/cli/main.py`
  - Prints `VERIFY_REQUIRED_FIELDS_MISSING` or `bundle.schema.incomplete` to stderr when strict `verify` mode fails with those codes.
- `api/public/python_v1.json`
  - Refreshed the Python public API manifest for the additive root exports.
- `api/public/py_ts_allowlist_v1.json`
  - Recorded Python-only typed exception exports as intentional SDK-language asymmetries.
- `tests/sdk/test_bundle_builder.py`
  - Covered `ProofBundleBuilder.minimal(...)` strict verification, public docstring, and typed input rejection.
- `tests/sdk/test_errors.py`
  - Covered SDK typed errors for empty and unsigned strict bundles.
- `tests/cli/test_verify_errors.py`
  - Covered CLI stderr error-code surfacing.
- `tests/conftest.py`
  - Added repository-local import setup for top-level issue tests.
- `docs/contributor/api-reference.md`
  - Documented the `attestplane.sdk` reference namespace stub.
- `docs/release-notes/v1.7.0.draft.md`
  - Added the one-line migration note for typed strict proof-bundle errors.

## Public API Additions

- `attestplane.sdk.ProofBundleBuilder`
- `attestplane.sdk.EmptyProofBundleError`
- `attestplane.sdk.IncompleteProofBundleError`
- `attestplane.sdk.ProofBundleError`
- `attestplane.sdk.verify_minimum_bundle`
- `attestplane.sdk.verify_minimum_bundle_file`
- `attestplane.sdk.raise_for_minimum_bundle_result`
- Root exports for `EmptyProofBundleError`, `IncompleteProofBundleError`, and `ProofBundleError`.

No existing public symbol was removed or renamed.
