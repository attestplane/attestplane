# Issue 141 Implementation Plan

Plan ID: `8bed96c40b295da3`

## Scope

Extend the Issue #125 documentation deliverable with a focused `v1.7.1`
sub-section that covers the SDK and CLI delta carried by the three local product
tasks:

- Issue 1 / Issue #137: additive canonicalization conformance vectors for the
  minimum proof-bundle helper and strict verifier.
- Issue 2 / Issue #138: explicit `attestplane verify` opt-in flags
  `--require-non-empty` and `--strict-schema`.
- Issue 3 / Issue #139: signed-schema round-trip regression for the minimum
  signed-attestation bundle behavior.

This runner phase uses only local repository files, local command output, and
the issue text. The project-level Opus consultation requirement is not executed
in this phase because the runner prompt explicitly forbids external advisory
services.

## Current Local Findings

- `docs/changes/` does not exist in this checkout, but Issue #141 names
  `docs/changes/v1.7.x.md` as the validation target.
- Issue #125 implemented its deliverable through
  `docs/release-notes/v1.7.0.md`,
  `docs/release-notes/v1.7.0.draft.md`, `CHANGELOG.md`, and
  `docs/contributor/api-reference.md`.
- `docs/release-notes/v1.7.1.draft.md` exists, but it is currently a release
  cut summary and does not provide the requested SDK/CLI integration snippets.
- `README.md` does not currently expose an explicit "What's new" section
  heading in the inspected local content, so the implementation must either add
  a small claim-safe anchor or update the nearest existing release/status anchor
  only if that matches the repository's docs style.
- The implementation must not land the docs before the corresponding product
  changes for Issues #137, #138, and #139 are present locally and validated.

## Implementation Approach

1. Create or update the active v1.7.x change document.
   - Preferred path: create `docs/changes/v1.7.x.md`, because the issue's
     validation command names that exact file and the directory is absent.
   - Keep it as a concise change/reference page, not release marketing.
   - Include a `## v1.7.1 SDK + CLI Delta` sub-section that explicitly says it
     extends the Issue #125 v1.7.0 summary rather than replacing or duplicating
     it.
   - Link back to the existing Issue #125 release-note/API-reference surfaces
     where useful.

2. Cover the three required product increments.
   - Conformance vectors: summarize the new canonicalization vectors from
     Issue #137 and note that they are additive; do not imply a schema bump or
     churn to existing v1.7.x fixture hashes unless the implementation evidence
     proves that happened.
   - CLI flags: document `attestplane verify <bundle> --require-non-empty` and
     `--strict-schema`, preserving the local finding that default `verify`
     behavior remains unchanged.
   - Round-trip regression: document the signed-schema byte-identical
     round-trip guard from Issue #139 as a regression test, not a new runtime
     verification claim.

3. Add one concrete snippet per requested surface.
   - SDK snippet: use the current local public surface,
     `attestplane.sdk.ProofBundleBuilder.minimal(subject_digest, signer)`,
     with typed `EmptyProofBundleError` / `IncompleteProofBundleError` handling
     if the final local API remains the same.
   - CLI snippet: show a single `attestplane verify` invocation using the new
     strict opt-in flags against the issue-approved/local fixture path.
   - Keep snippets copy-pasteable and free of secrets, real keys, tokens,
     private hostnames, or publication commands.

4. Update SDK and CLI reference surfaces only as pointers.
   - Add a short v1.7.1 pointer in `docs/contributor/api-reference.md` if the
     SDK snippet needs to be discoverable from the SDK reference.
   - Add a short CLI-reference pointer in
     `docs/usage/cli_proofbundle_verifier_alpha.md` or the locally discovered
     CLI reference if it remains the best canonical CLI docs surface.
   - Do not edit runtime CLI or SDK code in this docs issue.

5. Add the README cross-link.
   - Add or update a small "What's new" anchor in `README.md` that links to
     `docs/changes/v1.7.x.md#v171-sdk--cli-delta`.
   - Use neutral wording only: version, surface, and link. No promotional
     language, compliance claims, production-readiness claims, or release
     expansion claims.

6. Preserve release and product boundaries.
   - Before implementation closure, confirm Issues #137, #138, and #139 have
     corresponding local code/test evidence and passing validation.
   - If any product PR is missing or failing, leave the docs branch unlanded and
     record the dependency blocker in Issue #141 evidence.
   - Do not modify release artifacts, package versions, checksums, signed
     provenance files, release workflows, or gate policy.

