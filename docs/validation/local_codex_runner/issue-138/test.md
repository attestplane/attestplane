# Issue 138 Validation Evidence

Plan ID: `ea2324f7e1effb2e`

## Required Test

Command:

```bash
PYTHONPATH=sdk/python/src pytest tests/cli/test_verify_flags.py -x
```

Result:

```text
5 passed in 0.05s
```

## Required Smoke: Empty Bundle

The `attestplane` console script is not installed in this shell, so the exact command shape returned `command not found` / `exit=127`. Equivalent local source invocation:

```bash
PYTHONPATH=sdk/python/src python -c 'import sys; from attestplane.cli.main import main; raise SystemExit(main(sys.argv[1:]))' verify tests/fixtures/empty_bundle.json --require-non-empty; printf 'exit=%s\n' $?
```

Result:

```text
VERIFY_REQUIRED_FIELDS_MISSING
FAIL chain_id='p3-cli-empty-proofbundle' events=0 first_bad_index=None reason=None agreement=True metadata_reason='events must contain at least one event when require_non_empty=True' policy_trace_refs_reason=None retention_proofs_reason=None signed_attestation_schema_reason='events must contain at least one event before signed-attestation schema can pass' error_code=VERIFY_REQUIRED_FIELDS_MISSING
MODE: chain/report-oriented, not a full verifier. This command replays bundle events, compares the embedded verification_report with the recomputed chain result, and fails closed on malformed ProofBundle metadata and policy_trace_refs closure. It does not perform signature verification, anchor verification, or compliance certification.
exit=2
```

## Required Smoke: Signed Bundle

Equivalent local source invocation:

```bash
PYTHONPATH=sdk/python/src python -c 'import sys; from attestplane.cli.main import main; raise SystemExit(main(sys.argv[1:]))' verify tests/fixtures/v1.7.0_signed.json --strict-schema; printf 'exit=%s\n' $?
```

Result:

```text
OK chain_id='p3-cli-proofbundle' events=1 head=<hex elided>
MODE: chain/report-oriented, not a full verifier. This command replays bundle events, compares the embedded verification_report with the recomputed chain result, and fails closed on malformed ProofBundle metadata and policy_trace_refs closure. It does not perform signature verification, anchor verification, or compliance certification.
exit=0
```

## Focused Regression Suite

Command:

```bash
PYTHONPATH=sdk/python/src pytest tests/cli/test_verify_errors.py sdk/python/tests/cli/test_verify_errors.py sdk/python/tests/cli/test_main.py tests/verifier/test_proof_bundle_schema.py -q
```

Result:

```text
30 passed in 0.14s
```

## Help Output Check

Command:

```bash
PYTHONPATH=sdk/python/src python -c 'import sys; from attestplane.cli.main import main; raise SystemExit(main(sys.argv[1:]))' verify --help | sed -n '1,120p'
```

Key output:

```text
usage: attestplane verify [-h] [--bundle BUNDLE_OPTION] [--require-events]
                          [--require-non-empty] [--strict-schema] [--json]
                          [bundle]
...
  --require-non-empty   enforce the proof-bundle contract that strict bundles
                        contain at least one event
  --strict-schema       enforce the proof-bundle contract's minimum signed-
                        attestation schema
...
Exit codes: 0 success; 2 proof-bundle contract schema/non-empty violation; 1
cryptographic, chain-integrity, I/O, or other verification failure.
```

## Lint

Command:

```bash
ruff check sdk/python/src/attestplane/cli/main.py tests/cli/test_verify_flags.py tests/cli/test_verify_errors.py sdk/python/tests/cli/test_verify_errors.py sdk/python/tests/cli/test_main.py tests/verifier/test_proof_bundle_schema.py
```

Result:

```text
All checks passed!
```

## Gate

Command:

```bash
run_gate attestplane
```

Result:

```text
[run_gate] project dir not found: /Users/macworkers/attestplane
```

The project gate helper is not configured for this checkout path. Focused issue validation passed as recorded above.

## Test-Fix Round 1

The local conformance gate failure was narrowed to the TypeScript side of the issue:

- The recorded npm command expected root npm workspace metadata.
- The TypeScript verifier did not yet expose the Python verifier's opt-in minimum signed-attestation schema check.
- The recorded test selector referenced `verifier.test.ts`, which was absent locally.

Commands:

```bash
env PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance/test_verifier_conformance.py -q
npm run test --workspace sdk/typescript -- verifier.test.ts
npm run test --workspace sdk/typescript -- verifier_conformance.test.ts
npm run typecheck --workspace sdk/typescript
env PYTHONPATH=sdk/python/src pytest tests/cli/test_verify_flags.py -q
```

Results:

```text
sdk/python/tests/conformance/test_verifier_conformance.py: 12 passed in 0.04s
npm run test --workspace sdk/typescript -- verifier.test.ts: 2 files passed, 21 tests passed
npm run test --workspace sdk/typescript -- verifier_conformance.test.ts: 1 file passed, 8 tests passed
npm run typecheck --workspace sdk/typescript: passed
tests/cli/test_verify_flags.py: 5 passed in 0.05s
```

## Test-Fix Round 2

The local CI-fix round found two issue-related problems:

- TypeScript `requireNonEmpty` incorrectly enabled signed-attestation schema
  enforcement; the options are now independent.
- An import-path fragility in
`tests/conformance/test_signed_schema_conformance_roundtrip.py`: when pytest
selected `sdk/python` as the session root, `tests.verifier` was not importable.
The conformance test now loads the existing helper by file path.

Commands:

```bash
env PYTHONPATH=sdk/python/src pytest tests/conformance/test_signed_schema_conformance_roundtrip.py -q
env PYTHONPATH=sdk/python/src pytest tests/cli/test_verify_flags.py sdk/python/tests/conformance/test_verifier_conformance.py tests/conformance/test_negative_minimum_schema_vectors.py tests/conformance/test_signed_schema_conformance_roundtrip.py -q
npm run test --workspace sdk/typescript -- verifier.test.ts verifier_conformance.test.ts
ruff check tests/conformance/test_signed_schema_conformance_roundtrip.py
npm run test --workspace sdk/typescript
npm run typecheck --workspace sdk/typescript
npm run build --workspace sdk/typescript
/Users/macworkers/.npm/_npx/3c2a9ea6c4b6e0a2/node_modules/.bin/markdownlint-cli2 'docs/validation/local_codex_runner/issue-138/*.md'
typos --config _typos.toml docs/validation/local_codex_runner/issue-138 tests/conformance/test_signed_schema_conformance_roundtrip.py
codespell tests/conformance/test_signed_schema_conformance_roundtrip.py docs/validation/local_codex_runner/issue-138 --skip='*.json'
git diff --check
```

Results:

```text
tests/conformance/test_signed_schema_conformance_roundtrip.py: 1 passed in 0.04s
focused issue/conformance selector: 23 passed in 0.08s
focused TypeScript verifier selector: 3 files passed, 30 tests passed
ruff: All checks passed
TypeScript vitest: 31 files passed, 520 tests passed
TypeScript typecheck: passed
TypeScript tsc emit: passed
markdownlint issue-138 evidence: Summary: 0 errors
typos: passed
codespell: passed
git diff --check: passed
```

Local blocker:

```text
npm run lint --workspace sdk/typescript: failed because the local Biome binary is
not installed.
cd sdk/typescript && npx --no-install biome check src test: attempted blocked
registry access to registry.npmjs.org and exited with EPERM.
```
