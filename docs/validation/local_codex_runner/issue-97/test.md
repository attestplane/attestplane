# Issue 97 Validation Evidence

Plan ID: `9c2ebb04228d4d8e`

## Required Commands

### Targeted pytest

Command:

```bash
pytest -q sdk/python/tests/test_release_gate.py::test_product_delta_allows_real_sdk_changes_in_release_prep_range sdk/python/tests/test_stable_auto_train_queue.py::test_cadence_limiter_proceeds_for_mixed_real_release_prep_range
```

Result: pass.

Output:

```text
..                                                                       [100%]
2 passed in 0.01s
```

### Focused Regression Files

Command:

```bash
pytest -q sdk/python/tests/test_release_gate.py sdk/python/tests/test_stable_auto_train_queue.py
```

Result: pass.

```text
75 passed in 60.32s (0:01:00)
```

### Default Gate Follow-Up

Command:

```bash
python -m compileall scripts
```

Result: pass.

```text
Listing 'scripts'...
Listing 'scripts/api'...
Listing 'scripts/conformance'...
Listing 'scripts/dev'...
Listing 'scripts/fault'...
Listing 'scripts/local_codex_runner'...
Listing 'scripts/local_codex_runner/launchd'...
Listing 'scripts/local_codex_runner/prompts'...
Listing 'scripts/observability'...
Listing 'scripts/release'...
Listing 'scripts/security'...
Listing 'scripts/storage'...
```

```bash
pytest -q
```

Result: fail during collection before Issue #97 tests run because optional test
dependencies are unavailable in this runner environment. No tests were skipped,
xfailed, deleted, or weakened.

```text
ERROR sdk/python/tests/anchoring/test_sigstore.py
ImportError: attestplane.anchoring.http requires the 'anchor' extras.
ERROR sdk/python/tests/test_proof_bundle.py
ModuleNotFoundError: No module named 'jsonschema'
ERROR sdk/python/tests/test_properties.py
ModuleNotFoundError: No module named 'hypothesis'
ERROR sdk/python/tests/test_schemas_v1.py
ModuleNotFoundError: No module named 'jsonschema'
!!!!!!!!!!!!!!!!!!! Interrupted: 4 errors during collection !!!!!!!!!!!!!!!!!!!!
```

### Diff Whitespace Check

Command:

```bash
git diff --check
```

Result: pass.

Output: no output.

## Range Confirmation

Command:

```bash
git log --oneline --no-merges v1.7.4..HEAD
```

Output:

```text
f4dda59 Add multi-lane local Codex runner configuration
d974910 chore(release): prepare v1.7.5
3654115 Fix #172: align queue test with priority ordering
71a028e Fix #172: CI follow-up round 1
7dce5fc Fix #172: [P1][verifier] Introduce stable rejection reason-code taxonomy for `verify` failures
bb2ec0a Guard docs gate against non-doc runner diffs
c15606b Add canonicalization property tests
d229378 Prioritize local runner issue queue
211916a Fix local runner result cleanup between cycles
84c07f6 Validate opus runner network and interpreter changes
```

Command:

```bash
git diff --name-status v1.7.4..HEAD
```

Representative output:

```text
A	docs/release-notes/v1.7.5.draft.md
A	release/artifacts/v1.7.5/artifact-manifest.json
M	scripts/local_codex_runner/run_once.py
M	sdk/python/src/attestplane/verifier.py
A	sdk/python/src/attestplane/verify_reason_codes.py
M	sdk/typescript/src/verifier.ts
A	sdk/typescript/src/verify_reason_codes.ts
```

Conclusion: the release-prep diff is not only train-generated metadata. The
range contains real SDK implementation paths and local runner implementation
paths alongside release-prep metadata.

## Test-Fix Round 2

The default gate failure was rechecked locally. The Issue #97 scoped regression
coverage still passes, and no issue-local test failure was found to patch.

Command:

```bash
pytest -q sdk/python/tests/test_release_gate.py::test_product_delta_allows_real_sdk_changes_in_release_prep_range sdk/python/tests/test_stable_auto_train_queue.py::test_cadence_limiter_proceeds_for_mixed_real_release_prep_range
```

Result: pass.

```text
..                                                                       [100%]
2 passed in 0.02s
```

Command:

```bash
pytest -q sdk/python/tests/test_release_gate.py sdk/python/tests/test_stable_auto_train_queue.py
```

Result: pass.

```text
75 passed in 60.33s (0:01:00)
```

Command:

```bash
python -m compileall scripts
```

Result: pass.

Command:

```bash
git diff --check
```

Result: pass with no output.

Default `pytest -q` continues to fail during collection before the Issue #97
tests run because this runner environment lacks optional test dependencies:
`asn1crypto`, `jsonschema`, and `hypothesis`. No tests were skipped, xfailed,
deleted, weakened, or reclassified.

## Environment Fix Follow-Up

The failure above was caused by the lane worktree falling back to system Python
instead of the project virtualenv. Re-running the same test surface with the
project virtualenv succeeds.

Command:

```bash
ATTESTPLANE_REPO_DIR=/Users/macworkers/Projects/attestplane \
  /Users/macworkers/Projects/attestplane/sdk/python/.venv/bin/python \
  -m pytest sdk/python/tests -k 'release_gate or stable_auto_train' -x
```

Result: pass.

```text
76 passed, 936 deselected in 4.44s
```

Command:

```bash
ATTESTPLANE_REPO_DIR=/Users/macworkers/Projects/attestplane \
  /Users/macworkers/Projects/attestplane/sdk/python/.venv/bin/pytest -q
```

Result: pass.

```text
1326 passed in 26.78s
```