## Files Likely To Change

- `docs/changes/v1.7.x.md` (new; preferred issue-named deliverable)
- `README.md`
- `docs/contributor/api-reference.md` only if a SDK-reference pointer is needed
- `docs/usage/cli_proofbundle_verifier_alpha.md` or the discovered CLI reference
  only if a CLI-reference pointer is needed
- `docs/release-notes/v1.7.1.draft.md` only if the repository treats release
  notes, rather than `docs/changes/`, as the active Issue #125 extension point
- `CHANGELOG.md` only if local docs convention requires all user-visible
  reference deltas to also appear under `Unreleased`

Files that should not change for this docs task:

- SDK or CLI runtime implementation files
- conformance vector JSON files or fixture hash locks
- release artifact manifests, checksums, cosign bundles, SLSA provenance, or
  package metadata
- release workflows, release gates, claim-safety policy, or severity policy

## Tests And Local Gates

Issue-required validation:

```bash
markdownlint docs/changes/v1.7.x.md
python -m pytest docs/ --doctest-glob='*.md'
```

If this checkout still lacks a docs doctest harness, record that exact local
result in `test.md` and run a manual snippet smoke instead:

```bash
PYTHONPATH=sdk/python/src python -m pytest docs/ --doctest-glob='*.md' -q
rg -n "v1\\.7\\.1|ProofBundleBuilder\\.minimal|--require-non-empty|--strict-schema|round-trip|canonicalization" \
  README.md docs/changes/v1.7.x.md docs/contributor/api-reference.md docs/usage
```

Dependency checks before the docs are considered landable:

```bash
PYTHONPATH=sdk/python/src pytest tests/conformance -k canonicalization -x
PYTHONPATH=sdk/python/src pytest tests/cli/test_verify_flags.py -x
PYTHONPATH=sdk/python/src pytest tests/verifier/test_signed_schema_roundtrip.py -x -vv
PYTHONPATH=sdk/python/src pytest tests/conformance -k signed_schema -x
```

Focused markdown checks for touched docs:

```bash
markdownlint README.md docs/changes/v1.7.x.md docs/contributor/api-reference.md docs/usage/cli_proofbundle_verifier_alpha.md
```

Local gate before closure:

```bash
run_gate attestplane
```

If `run_gate attestplane` is unavailable in this checkout, record the exact
failure in test evidence and run the focused docs/product validation commands
above without weakening the required release gates.

## Risk Classification

P2, low-to-medium risk.

The intended change is documentation-only, so runtime risk is low. The main risk
is sequencing: Issue #141 explicitly must not land before the product PRs for
Issues #137, #138, and #139 merge. The second risk is documentation-path
ambiguity because the issue names `docs/changes/v1.7.x.md`, while the current
Issue #125 evidence used release notes, changelog, and API reference files. The
mitigation is to create the issue-named `docs/changes/` page as a thin extension
and cross-link rather than duplicating the full Issue #125 release summary.

Claim-safety risk is also present because README/release wording can easily
overstate verifier or compliance guarantees. All wording should stay within the
existing pre-GA, non-certification, no-production-readiness boundaries.

## Evidence Files To Update

- `docs/validation/local_codex_runner/issue-141/plan.md` for this planning
  phase.
- `docs/validation/local_codex_runner/issue-141/code.md` in the implementation
  phase, listing exact docs files changed and the product-PR dependency status.
- `docs/validation/local_codex_runner/issue-141/test.md` in the validation
  phase, with exact markdownlint, doctest/manual snippet smoke, dependency
  checks, and any unavailable gate notes.
- `docs/validation/local_codex_runner/issue-141/review.md` if a later review
  phase is run, confirming no duplication of Issue #125, no marketing copy, and
  no release-boundary changes.
- `docs/validation/local_codex_runner/issue-141/gate_report.md` /
  `gate_report.json` if the local runner records gate output in the same format
  as nearby issues.

Do not update release artifacts, package publishing evidence, signed checksums,
schema locks, or fixture hash locks for this docs-only task.

## Safety Confirmation

This task will not merge branches, create tags, move tags, publish npm packages,
publish PyPI packages, push to PyPI, push to any remote, or weaken release
gates. It will not lower P0/P1 severity, remove failing tests to manufacture a
pass, loosen release gates, loosen claim-safety policy, or read/log credentials
files such as ChatGPT cookies, GitHub tokens, OpenAI tokens, private keys,
`.pypirc`, or `.npmrc`.
