# Local Codex Runner Plan Prompt

You are working in Attestplane on Issue #118.

Issue title: [P2][docs] Summarize the user-visible delta for v1.6.2
Issue URL: https://github.com/attestplane/attestplane/issues/118
Labels: type:docs, area:docs, priority:P2, planned-task, auto-codex-approved

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

- Analyze the issue and write an implementation plan only.
- Do not edit code in this phase.
- Write the plan to `/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-118/plan.md`.

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
