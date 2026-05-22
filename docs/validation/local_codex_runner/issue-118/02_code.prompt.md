# Local Codex Runner Code Prompt

You are working in Attestplane on Issue #118.

Issue title: [P2][docs] Summarize the user-visible delta for v1.6.2
Issue URL: https://github.com/attestplane/attestplane/issues/118
Labels: type:docs, area:docs, priority:P2, planned-task, auto-codex-approved
Evidence directory: `/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-118`
Plan path: `/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-118/plan.md`

Issue body:
Source planning issue: #113
- Priority: P2
- Affected modules: `CHANGELOG.md`, `docs/releases/v1.6.2.md`, `README.md` (release table only)
- Acceptance criteria:
  - One-paragraph user-facing summary covering the single real change: planned-task issues created from Opus consultations are now re-fetched from GitHub before downstream consumption, eliminating the "first-run sees zero new issues" race.
  - Note the CI-only improvements (proxy strategy, local Python on opus runner) under a separate "Infrastructure" bullet so users do not mistake them for product changes.
  - Cross-link #108-style boundary audit (this milestone's ISSUE 1) and the related task issues spawned from this plan.
- Validation commands:
  - `markdownlint docs/releases/v1.6.2.md CHANGELOG.md`
  - `python -m scripts.release.render_release_notes --version v1.6.2 --check`
  - `git diff --stat -- docs CHANGELOG.md`
- Rollout / migration notes: docs-only. No tag movement, no package republish. If ISSUE 1 surfaces an undisclosed behavior change, expand this summary before closing.
Plan ID: `62384e54aa68607a`

Generated from accepted development plan.


Task:

- Implement the plan using focused code, test, documentation, and evidence changes.
- Keep the diff scoped to this issue.
- Update evidence under `/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-118` when behavior or validation changes.

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
