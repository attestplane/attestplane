# Post-Merge Gitleaks Release Gate 2026-05-18

## Branch

- Branch: `feat/p3-4-positive-crypto-wiring-20260518`
- HEAD: `a1af21d`
- Merge commit: `a1af21dc86f01a64327eaa1e1b5e816772192c26`
- PR: `#10`

## Gitleaks

- Command: `gitleaks detect --source . --no-git --redact --report-format json --report-path /tmp/attestplane-gitleaks/post-merge-redacted.json`
- Result: clean
- Findings: 0
- Redacted report: `/tmp/attestplane-gitleaks/post-merge-redacted.json`

## Python Tests

- Command: `sdk/python/.venv/bin/python -m pytest sdk/python/tests/adapters/test_langsmith.py sdk/python/tests/signing/test_base.py sdk/python/tests/anchoring/test_sigstore.py -q`
- Result: passed
- Summary: 59 passed
- Note: system/default Python interpreter missing pytest for that command; repo pytest environment available and passed.

## TypeScript Tests

- Command: `npm test -- test/adapters/langsmith.test.ts`
- Working directory: `sdk/typescript`
- Result: passed
- Summary: 16 passed

## CI Context

- Pre-merge workflow_dispatch CI verdict: `REMOTE_CI_SUCCESS`
- Covered workflows: `ci`, `sdk-python`, `sdk-typescript`, `osv-scanner`, `invariants`, `codeql`

## Release Blocker Status

- `gitleaks_not_clean`: resolved
- Rotation required: no
- History cleanup required: no

## Remaining Limitations

- No publish was performed.
- No deployment was performed.
- No GitHub Release was created.
- This post-merge evidence commit is local until explicitly approved for push.

## Go/No-Go

`GO_POST_MERGE_LOCAL_GATE`
