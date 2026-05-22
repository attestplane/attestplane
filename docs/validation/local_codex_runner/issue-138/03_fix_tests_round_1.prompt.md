# Local Codex Runner Test-Fix Prompt

You are working in Attestplane on Issue #138.

Issue title: [P1][cli] Expose `verify --require-non-empty` and `--strict-schema` flags
Issue URL: https://github.com/attestplane/attestplane/issues/138
Labels: priority:P1, area:conformance, planned-task, auto-codex-approved
Evidence directory: `/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-138`

Failure summary:
# Gate Report: FAIL

Gate: `area:conformance`

## Commands

- `env PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance/test_verifier_conformance.py -q`: exit=0
- `npm run test --workspace sdk/typescript -- verifier.test.ts`: exit=1

Task:

- Fix only failures related to this issue.
- Update tests and evidence as needed.
- Keep the diff scoped and preserve the original safety posture.

Hard red lines:

- Use only local repository files, local command output, and the issue text.
- Do not use web search, browser tools, external plugin/app connectors, or external advisory services in this runner phase.
- Do not skip, xfail, delete, or weaken tests just to pass.
- Do not lower severity.
- Do not weaken release gates or release_blocking policy.
- Do not merge, tag, publish packages, or push PyPI.
- Do not read or log secrets, cookies, private keys, `.pypirc`, `.npmrc`, or credentials files.
