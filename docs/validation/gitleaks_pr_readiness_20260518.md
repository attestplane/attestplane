# Gitleaks PR Readiness 2026-05-18

## Branch

- Branch: `fix/security-gitleaks-redaction-20260518`
- Base branch: `feat/p3-4-positive-crypto-wiring-20260518`
- HEAD under test: `3ef5e96`

## Diff Files

- `docs/validation/gitleaks_remediation_20260518.json`
- `docs/validation/gitleaks_remediation_20260518.md`
- `sdk/python/src/attestplane/anchoring/sigstore.py`
- `sdk/python/src/attestplane/signing/base.py`
- `sdk/python/tests/adapters/test_langsmith.py`
- `sdk/typescript/test/adapters/langsmith.test.ts`

## Gitleaks

- Command: `gitleaks detect --source . --no-git --redact --report-format json --report-path /tmp/attestplane-gitleaks/pr-readiness-redacted.json`
- Result: clean
- Findings: 0
- Redacted report path: `/tmp/attestplane-gitleaks/pr-readiness-redacted.json`

## Tests

- Python: `59 passed`
  - `sdk/python/.venv/bin/python -m pytest sdk/python/tests/adapters/test_langsmith.py sdk/python/tests/signing/test_base.py sdk/python/tests/anchoring/test_sigstore.py -q`
  - Note: system/default Python interpreter missing pytest for that command; repo pytest environment available and passed.
- TypeScript: `16 passed`
  - `npm test -- test/adapters/langsmith.test.ts` in `sdk/typescript`

## Evidence Files

- `docs/validation/gitleaks_remediation_20260518.md`
- `docs/validation/gitleaks_remediation_20260518.json`
- `docs/validation/gitleaks_pr_readiness_20260518.md`
- `docs/validation/gitleaks_pr_readiness_20260518.json`

## Local Release Gate Status

`GO_FOR_PR_PREP`

## Remaining Limitations

- Remote CI was not triggered.
- No push or PR has been created.
- JIT Review remains optional degraded in the automation control repo.
- No production deployment or publish was performed.

## Recommended PR Title

```text
fix(security): remediate gitleaks findings for release gate
```

## Recommended PR Body

```markdown
Summary:
- Remediates 4 gitleaks findings blocking the local release gate.
- Replaces LangSmith test fixtures with explicit mock/test-only placeholders.
- Adds narrow inline allow markers for false-positive key object references.
- Adds validation evidence for remediation.

Validation:
- gitleaks detect --source . --no-git --redact: 0 findings
- sdk/python/.venv/bin/python -m pytest sdk/python/tests/adapters/test_langsmith.py sdk/python/tests/signing/test_base.py sdk/python/tests/anchoring/test_sigstore.py -q: 59 passed
- npm test -- test/adapters/langsmith.test.ts: 16 passed
- L0 automation dry-run from control repo: passed
- control repo pytest: 15 passed

Security:
- No secret values are printed or persisted in reports.
- rotation_required: no
- history_cleanup_required: no
- gitleaks_not_clean resolved.

Limitations:
- Remote CI not triggered.
- No push/PR yet.
- JIT Review remains optional degraded in the automation control repo.
```

## Reviewer Checklist

- Confirm the fixture placeholder changes preserve LangSmith redaction behavior.
- Confirm inline gitleaks allow markers are limited to false-positive object references.
- Confirm remediation evidence does not contain secret values.
- Confirm no release, deploy, publish, or remote CI action was performed.

## Explicit Non-Actions

- No push.
- No PR created.
- No merge.
- No CI triggered.
- No publish.
