# Local Codex Runner Code Prompt

You are working in Attestplane on Issue #137.

Issue title: [P1][sdk] Extend minimum-bundle helper with canonicalization edge-case conformance vectors
Issue URL: https://github.com/attestplane/attestplane/issues/137
Labels: priority:P1, area:verifier, planned-task, auto-codex-approved
Evidence directory: `/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-137`
Plan path: `/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-137/plan.md`

Issue body:
Source planning issue: #136
- Priority: P1
- Affected modules: SDK public API (minimum proof bundle helper added in #132/#123), conformance vectors (negative set added in #134/#122), canonicalization
- Acceptance criteria:
  - Conformance suite gains at least 4 new vectors covering: duplicate JSON keys, NFC vs NFD payload strings, trailing-whitespace/BOM in canonical JSON, and integer-boundary timestamp fields.
  - Each vector exists in both positive (helper-emitted) and negative (hand-crafted, must-reject) form.
  - `minimum_proof_bundle()` SDK helper documents which invariants it canonicalizes vs. which the verifier rejects.
  - No churn in existing v1.7.x fixture hashes; new vectors land in additive sub-directories.
- Validation commands:
  - `pytest tests/conformance -k canonicalization -x`
  - `pytest tests/conformance -k minimum_bundle_negative -x`
  - `python -m attestplane.sdk.examples.minimum_bundle | python -m attestplane.verifier --strict`
- Rollout / migration notes: Additive only — no schema bump. Ensure the new vectors are referenced from `tests/conformance/README.md` so downstream verifiers can opt-in.

---
Plan ID: `b90ec19045702353`

Generated from accepted development plan.


Task:

- Implement the plan using focused code, test, documentation, and evidence changes.
- Keep the diff scoped to this issue.
- Update evidence under `/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-137` when behavior or validation changes.

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
