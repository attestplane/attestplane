# Local Codex Runner Code Prompt

You are working in Attestplane on Issue #{{issue_number}}.

Issue title: {{issue_title}}
Issue URL: {{issue_url}}
Labels: {{issue_labels}}
Evidence directory: `{{evidence_dir}}`
Plan path: `{{plan_path}}`

Issue body:
{{issue_body}}

Task:

- Implement the plan using focused code, test, documentation, and evidence changes.
- Keep the diff scoped to this issue.
- Update evidence under `{{evidence_dir}}` when behavior or validation changes.

Hard red lines:

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
