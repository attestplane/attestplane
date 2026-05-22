# Local Codex Runner Code Prompt

You are working in Attestplane on Issue #154.

Issue title: [P1][verifier] Cross-wire canonicalization edge-case vectors into the signed-schema round-trip regression
Issue URL: https://github.com/attestplane/attestplane/issues/154
Labels: priority:P1, area:verifier, planned-task, auto-codex-approved
Evidence directory: `/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-154`
Plan path: `/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-154/plan.md`

Issue body:
Source planning issue: #153
- Priority: P1
- Affected modules: `verifier` (conformance fixture loader + round-trip regression added in #146), `conformance` vectors directory extended by #150.
- Acceptance criteria:
  - The signed-schema round-trip regression introduced in #146 iterates over every canonicalization edge-case vector added by #150 (UTF-8 normalization, key ordering, number coercion, escaped-slash cases) instead of only the original minimum-bundle fixture.
  - Test fails loudly with a vector-id-tagged assertion message when any vector breaks round-trip equivalence, so a regression points to a specific fixture rather than a generic mismatch.
  - Vectors are loaded from a single shared manifest reused by the SDK helper (#132/#150) and the verifier — no parallel hard-coded list in the test file.
  - Existing PASS cases keep passing; no fixture lock churn beyond the one new manifest entry, if any.
- Validation commands:
  - `cargo test -p attestplane-verifier signed_schema_round_trip` (or workspace equivalent: `pnpm test --filter verifier round_trip` / `pytest verifier/tests/test_signed_schema_round_trip.py`) — must enumerate ≥ all #150 vector ids in test output.
  - `cargo test -p attestplane-conformance` (full conformance suite) to confirm shared manifest still resolves for the SDK helper path.
  - `git grep -n "canonicalization" verifier/tests` to confirm there is exactly one place loading the manifest.
- Rollout / migration notes: Pure test/infra hardening of an existing P1 regression; no public API or wire-format change. Safe to land on `main` without a feature flag. If the shared manifest path is moved, update the SDK helper import in one commit to avoid a transient broken build. Reference #137/#139/#150 in PR body so reviewers see the chain.

---
Plan ID: `e2e4a0599bd4718a`

Generated from accepted development plan.


Task:

- Implement the plan using focused code, test, documentation, and evidence changes.
- Keep the diff scoped to this issue.
- Update evidence under `/Users/macworkers/Projects/attestplane-local-runner/docs/validation/local_codex_runner/issue-154` when behavior or validation changes.

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
