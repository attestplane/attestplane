# Local Codex Runner Plan Prompt

You are working in Attestplane on Issue #125.

Issue title: [P2][docs] Summarize the v1.7.0 user-visible delta (non-empty + minimum-schema bundle contract)
Issue URL: https://github.com/attestplane/attestplane/issues/125
Labels: type:docs, area:docs, priority:P2, planned-task, auto-codex-approved

Issue body:
Source planning issue: #120
- Priority: P2
- Affected modules: `CHANGELOG.md`, `docs/release-notes/v1.7.0.md`, SDK migration notes; **support task**
- Acceptance criteria:
  - Release note explicitly states v1.7.0 is the first stable since v1.5.0 to carry product changes (per `5b32c86` productless-release block and #119), and enumerates: non-empty bundle requirement (`3f551d9`), Issue 1 schema tightening, Issue 3 SDK builder + typed errors.
  - Includes a 3-line "what integrators must do" block and a link back to this planning issue.
  - No secrets, no signing keys, no internal runner hostnames.
- Validation commands:
  - `markdownlint docs/release-notes/v1.7.0.md CHANGELOG.md`
  - `python scripts/release/check_changelog.py --version 1.7.0`
- Rollout / migration notes: Docs-only; do not move tags or republish. Land after Issues 1–3 are merged so the note matches shipped behavior.
Plan ID: `f9ab1b6b3254613c`

Generated from accepted development plan.


Task:

- Analyze the issue and write an implementation plan only.
- Do not edit code in this phase.
- Write the plan to `/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-125/plan.md`.

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
