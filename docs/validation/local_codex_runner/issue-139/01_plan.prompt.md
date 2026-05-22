# Local Codex Runner Plan Prompt

You are working in Attestplane on Issue #139.

Issue title: [P1][verifier] Add signed-schema round-trip regression locking #126 behavior
Issue URL: https://github.com/attestplane/attestplane/issues/139
Labels: priority:P1, area:verifier, planned-task, auto-codex-approved

Issue body:
Source planning issue: #136
- Priority: P1
- Affected modules: verifier (signed schema enforcement from #126/#121), proof-bundle schema, conformance fixture lock (`cb3d3345`)
- Acceptance criteria:
  - New regression test loads each signed fixture, re-canonicalizes via SDK, re-signs with the test key, and asserts byte-identical output to the locked fixture.
  - Test fails loudly when the schema enforcement is relaxed or when canonicalization drift is introduced.
  - Failure messages name the exact field that diverged (not just a hash mismatch).
  - Suite runs in <5s on the standard runner; no network.
- Validation commands:
  - `pytest tests/verifier/test_signed_schema_roundtrip.py -x -vv`
  - `pytest tests/conformance -k signed_schema -x`
- Rollout / migration notes: Pure test addition. If the round-trip discovers any pre-existing drift in the v1.7.0 locked fixture, open a separate P0 issue rather than silently regenerating the fixture.

---
Plan ID: `2e8af61f69ea41f4`

Generated from accepted development plan.


Task:

- Analyze the issue and write an implementation plan only.
- Do not edit code in this phase.
- Write the plan to `/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-139/plan.md`.

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
