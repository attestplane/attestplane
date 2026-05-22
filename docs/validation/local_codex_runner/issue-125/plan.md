# Issue 125 Implementation Plan

Plan ID: `f9ab1b6b3254613c`

## Scope

Document the v1.7.0 user-visible product delta: the strict non-empty proof-bundle
contract, minimum signed-attestation schema tightening, and SDK migration path through
`ProofBundleBuilder.minimal(...)` plus typed bundle errors.

This runner phase uses only local repository files, local command output, and the issue
text. The project-level Opus consultation requirement is not executed in this phase
because the runner prompt explicitly forbids external advisory services.

## Current Local Findings

- `docs/release-notes/v1.7.0.draft.md` exists and already mentions the non-empty bundle
  requirement, `ProofBundleBuilder.minimal(subject_digest, signer)`, typed
  `EmptyProofBundleError` / `IncompleteProofBundleError`, and the productless-release
  block, but it does not yet explicitly state that v1.7.0 is the first stable since
  v1.5.0 to carry product changes.
- The issue acceptance criteria name `docs/release-notes/v1.7.0.md`; the local release
  artifact manifest currently points to `docs/release-notes/v1.7.0.draft.md`.
- `CHANGELOG.md` currently records v1.7.0 conformance vectors under `Unreleased`, but
  does not yet provide a concise v1.7.0 integrator-facing summary.
- `docs/contributor/api-reference.md` already documents the additive `attestplane.sdk`
  namespace and the `ProofBundleBuilder`, `EmptyProofBundleError`, and
  `IncompleteProofBundleError` public symbols.
- Local git history confirms relevant commits:
  - `5b32c86` `fix: block productless stable releases`
  - `3f551d9` `feat: require non-empty proof bundles on demand`
  - `2ed64af` `Fix #121: enforce proof bundle signed schema (#126)`
  - `a4b40ea` `Fix #123: add minimum proof bundle SDK helper (#132)`
  - `f890642` `Fix #122: add negative conformance vectors (#134)`
- The issue validation command references `scripts/release/check_changelog.py`, but this
  checkout does not currently contain that file or any other script path matching
  `*check_changelog.py`.

## Implementation Approach

1. Update the active v1.7.0 release note.
   - Prefer the file expected by the issue, `docs/release-notes/v1.7.0.md`, if the
     implementation phase confirms the release-note workflow has moved from draft to final.
   - If the repository still treats draft release notes as authoritative, update
     `docs/release-notes/v1.7.0.draft.md` and record why the issue-named final path is not
     present.
   - Add explicit wording that v1.7.0 is the first stable since v1.5.0 to carry product
     changes, tying that statement to the local `5b32c86` productless-release block and
     Issue #119 context from the task text.
   - Enumerate the shipped user-visible changes:
     - non-empty bundle requirement from `3f551d9`;
     - Issue 1 minimum-schema tightening for signed attestations;
     - Issue 3 SDK builder and typed error migration path.
   - Add a three-line "What integrators must do" block:
     - stop emitting or accepting empty proof bundles;
     - emit at least one minimum-valid signed attestation with subject digest material;
     - migrate SDK callers to `ProofBundleBuilder.minimal(...)` and typed error handling.
   - Link back to planning issue #120 and this planned-task issue #125 without adding
     external secrets, signing keys, or internal runner hostnames.

2. Update `CHANGELOG.md`.
   - Add a concise v1.7.0-facing entry under `Unreleased` or the repository's established
     release-note/changelog staging location.
   - Keep the wording claim-safe: no production readiness, compliance certification,
     certified provenance, SLSA L3, or long-term archival trust claims.
   - Preserve existing historical changelog entries and do not retcon earlier releases.

3. Reconcile SDK migration notes only if needed.
   - Confirm whether `docs/contributor/api-reference.md` is sufficient as the SDK migration
     note for typed errors and the builder helper.
   - If it is too thin for integrators, add a short migration paragraph there or in the
     active v1.7.0 release note rather than creating a new broad docs surface.

