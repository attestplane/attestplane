# Issue 138 Implementation Plan

Plan ID: `ea2324f7e1effb2e`

## Scope

Expose explicit `attestplane verify <bundle>` opt-in flags for the v1.7.0 proof-bundle contract:

- `--require-non-empty`: fail closed when a proof bundle has zero events.
- `--strict-schema`: fail closed on the minimum signed-attestation schema contract.

Defaults must preserve current `attestplane verify <bundle>` behavior. This runner phase used only local repository files, local command output, and the issue text. The project-level Opus consultation requirement is not executed in this phase because the runner prompt explicitly forbids external advisory services.

## Current Local Findings

- Runtime enforcement already exists in `sdk/python/src/attestplane/verifier.py`:
  - `verify_proof_bundle(..., require_non_empty=True)`
  - `verify_proof_bundle(..., require_signed_attestation=True)`
  - `verify_proof_bundle_file(...)` forwards both options.
- Current CLI wiring in `sdk/python/src/attestplane/cli/main.py` has older names/behavior:
  - `--require-events` maps to `require_non_empty`.
  - `--bundle PATH` enables implicit strict proof-bundle schema mode.
  - schema/non-empty violations currently return `1`, even when `error_code` is `VERIFY_REQUIRED_FIELDS_MISSING` or `VERIFY_BUNDLE_SCHEMA_INCOMPLETE`.
- Existing CLI tests in both `tests/cli/test_verify_errors.py` and `sdk/python/tests/cli/test_verify_errors.py` assert the current `rc == 1` behavior for strict schema/non-empty failures, so the implementation must update or replace those expectations intentionally.
- Existing positive/negative strict-schema fixtures are under `tests/fixtures/bundles/`:
  - `valid_signed_attestation.json`
  - `empty_attestations.json`
  - `missing_signatures.json`
  - `malformed_signature.json`
  - `signature_digest_mismatch.json`
- The issue validation names `tests/fixtures/empty_bundle.json` and `tests/fixtures/v1.7.0_signed.json`, but those exact files are not present locally. The implementation should either add compatibility fixture aliases at those paths or adjust validation evidence to the local fixture names only if the issue owner accepts that deviation. Preferred path: add small canonical fixture files/aliases matching the issue commands.

## Implementation Approach

1. Add explicit CLI flags.
   - In `build_parser()` for `verify`, add `--require-non-empty` and `--strict-schema`.
   - Help text must be one-line and reference the proof-bundle contract, for example:
     - `--require-non-empty`: "enforce the proof-bundle contract that strict bundles contain at least one event"
     - `--strict-schema`: "enforce the proof-bundle contract's minimum signed-attestation schema"
   - Keep `--require-events` as a backward-compatible alias unless a separate deprecation issue removes it.
   - Keep `--bundle PATH` behavior for compatibility, but prefer the positional `bundle` plus explicit flags in new tests/docs.

2. Wire flags to verifier runtime without changing defaults.
   - Compute `require_non_empty = args.require_non_empty or args.require_events or strict_bundle_mode`.
   - Compute `require_signed_attestation = args.strict_schema or strict_bundle_mode`.
   - Do not make `--strict-schema` automatically imply non-empty unless the runtime already requires events for signed-attestation validation. This preserves the two explicit knobs while still producing a schema failure for an empty bundle under strict schema because no signed attestation can be valid without events.
   - Keep the JSON payload fields stable, but consider adding `require_non_empty` and `strict_schema` while preserving existing `require_events` / `strict_proof_bundle_schema` fields if downstream tests depend on them.

3. Implement required exit code distinction.
   - `0`: `result.ok is True`.
   - `2`: verifier result is not ok because of schema/non-empty contract violations, specifically `VERIFY_REQUIRED_FIELDS_MISSING` or `VERIFY_BUNDLE_SCHEMA_INCOMPLETE`, and malformed JSON / `BundleSchemaError` from shape validation.
   - `1`: cryptographic or chain-integrity verification failure, I/O failure, or other verifier failure outside the schema/non-empty contract.
   - Because current `verify` does not perform real cryptographic verification, document `1` as the reserved failure bucket for cryptographic/chain failures and keep existing chain/tamper failures returning `1`.

4. Add focused CLI integration coverage.
   - Create `tests/cli/test_verify_flags.py`.
   - Cover defaults: valid bundle succeeds without flags; invalid/empty bundle preserves current non-strict behavior without `--require-non-empty`.
   - Cover `--require-non-empty`: valid signed bundle succeeds; empty bundle exits `2`.
   - Cover `--strict-schema`: signed valid bundle exits `0`; missing/malformed unsigned schema fixture exits `2`.
   - Cover combined flags: valid signed bundle exits `0`; empty or unsigned invalid bundle exits `2`.
   - Add a help-output assertion that `main(["verify", "--help"])` or parser formatting includes both new flags and the proof-bundle contract rationale.

