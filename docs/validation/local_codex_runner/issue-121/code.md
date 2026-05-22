# Issue 121 Code Evidence

Plan ID: `bcea17ac4c19edbd`

Implemented in this runner phase:

- Added strict proof-bundle schema enforcement in `sdk/python/src/attestplane/verifier.py`.
  - `require_signed_attestation=True` requires at least one syntactically valid signature record.
  - `require_non_empty=True` now layers this signed-attestation schema gate on top of the existing non-empty event check.
  - The existing empty-event strict failure keeps `VERIFY_REQUIRED_FIELDS_MISSING`.
  - Non-empty bundles without a usable signed attestation return `bundle.schema.incomplete`.
  - The schema gate is pre-crypto and uses local shape validation only; it does not require the optional `[signing]` extras or perform cryptographic signature verification.
- Added stable verifier error code `bundle.schema.incomplete` in `sdk/python/src/attestplane/verify_errors.py`.
- Added `verify --bundle <path>` CLI compatibility in `sdk/python/src/attestplane/cli/main.py`.
  - This path enables strict proof-bundle schema mode without changing legacy positional `verify <bundle>` behavior.
- Added `sdk/python/src/attestplane/cli/__main__.py` so `python -m attestplane.cli ...` works.
- Added a repository-root import shim at `attestplane/__init__.py` so local root-level `python -m attestplane.cli ...` can resolve the SDK source tree without an editable install.
- Made `uuid_utils` a producer-path lazy import in `sdk/python/src/attestplane/hashchain.py`, so read-only verifier/CLI imports do not require the event-id generation dependency before command dispatch.
- Added negative and positive fixtures under `tests/fixtures/bundles/`:
  - `empty_attestations.json`
  - `missing_signatures.json`
  - `malformed_signature.json`
  - `signature_digest_mismatch.json`
  - `valid_signed_attestation.json`
- Added focused issue tests under `tests/verifier/`.

Canonicalization note:

- No canonicalization code or existing conformance fixture JSON was changed.
- The new schema gate compares signature subject digests against `hash_event(event.event)`, reusing the existing canonical event digest recipe.
