# Local Codex Runner Code Prompt

You are working in Attestplane on Issue #141.

Issue title: [P2][docs] Extend #125 with the v1.7.1 SDK + CLI delta
Issue URL: https://github.com/attestplane/attestplane/issues/141
Labels: type:docs, area:docs, priority:P2, planned-task, auto-codex-approved
Evidence directory: `/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-141`
Plan path: `/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-141/plan.md`

Issue body:
Source planning issue: #136
- Priority: P2
- Affected modules: docs (`docs/changes/`), SDK reference, CLI reference — extends open issue #125, does **not** duplicate
- Acceptance criteria:
  - Add a v1.7.1 sub-section to the deliverable tracked by #125 covering: new conformance vectors (Issue 1), new CLI flags (Issue 2), and the round-trip regression (Issue 3).
  - One concrete code snippet per surface (SDK call, CLI invocation).
  - Cross-link from `README.md` "What's new" anchor; no marketing copy.
- Validation commands:
  - `markdownlint docs/changes/v1.7.x.md`
  - `python -m pytest docs/ --doctest-glob='*.md'` (if doctest harness exists; otherwise manual snippet copy-paste smoke)
- Rollout / migration notes: Support task; only acceptable here because Issues 1–3 above carry the mandatory product increment. Do not land docs before the corresponding product PRs merge.
Plan ID: `8bed96c40b295da3`

Generated from accepted development plan.


Task:

- Implement the plan using focused code, test, documentation, and evidence changes.
- Keep the diff scoped to this issue.
- Update evidence under `/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-141` when behavior or validation changes.

Hard red lines:

- Use only local repository files, local command output, and the issue text.
- Do not use web search, browser tools, external plugin/app connectors, or external advisory services in this runner phase.
- Do not merge `main`.
- Do not create or move tags.
- Do not publish packages.
- Do not push PyPI.
- Do not lower P0/P1 severity.
- Do not delete or skip failing tests to manufacture a pass.
- Do not weaken release gates, claim-safety checks, or release_blocking policy.
- Do not modify publish/tag/release workflows unless the issue label explicitly authorizes it.
- Do not introduce uncertain external dependencies without justification and tests.
- Do not read or log ChatGPT cookies, GitHub tokens, OpenAI tokens, private keys, `.pypirc`, `.npmrc`, or credentials files.

Every functional change must include a test or a concrete evidence update.
