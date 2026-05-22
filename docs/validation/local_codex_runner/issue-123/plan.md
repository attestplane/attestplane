# Issue 123 Implementation Plan

Plan ID: `459c5d0725bd7460`

## Scope

Implement an additive SDK path for creating a minimum-valid proof bundle and expose typed SDK/CLI errors for the strict proof-bundle incompleteness rejection introduced by the Issue 1 verifier work.

This runner phase used only local repository files, local command output, and the issue text. The project-level Opus consultation requirement is not executed in this phase because the runner prompt explicitly forbids external advisory services.

## Current Local Findings

- `sdk/python/src/attestplane/proof_bundle.py` owns `ProofBundleBuilder`, signature serialization, and the module `__all__`.
- `sdk/python/src/attestplane/verifier.py` already has the strict minimum signed-attestation schema path, returning `VERIFY_BUNDLE_SCHEMA_INCOMPLETE` (`"bundle.schema.incomplete"`) through `BundleVerificationResult.error_code`.
- `sdk/python/src/attestplane/verify_errors.py` already defines the machine-readable incomplete-bundle code, but there is no typed `EmptyProofBundleError` / `IncompleteProofBundleError` SDK exception yet.
- `sdk/python/src/attestplane/cli/main.py` currently emits verify failures through `_emit(...)`, which writes human output to stdout. The issue requires the matching error code on stderr for the new rejection.
- There is currently no `sdk/python/src/attestplane/sdk/` package. Existing public Python exports are rooted at `attestplane`, `attestplane.proof_bundle`, and related modules.
- The requested validation paths `tests/sdk/test_bundle_builder.py`, `tests/sdk/test_errors.py`, and `tests/cli/test_verify_errors.py` do not exist yet in this checkout; current Python tests live primarily under `sdk/python/tests/...`.
- The API reference docs stub is `docs/contributor/api-reference.md`; rendered reference material is generated from public symbols/docstrings.

## Implementation Approach

1. Add typed SDK exceptions without replacing existing verifier classes.
   - Introduce `EmptyProofBundleError` and `IncompleteProofBundleError` in a public SDK-facing module.
   - Keep `BundleSchemaError` / `BundleVerificationError` intact for schema and I/O failures.
   - Map verifier result failures as follows for SDK convenience paths:
     - zero-event strict rejection -> `EmptyProofBundleError`;
     - signed-attestation schema rejection -> `IncompleteProofBundleError`;
   - Ensure each typed error carries or exposes the stable verifier error code (`VERIFY_REQUIRED_FIELDS_MISSING` or `VERIFY_BUNDLE_SCHEMA_INCOMPLETE`) so CLI and SDK callers do not parse message text.

2. Add the public SDK namespace expected by the issue.
   - Create `sdk/python/src/attestplane/sdk/__init__.py` and likely `sdk/python/src/attestplane/sdk/bundle.py`.
   - Re-export `ProofBundleBuilder`, `EmptyProofBundleError`, and `IncompleteProofBundleError` from `attestplane.sdk`.
   - Keep existing imports from `attestplane` and `attestplane.proof_bundle` working; do not remove or rename public symbols.
   - Add the new public names to relevant `__all__` lists: `attestplane.sdk`, `attestplane.sdk.bundle`, `attestplane.proof_bundle` if the builder-owned exceptions live there, and root `attestplane` if the project wants root-level parity for public Python APIs.

3. Add `ProofBundleBuilder.minimal(subject_digest, signer)`.
   - Implement as an additive classmethod or staticmethod on the existing `ProofBundleBuilder`.
   - Validate `subject_digest` as a lowercase 64-hex digest and fail with the typed SDK error hierarchy, not generic `ValueError`, for minimum-bundle construction failures.
   - Build exactly one deterministic minimal event and one syntactically valid signature record so the resulting bundle passes:
     - `verify_proof_bundle(bundle, require_non_empty=True)`;
     - `verify_proof_bundle(bundle, require_signed_attestation=True)`;
     - JSON schema validation against `schemas/v1/proof_bundle.schema.json`.
   - Prefer the existing signing API when `signer` is an `attestplane.signing.Signer`: use `sign_event(...)` for a per-event signature, then adapt any digest mismatch against the current strict schema checker deliberately and in tests.
   - If the accepted contract treats `subject_digest` as an external artifact digest rather than the canonical event digest, document the exact field placement in the method docstring and keep the verifier-facing signed digest tied to the canonical bundle event hash.
   - Add a docstring stating the v1.7.x stability guarantee: the method remains additive, the returned bundle shape stays minimum-valid for v1.7.x strict verification, and existing public symbols remain compatible.

4. Surface typed errors through SDK verification helpers.
   - Add a small SDK-facing helper if needed, for example `verify_minimum_bundle(...)`, that wraps `verify_proof_bundle(...)` / `verify_proof_bundle_file(...)` and raises `EmptyProofBundleError` or `IncompleteProofBundleError` based on `BundleVerificationResult.error_code`.
   - Keep the lower-level verifier result API stable; do not convert `verify_proof_bundle(...)` itself to raising typed errors unless tests prove that is the accepted public contract.

