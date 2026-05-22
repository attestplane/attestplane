# Issue 89 Validation Evidence

Plan ID: `0eaa183f7a04f6db`

## Required Commands

### Required Pytest Command

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

The lane initially did not contain `sdk/python/.venv/bin/python`. Attempting to
create it from the checked-in lockfile with `uv` was blocked by restricted
network/cache access while fetching `uuid-utils==0.16.0`. The partial virtualenv
is ignored by `.gitignore` and is not part of the diff.

### Required Whitespace Check

Command:

```bash
git diff --check
```

Result: pass.

Exit code: `0`

Output: no output.

## Focused Regression Validation

### Edited Regression Tests

Command:

```bash
pytest -q sdk/python/tests/test_release_gate.py::test_product_delta_allows_real_sdk_changes_in_release_prep_range sdk/python/tests/test_stable_auto_train_queue.py::test_cadence_limiter_proceeds_for_mixed_real_release_prep_range
```

Result: pass.

Exit code: `0`

Output:

```text
..                                                                       [100%]
2 passed in 0.05s
```

### Release Gate And Stable Train Test Files

Command:

```bash
pytest -q sdk/python/tests/test_release_gate.py sdk/python/tests/test_stable_auto_train_queue.py
```

Result: pass.

Exit code: `0`

Output:

```text
75 passed in 60.31s (0:01:00)
```

### Fallback Full `-k` Attempt

Command:

```bash
PYTHONPATH=sdk/python/src pytest sdk/python/tests -k 'release_gate or stable_auto_train' -x
```

Result: blocked during collection before the selected tests could run.

Exit code: `1`

Relevant output:

```text
ERROR sdk/python/tests/anchoring/test_sigstore.py
ImportError: attestplane.anchoring.http requires the 'anchor' extras. Install with: pip install attestplane[anchor]
```

No tests were deleted, skipped, xfailed, weakened, or reclassified to
manufacture a pass.

## Local Range Evidence

Command:

```bash
git log --no-merges --pretty=tformat:'%h %s' v1.7.4..HEAD
```

Output:

```text
51cf2e2 Fix #94: [P2][docs] Summarize the user-visible delta for v1.5.9 (#190)
80fe23f Fix #96: [P0][release] Confirm the v1.5.10 real-change boundary (#191)
b4a5fd2 Fix #97: cover mixed real release-prep ranges (#192)
4cd29d4 Fix #92: [P0][release] Confirm the v1.5.9 real-change boundary (#187)
dd56009 Fix #114: [P0][release] Confirm the v1.6.2 real-change boundary (#189)
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
git diff --check v1.7.4..HEAD
```

Result: pass.

Exit code: `0`

Output: no output.

Conclusion: the local release-prep range is mixed real work plus train metadata,
not train-generated metadata only.
