# Issue 97 Code Evidence

Plan ID: `9c2ebb04228d4d8e`

## Summary

Implemented focused regression coverage for the local `v1.7.4..HEAD` range:

- Added a stable auto-train cadence regression proving a mixed range with
  `chore(release): prepare v1.7.5` plus real commit subjects proceeds.
- Added a release-gate product-delta regression proving release-prep metadata
  remains support-only while real SDK implementation paths make the range a
  product implementation delta.

## Files Changed

- `sdk/python/tests/test_stable_auto_train_queue.py`
- `sdk/python/tests/test_release_gate.py`
- `docs/validation/local_codex_runner/issue-97/code.md`
- `docs/validation/local_codex_runner/issue-97/test.md`

## Local Range Used

Commit subjects from `git log --oneline --no-merges v1.7.4..HEAD` include:

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

Representative `git diff --name-status v1.7.4..HEAD` paths include:

```text
A	docs/release-notes/v1.7.5.draft.md
A	release/artifacts/v1.7.5/artifact-manifest.json
M	scripts/local_codex_runner/run_once.py
M	sdk/python/src/attestplane/verifier.py
A	sdk/python/src/attestplane/verify_reason_codes.py
M	sdk/typescript/src/verifier.ts
A	sdk/typescript/src/verify_reason_codes.ts
```

The release-prep diff is not only train-generated metadata because the local
range includes real SDK implementation files and local runner implementation
files in addition to release notes and release artifact metadata.

## Safety

No release script behavior, release workflow, tag, publish, push, or gate policy
was changed. The implementation is limited to tests and local evidence.