5. Add or reconcile issue-named fixtures.
   - Preferred: add `tests/fixtures/empty_bundle.json` and `tests/fixtures/v1.7.0_signed.json` by reusing the current local bundle shapes from `tests/fixtures/bundles/empty_attestations.json` / `valid_signed_attestation.json`, with `empty_bundle.json` adjusted to truly contain zero events if needed for the exact validation command.
   - If duplicating fixtures is considered undesirable, update the implementation evidence to state the exact local alternative commands and why the issue paths are absent. Do not silently skip the issue-required commands.

6. Update user-facing docs/changelog.
   - Update `CHANGELOG.md` under `Unreleased` / `Conformance` with a short rollout note: downstream automation can adopt `attestplane verify --require-non-empty` and `--strict-schema` now before they become default in a future `x.0.0`.
   - Update CLI docstring/help comments in `sdk/python/src/attestplane/cli/main.py` to document exit codes `0`, `2`, and `1`.
   - If there is an existing CLI reference document discovered during implementation, update it too; otherwise keep the documentation surface to CLI help and changelog.

## Files Likely To Change

- `sdk/python/src/attestplane/cli/main.py`
- `tests/cli/test_verify_flags.py` (new)
- `tests/cli/test_verify_errors.py`
- `sdk/python/tests/cli/test_verify_errors.py`
- `CHANGELOG.md`
- `tests/fixtures/empty_bundle.json` (new, if matching issue validation paths)
- `tests/fixtures/v1.7.0_signed.json` (new, if matching issue validation paths)
- `docs/validation/local_codex_runner/issue-138/code.md` in the implementation phase
- `docs/validation/local_codex_runner/issue-138/test.md` in the validation phase
- `docs/validation/local_codex_runner/issue-138/review.md` if a later review phase is run

Runtime verifier files should not need changes unless implementation uncovers a mismatch in `require_non_empty` / `require_signed_attestation` semantics.

## Tests And Local Gates

Issue-required validation:

```bash
PYTHONPATH=sdk/python/src pytest tests/cli/test_verify_flags.py -x
PYTHONPATH=sdk/python/src attestplane verify tests/fixtures/empty_bundle.json --require-non-empty; echo $?
PYTHONPATH=sdk/python/src attestplane verify tests/fixtures/v1.7.0_signed.json --strict-schema; echo $?
```

Focused existing checks:

```bash
PYTHONPATH=sdk/python/src pytest tests/cli/test_verify_errors.py sdk/python/tests/cli/test_verify_errors.py -q
PYTHONPATH=sdk/python/src pytest tests/verifier/test_proof_bundle_schema.py tests/conformance/test_negative_minimum_schema_vectors.py -q
PYTHONPATH=sdk/python/src pytest sdk/python/tests/cli/test_verify_cli_deterministic_json.py -q
```

Help and manual exit-code smoke checks:

```bash
PYTHONPATH=sdk/python/src attestplane verify --help
PYTHONPATH=sdk/python/src attestplane verify tests/fixtures/bundles/valid_signed_attestation.json --strict-schema; echo $?
PYTHONPATH=sdk/python/src attestplane verify tests/fixtures/bundles/missing_signatures.json --strict-schema; echo $?
```

Local gate before closure:

```bash
run_gate attestplane
```

If `run_gate attestplane` is unavailable in this checkout, record the exact failure in `test.md` and run the focused CLI/verifier/conformance commands above without weakening the required release gates.

## Risk Classification

P1, medium risk.

The code change is small, but it changes user-visible CLI exit-code semantics for the new strict opt-in paths and may require updating existing tests that currently assert `1` for schema/non-empty failures. The main compatibility risk is older `--require-events` / `--bundle` behavior; the implementation should preserve those aliases unless a separate issue authorizes removal. The main validation risk is fixture naming: the issue references two fixture paths that are absent locally, so the implementation should add stable aliases rather than changing the acceptance command shape.

## Evidence Files To Update

- `docs/validation/local_codex_runner/issue-138/plan.md` for this planning phase.
- `docs/validation/local_codex_runner/issue-138/code.md` in the implementation phase, listing exact code, fixture, and documentation files changed.
- `docs/validation/local_codex_runner/issue-138/test.md` in the validation phase, with exact command outputs and exit codes for the issue-required commands.
- `docs/validation/local_codex_runner/issue-138/review.md` in the review phase if review is run.
- `docs/validation/local_codex_runner/issue-138/gate_report.md` / `.json` if the local runner phase records gate output in the same format as nearby issues.

Do not update release artifacts, signed checksums, package manifests, schema locks, or fixture hash locks unless a later implementation phase deliberately adds public conformance fixtures and records the required lock update.

## Safety Confirmation

This task will not merge branches, create tags, move tags, publish npm packages, publish PyPI packages, push to PyPI, push to any remote, or weaken release gates. It will not lower P0/P1 severity, remove failing tests to manufacture a pass, loosen release gates, loosen claim-safety policy, or read/log credentials files such as ChatGPT cookies, GitHub tokens, OpenAI tokens, private keys, `.pypirc`, or `.npmrc`.
