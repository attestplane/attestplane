# Gitleaks Remediation 2026-05-18

## Summary

- Target repo: `/Users/macworkers/Projects/attestplane`
- Branch: `fix/security-gitleaks-redaction-20260518`
- HEAD before: `dd6f782`
- HEAD after remediation before commit: `dd6f782`
- Findings before: 4
- Findings after: 0
- Gitleaks result: clean
- L0 dry-run result: passed
- Release gate result: `GO_DRY_RUN_ONLY`

## Files Changed

- `sdk/python/src/attestplane/anchoring/sigstore.py`
- `sdk/python/src/attestplane/signing/base.py`
- `sdk/python/tests/adapters/test_langsmith.py`
- `sdk/typescript/test/adapters/langsmith.test.ts`
- `docs/validation/gitleaks_remediation_20260518.json`
- `docs/validation/gitleaks_remediation_20260518.md`

## Finding Classifications

| Rule | File | Line | Classification | Action | Rotation | History cleanup |
|---|---:|---:|---|---|---|---|
| `generic-api-key` | `sdk/python/tests/adapters/test_langsmith.py` | 58 | `test_fixture_or_placeholder` | Replaced the fixture value with `REDACTED_FOR_TEST` and renamed the local variable away from a secret-like assignment shape. | no | no |
| `generic-api-key` | `sdk/python/src/attestplane/signing/base.py` | 100 | `false_positive` | Added a narrow inline gitleaks allow marker to a typed Ed25519PrivateKey object reference. | no | no |
| `generic-api-key` | `sdk/python/src/attestplane/anchoring/sigstore.py` | 112 | `false_positive` | Added a narrow inline gitleaks allow marker to an optional Ed25519PrivateKey object parameter. | no | no |
| `generic-api-key` | `sdk/typescript/test/adapters/langsmith.test.ts` | 62 | `test_fixture_or_placeholder` | Replaced the fixture value with `REDACTED_FOR_TEST` and renamed the local variable away from a secret-like assignment shape. | no | no |

No secret values are recorded in this report.

## Validation

- `gitleaks detect --source . --no-git --redact --report-format json --report-path /tmp/attestplane-gitleaks/after-inline-redacted.json`: passed, 0 findings.
- `sdk/python/.venv/bin/python -m pytest sdk/python/tests/adapters/test_langsmith.py sdk/python/tests/signing/test_base.py sdk/python/tests/anchoring/test_sigstore.py -q`: passed, 59 tests.
- `npm test -- test/adapters/langsmith.test.ts` in `sdk/typescript`: passed, 16 tests.
- L0 dry-run from automation control repo: passed.
- L0 read-only run from automation control repo: passed.
- Automation control pytest: passed, 15 tests.

## L0 Gate Result

- `gitleaks`: ok
- `gitleaks_findings`: 0
- JIT Review: timeout, degraded mode true, fallback `local_static_review`
- Release Go/No-Go: `GO_DRY_RUN_ONLY`

## Remaining Risk

- Two inline gitleaks allow markers are intentionally narrow and attached only to false-positive typed Ed25519PrivateKey object references.
- Secret rotation was not performed.
- Git history cleanup was not performed.
