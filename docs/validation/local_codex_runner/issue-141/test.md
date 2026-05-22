# Issue 141 Validation Evidence

Plan ID: `8bed96c40b295da3`

## Issue-Required Markdown Command

Command:

```bash
markdownlint docs/changes/v1.7.x.md
```

Result:

```text
zsh:1: command not found: markdownlint
```

Local equivalent command:

```bash
/Users/macworkers/.npm/_npx/3c2a9ea6c4b6e0a2/node_modules/.bin/markdownlint-cli2 docs/changes/v1.7.x.md README.md docs/contributor/api-reference.md docs/usage/cli_proofbundle_verifier_alpha.md
```

Result:

```text
markdownlint-cli2 v0.22.1 (markdownlint v0.40.0)
Finding: docs/changes/v1.7.x.md README.md docs/contributor/api-reference.md docs/usage/cli_proofbundle_verifier_alpha.md
Linting: 4 file(s)
Summary: 0 error(s)
```

## Issue-Required Doctest Command

Command:

```bash
PYTHONPATH=sdk/python/src python -m pytest docs/ --doctest-glob='*.md' -q
```

Result:

```text
/opt/homebrew/opt/python@3.14/bin/python3.14: No module named pytest
```

Local Python 3.11 equivalent:

```bash
PYTHONPATH=sdk/python/src python3.11 -m pytest docs/ --doctest-glob='*.md' -q
```

Result:

```text
no tests ran in 0.08s
```

The docs tree has no collected doctest examples under the local harness, so the
SDK and CLI snippets were smoke-tested manually.

## Manual SDK Snippet Smoke

Command:

```bash
PYTHONPATH=sdk/python/src python3.11 - <<'PY'
from attestplane.sdk import EmptyProofBundleError, IncompleteProofBundleError, ProofBundleBuilder, verify_minimum_bundle
from attestplane.signing import InMemoryKeyProvider, Signer

subject_digest = "3f551d9" + "0" * 57
signer = Signer(chain_id="example-minimum-bundle", key_provider=InMemoryKeyProvider(seed=b"\x12" * 32))
try:
    bundle = ProofBundleBuilder.minimal(subject_digest, signer)
    result = verify_minimum_bundle(bundle)
except (EmptyProofBundleError, IncompleteProofBundleError):
    raise
assert result.ok
print(f"ok={result.ok} events={result.event_count} error_code={result.error_code}")
PY
```

Result:

```text
ok=True events=1 error_code=VERIFY_OK
```

## Manual CLI Snippet Smoke

Command:

```bash
PYTHONPATH=sdk/python/src python3.11 -c 'import sys; from attestplane.cli.main import main; raise SystemExit(main(sys.argv[1:]))' verify tests/fixtures/v1.7.0_signed.json --require-non-empty --strict-schema; printf 'exit=%s\n' $?
```

Result:

```text
OK chain_id='p3-cli-proofbundle' events=1 head=<hex elided>
MODE: chain/report-oriented, not a full verifier. This command replays bundle events, compares the embedded verification_report with the recomputed chain result, and fails closed on malformed ProofBundle metadata and policy_trace_refs closure. It does not perform signature verification, anchor verification, or compliance certification.
exit=0
```

## Dependency Checks

Command:

```bash
PYTHONPATH=sdk/python/src pytest tests/conformance -k canonicalization -x
```

Result:

```text
8 passed, 6 deselected in 0.09s
```

Command:

```bash
PYTHONPATH=sdk/python/src pytest tests/cli/test_verify_flags.py -x
```

Result:

```text
5 passed in 0.08s
```

Command:

```bash
PYTHONPATH=sdk/python/src pytest tests/verifier/test_signed_schema_roundtrip.py -x -vv
```

Result:

```text
2 passed in 0.04s
```

Command:

```bash
PYTHONPATH=sdk/python/src pytest tests/conformance -k signed_schema -x
```

Result:

```text
1 passed, 13 deselected in 0.04s
```

## Diff Check

Markdownlint for the new evidence files was also run after writing this file:

```bash
/Users/macworkers/.npm/_npx/3c2a9ea6c4b6e0a2/node_modules/.bin/markdownlint-cli2 docs/changes/v1.7.x.md README.md docs/contributor/api-reference.md docs/usage/cli_proofbundle_verifier_alpha.md docs/validation/local_codex_runner/issue-141/code.md docs/validation/local_codex_runner/issue-141/test.md docs/validation/local_codex_runner/issue-141/gate_report.md
```

Result:

```text
Summary: 0 error(s)
```

Command:

```bash
git diff --check
```

Result:

```text
PASS
```

## Local Gate

Command:

```bash
run_gate Projects/attestplane
```

Result:

```text
196 passed, 1 warning in 43.63s
{"project":"Projects/attestplane","mode":"fast","sha":"386852e","result":"PASS","duration_seconds":44,"report":""}
```

Warning: pytest cache could not write under
`/Users/macworkers/Projects/attestplane/.pytest_cache` due to sandbox
permissions. Tests still passed.