5. Update CLI error surfacing for the new rejection.
   - In `cmd_verify`, when `result.ok` is false and `result.error_code` is `VERIFY_BUNDLE_SCHEMA_INCOMPLETE` or `VERIFY_REQUIRED_FIELDS_MISSING`, print the exact error code to stderr and return non-zero.
   - Preserve existing JSON stdout structure for `--json`; add stderr code output only where the issue requires it.
   - Do not weaken the existing strict `--bundle` behavior.

6. Update docs and release-note evidence.
   - Update `docs/contributor/api-reference.md` only as a stub/reference workflow note if needed; primary rendered docs should come from new docstrings and `__all__`.
   - Add a release-note entry under `docs/release-notes/` or the current release-note file used by this train, mentioning the migration path from generic errors to `EmptyProofBundleError` / `IncompleteProofBundleError`.

## Files Likely To Change

- `sdk/python/src/attestplane/proof_bundle.py`
- `sdk/python/src/attestplane/verifier.py` if SDK wrappers need a shared mapping helper
- `sdk/python/src/attestplane/verify_errors.py` only if an additional error constant/export is needed
- `sdk/python/src/attestplane/cli/main.py`
- `sdk/python/src/attestplane/__init__.py`
- `sdk/python/src/attestplane/sdk/__init__.py` (new)
- `sdk/python/src/attestplane/sdk/bundle.py` (new)
- `sdk/python/tests/test_import_surface.py`
- `sdk/python/tests/test_proof_bundle.py` or new top-level compatibility tests
- `sdk/python/tests/cli/test_main.py`
- `tests/sdk/test_bundle_builder.py` (new, issue-requested path)
- `tests/sdk/test_errors.py` (new, issue-requested path)
- `tests/cli/test_verify_errors.py` (new, issue-requested path)
- `api/public/python_v1.json` if the public API manifest gate expects checked-in updates
- `docs/contributor/api-reference.md`
- `docs/release-notes/*.md` for the one-line migration note

## Tests And Local Gates

Issue-required targeted validation:

```bash
pytest tests/sdk/test_bundle_builder.py tests/sdk/test_errors.py -q
pytest tests/cli/test_verify_errors.py -q
python -c "from attestplane.sdk import ProofBundleBuilder; ProofBundleBuilder.minimal.__doc__"
```

Existing local coverage to keep green:

```bash
pytest sdk/python/tests/test_proof_bundle.py -q
pytest sdk/python/tests/cli/test_main.py -q
pytest sdk/python/tests/test_import_surface.py -q
pytest sdk/python/tests/test_public_api_manifest.py -q
pytest sdk/python/tests/signing/test_signer.py sdk/python/tests/signing/test_proof_bundle_signatures.py -q
```

Public API and schema checks:

```bash
python scripts/api/extract_python_public_api.py
python scripts/api/check_public_api_manifest.py
python scripts/check-schema-hashes.sh
```

Local gate before closure:

```bash
run_gate attestplane
```

If `run_gate attestplane` is unavailable in this checkout, record that fact in the test evidence and run the closest local Python gate from `sdk/python/pyproject.toml` without weakening the required release gates.

## Risk Classification

P1, medium risk.

The change is additive, but it touches public SDK imports, verifier error taxonomy, and CLI output streams. The main compatibility risk is accidentally changing existing `ProofBundleBuilder.build()` output or forcing strict signed-attestation semantics onto legacy chain/report-only verification. The mitigation is to keep the new minimal builder and typed-error raising path opt-in while preserving existing verifier result APIs and root public symbols.

There is a smaller signing-contract risk because the current strict schema helper compares signature `signed_event_hash_hex` to canonical event hashes, while the existing `Signer.sign_event(...)` records the chain event hash. Implementation should either adapt the minimal builder output to the current verifier contract with explicit tests or first reconcile that mismatch locally without changing canonicalization.

## Evidence Files To Update

- `docs/validation/local_codex_runner/issue-123/plan.md` for this planning phase.
- `docs/validation/local_codex_runner/issue-123/code.md` in the implementation phase, listing changed files and public API additions.
- `docs/validation/local_codex_runner/issue-123/test.md` in the validation phase, with exact command outputs and any unavailable gate notes.
- `docs/validation/local_codex_runner/issue-123/review.md` in the review phase, including public API and CLI stderr checks.
- Release-note evidence under the active `docs/release-notes/` file for the v1.7.x migration note.

## Safety Confirmation

This task will not merge branches, create or move tags, publish npm packages, publish PyPI packages, push to PyPI, push to any remote, or weaken release gates. It will not lower P1 severity, remove failing tests to manufacture a pass, loosen claim-safety policy, or read/log credentials files such as ChatGPT cookies, GitHub tokens, OpenAI tokens, private keys, `.pypirc`, or `.npmrc`.
