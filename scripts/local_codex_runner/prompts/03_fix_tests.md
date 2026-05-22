# Local Codex Runner Test-Fix Prompt

You are working in Attestplane on Issue #{{issue_number}}.

Issue title: {{issue_title}}
Issue URL: {{issue_url}}
Labels: {{issue_labels}}
Evidence directory: `{{evidence_dir}}`

Failure summary:
{{gate_log}}

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
