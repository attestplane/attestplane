# Issue 80 Validation Evidence

Plan ID: `a436b5c984b97ca8`

## Required Command

Command:

```bash
sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'release_gate or stable_auto_train' -x
```

Result: blocked in this lane environment.

Exit code: `1`

Output:

```text
/Users/macworkers/Projects/attestplane-lane-p1-2/sdk/python/.venv/bin/python: No module named pytest
```

The project venv exists, but `pytest` is not installed inside it in this
runner. A host-level `pytest` is available, but the required exact command
cannot run without first populating the venv.

## Focused Regression Validation

Command:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=/opt/homebrew/lib/python3.11/site-packages:sdk/python/src sdk/python/.venv/bin/python -m pytest sdk/python/tests/test_release_gate.py sdk/python/tests/test_stable_auto_train_queue.py -q
```

Result: pass.

Exit code: `0`

Output:

```text
75 passed in 60.45s (0:01:00)
```

## Range Evidence

Command:

```bash
git log --no-merges --pretty=tformat:'%h %s' v1.7.4..HEAD
```

Representative output:

```text
84c07f6 Validate opus runner network and interpreter changes
211916a Fix local runner result cleanup between cycles
d229378 Prioritize local runner issue queue
c15606b Add canonicalization property tests
bb2ec0a Guard docs gate against non-doc runner diffs
7dce5fc Fix #172: [P1][verifier] Introduce stable rejection reason-code taxonomy for `verify` failures
71a028e Fix #172: CI follow-up round 1
3654115 Fix #172: align queue test with priority ordering
d974910 chore(release): prepare v1.7.5
```

Command:

```bash
git diff --name-status v1.7.4..HEAD
```

Representative output:

```text
M  scripts/local_codex_runner/run_once.py
M  sdk/python/src/attestplane/verifier.py
A  sdk/python/src/attestplane/verify_reason_codes.py
M  sdk/typescript/src/verifier.ts
A  sdk/typescript/src/verify_reason_codes.ts
A  tests/canonicalization/test_canonicalization_properties.py
```

Conclusion: the local release-prep range contains real product work alongside
train-generated release-prep metadata.
