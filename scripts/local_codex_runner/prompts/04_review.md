# Local Codex Runner Self-Review Prompt

You are reviewing the current diff for Issue #{{issue_number}}.

Issue title: {{issue_title}}
Issue URL: {{issue_url}}
Labels: {{issue_labels}}

Write:

- JSON report to `{{review_json_path}}`.
- Markdown report to `{{review_md_path}}`.

Review checklist:

1. Did the diff weaken any release gate?
2. Did it lower severity?
3. Did it leak or log secrets?
4. Did it modify publish/tag logic?
5. Did it delete key tests?
6. Did it implement behavior without tests or evidence?
7. Did it introduce uncertain external dependencies?
8. Did it avoid merge, tag, package publish, and PyPI push?

JSON fields:

- status: PASS, WARN, or FAIL
- blocking_reasons: list
- warnings: list
- validation: list
- residual_risks: list
- no_merge_tag_publish_pypi: true or false

If any hard red line is violated, status must be FAIL.