4. Reconcile release-note filename references.
   - If the final file is created as `docs/release-notes/v1.7.0.md`, update local metadata
     that points at the draft only if that metadata is part of the docs contract and not a
     release artifact checksum/signing input.
   - Do not alter `release/artifacts/v1.7.0/checksums.sha256` or any signed/published
     release artifact inventory during this docs support task.

5. Preserve release and safety boundaries.
   - Treat this as docs-only.
   - Do not change release workflows, release gates, package versions, artifact hashes,
     signing configuration, or claim-safety policy.

## Files Likely To Change

- `docs/release-notes/v1.7.0.md` if the implementation phase finalizes the issue-requested
  release-note path.
- `docs/release-notes/v1.7.0.draft.md` if the repository keeps draft release notes as the
  active local source for v1.7.0.
- `CHANGELOG.md`
- `docs/contributor/api-reference.md` only if the existing SDK convenience namespace note is
  not enough for the migration-note requirement.
- `release/artifacts/v1.7.0/artifact-manifest.json` only if the release-note filename is
  intentionally finalized and the manifest is not treated as immutable post-prep evidence.

## Tests And Local Gates

Issue-required validation, adjusted for the local filename if needed:

```bash
markdownlint docs/release-notes/v1.7.0.md CHANGELOG.md
python scripts/release/check_changelog.py --version 1.7.0
```

If `docs/release-notes/v1.7.0.md` still does not exist after implementation, run the
markdownlint command against `docs/release-notes/v1.7.0.draft.md` and record the path
reconciliation in evidence.

If `scripts/release/check_changelog.py` is still absent, record that exact local blocker in
test evidence and run the closest available release-doc validation without weakening the
issue acceptance criteria.

Additional local checks:

```bash
rg -n "v1\\.7\\.0|ProofBundleBuilder\\.minimal|EmptyProofBundleError|IncompleteProofBundleError|bundle\\.schema\\.incomplete" \
  CHANGELOG.md docs/release-notes docs/contributor/api-reference.md
rg -n "production-ready|compliance certification|SLSA L3|signing key|internal runner" \
  CHANGELOG.md docs/release-notes/v1.7.0*
```

No full product gate is required for docs-only text unless the implementation phase touches
release automation, SDK code, schemas, or artifact manifests. If touched, run the nearest
local release gate and record the result.

## Risk Classification

P2, low implementation risk.

The change is documentation-only and should not alter runtime behavior. The main risk is
release-contract ambiguity: the issue asks for `docs/release-notes/v1.7.0.md`, while local
release evidence currently points at `docs/release-notes/v1.7.0.draft.md`. The implementation
must avoid accidentally rewriting immutable release artifacts or implying that packages were
republished. A secondary risk is overclaiming the release; wording must stay within the
existing explicit boundaries and claim-safety policy.

## Evidence Files To Update

- `docs/validation/local_codex_runner/issue-125/plan.md` for this planning phase.
- `docs/validation/local_codex_runner/issue-125/code.md` in the implementation phase,
  listing exact docs files changed and any filename reconciliation.
- `docs/validation/local_codex_runner/issue-125/test.md` in the validation phase, with exact
  markdownlint and changelog-check command output or documented local blockers.
- `docs/validation/local_codex_runner/issue-125/review.md` in the review phase, confirming
  the three-line integrator block, planning issue link, release-boundary language, and absence
  of secrets, signing keys, and internal runner hostnames.

## Safety Confirmation

This task will not merge branches, create tags, move tags, publish npm packages, publish
PyPI packages, push to PyPI, push to any remote, or weaken release gates. It will not lower
P0/P1 severity, remove failing tests to manufacture a pass, loosen release gates, loosen
claim-safety policy, or read/log credentials files such as ChatGPT cookies, GitHub tokens,
OpenAI tokens, private keys, `.pypirc`, or `.npmrc`.
