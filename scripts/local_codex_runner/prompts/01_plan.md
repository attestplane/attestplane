# Local Codex Runner Plan Prompt

You are working in Attestplane on Issue #{{issue_number}}.

Issue title: {{issue_title}}
Issue URL: {{issue_url}}
Labels: {{issue_labels}}

Issue body:
{{issue_body}}

Task:
- Analyze the issue and write an implementation plan only.
- Do not edit code in this phase.
- Write the plan to `{{plan_path}}`.

The plan must include:
- Files likely to change.
- Tests and local gates to run.
- Risk classification.
- Evidence files to update.
- Confirmation that this task will not merge, tag, publish npm/PyPI packages, push PyPI, or weaken release gates.

Safety rules:
- Do not lower P0/P1 severity.
- Do not remove failing tests to manufacture a pass.
- Do not loosen release gates or claim-safety policy.
- Do not read or log ChatGPT cookies, GitHub tokens, OpenAI tokens, private keys, `.pypirc`, `.npmrc`, or credentials files.

