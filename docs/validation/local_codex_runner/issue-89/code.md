# Issue 89 Code Evidence

Plan ID: `0eaa183f7a04f6db`

## Summary

Expanded regression coverage for the real local `v1.7.4..HEAD` release-prep
range.

- Broadened the release-gate fixture in `test_release_gate.py` to include
  representative files from the real range: release artifacts, validation
  evidence, API manifests, local runner files, SDK Python implementation and
  tests, SDK TypeScript implementation and tests, package metadata, and
  top-level regression tests.
- Broadened the stable auto-train cadence regression in
  `test_stable_auto_train_queue.py` to mirror the local real commit subjects
  around `chore(release): prepare v1.7.5`.

## Files Changed

- `sdk/python/tests/test_release_gate.py`
- `sdk/python/tests/test_stable_auto_train_queue.py`
- `docs/validation/local_codex_runner/issue-89/code.md`
- `docs/validation/local_codex_runner/issue-89/test.md`
- `docs/validation/local_codex_runner/issue-89/gate_report.md`
- `docs/validation/local_codex_runner/issue-89/gate_report.json`

## Release-Prep Range Confirmation

Local commit subjects from `git log --no-merges --pretty=tformat:'%h %s'
v1.7.4..HEAD` include real work as well as release-prep metadata:

```text
51cf2e2 Fix #94: \[P2\]\[docs\] Summarize the user-visible delta for v1.5.9 (#190)
80fe23f Fix #96: \[P0\]\[release\] Confirm the v1.5.10 real-change boundary (#191)
b4a5fd2 Fix #97: cover mixed real release-prep ranges (#192)
4cd29d4 Fix #92: \[P0\]\[release\] Confirm the v1.5.9 real-change boundary (#187)
dd56009 Fix #114: \[P0\]\[release\] Confirm the v1.6.2 real-change boundary (#189)
f4dda59 Add multi-lane local Codex runner configuration
d974910 chore(release): prepare v1.7.5
3654115 Fix #172: align queue test with priority ordering
71a028e Fix #172: CI follow-up round 1
7dce5fc Fix #172: \[P1\]\[verifier\] Introduce stable rejection reason-code taxonomy for `verify` failures
bb2ec0a Guard docs gate against non-doc runner diffs
c15606b Add canonicalization property tests
d229378 Prioritize local runner issue queue
211916a Fix local runner result cleanup between cycles
84c07f6 Validate opus runner network and interpreter changes
```

Representative files from `git diff --name-status v1.7.4..HEAD` include:

```text
M  api/public/python_v1.json
M  api/public/typescript_v1.json
A  docs/release-notes/v1.7.5.draft.md
A  release/artifacts/v1.7.5/artifact-manifest.json
M  scripts/local_codex_runner/run_once.py
M  sdk/python/src/attestplane/cli/main.py
M  sdk/python/src/attestplane/verifier.py
A  sdk/python/src/attestplane/verify_reason_codes.py
M  sdk/python/tests/test_release_gate.py
M  sdk/python/tests/test_stable_auto_train_queue.py
M  sdk/typescript/src/index.ts
M  sdk/typescript/src/verifier.ts
A  sdk/typescript/src/verify_reason_codes.ts
A  tests/canonicalization/test_canonicalization_properties.py
A  tests/local_codex_runner/test_run_once.py
A  tests/verifier/test_verify_reason_codes.py
```

Conclusion: the release-prep diff is not only train-generated metadata. The
range includes real SDK implementation changes, SDK tests, local runner changes,
verifier reason-code work, conformance/public API updates, and regression tests
alongside release notes, package metadata, and `release/artifacts/v1.7.5/*`.

## Safety

No release workflow, publish workflow, tag, package version, release artifact,
or release gate implementation was changed. The functional diff is limited to
regression tests plus issue-local evidence.
