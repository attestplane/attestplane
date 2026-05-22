# Local Codex Runner Self-Review Prompt

You are reviewing the current diff for Issue #141.

Issue title: [P2][docs] Extend #125 with the v1.7.1 SDK + CLI delta
Issue URL: https://github.com/attestplane/attestplane/issues/141
Labels: type:docs, area:docs, priority:P2, planned-task, auto-codex-approved

Write:

- JSON report to `/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-141/codex_review_report.json`.
- Markdown report to `/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-141/codex_review_report.md`.

Review checklist:

0. Did the review use only local repository files, local command output, and the issue text?
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
