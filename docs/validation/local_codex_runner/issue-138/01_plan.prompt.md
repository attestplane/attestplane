# Local Codex Runner Plan Prompt

You are working in Attestplane on Issue #138.

Issue title: [P1][cli] Expose `verify --require-non-empty` and `--strict-schema` flags
Issue URL: https://github.com/attestplane/attestplane/issues/138
Labels: priority:P1, area:conformance, planned-task, auto-codex-approved

Issue body:
Source planning issue: #136
- Priority: P1
- Affected modules: CLI (`attestplane verify`), verifier runtime (enforcement added in `3f551d9` non-empty + `2ed64af`/#126 signed schema), SDK glue
- Acceptance criteria:
  - `attestplane verify <bundle>` gains `--require-non-empty` and `--strict-schema` flags; defaults preserve current behavior (no behavior change without the flag).
  - Exit codes documented: `0` success, `2` schema/non-empty violation, `1` cryptographic failure.
  - `--help` output enumerates both flags with a one-line rationale referencing the proof-bundle contract.
  - Integration test covers all four combinations (flag on/off × valid/invalid bundle).
- Validation commands:
  - `pytest tests/cli/test_verify_flags.py -x`
  - `attestplane verify tests/fixtures/empty_bundle.json --require-non-empty; echo $?` (expect `2`)
  - `attestplane verify tests/fixtures/v1.7.0_signed.json --strict-schema; echo $?` (expect `0`)
- Rollout / migration notes: Flags are opt-in; no migration. Note in CHANGELOG that downstream automation can adopt the flags before they become default in a future `x.0.0`.

---
Plan ID: `ea2324f7e1effb2e`

Generated from accepted development plan.


Task:

- Analyze the issue and write an implementation plan only.
- Do not edit code in this phase.
- Write the plan to `/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-138/plan.md`.

The plan must include:

- Files likely to change.
- Tests and local gates to run.
- Risk classification.
- Evidence files to update.
- Confirmation that this task will not merge, tag, publish npm/PyPI packages, push PyPI, or weaken release gates.

Safety rules:

- Use only local repository files, local command output, and the issue text.
- Do not use web search, browser tools, external plugin/app connectors, or external advisory services in this runner phase.
- Do not lower P0/P1 severity.
- Do not remove failing tests to manufacture a pass.
- Do not loosen release gates or claim-safety policy.
- Do not read or log ChatGPT cookies, GitHub tokens, OpenAI tokens, private keys, `.pypirc`, `.npmrc`, or credentials files.
