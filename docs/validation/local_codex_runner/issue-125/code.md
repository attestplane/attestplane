# Issue 125 Code Evidence

Plan ID: `f9ab1b6b3254613c`

Implemented the v1.7.0 user-visible documentation delta as a docs-only change.

## Files Changed

- `docs/release-notes/v1.7.0.md`
  - Added the issue-requested final release-note path.
  - States that v1.7.0 is the first stable since v1.5.0 to carry
    user-visible product changes.
  - Enumerates the non-empty bundle requirement from `3f551d9`, Issue 1
    minimum signed-attestation schema tightening, and Issue 3 SDK builder plus
    typed errors.
  - Includes the three-line "What Integrators Must Do" block.
  - Links the issue references back to the GitHub URLs for Issue #120 and
    Issue #125.
- `docs/release-notes/v1.7.0.draft.md`
  - Kept the draft release note in sync because
    `release/artifacts/v1.7.0/artifact-manifest.json` still names the draft as
    `release_notes_file`.
  - Did not modify artifact hashes, upload plans, release metadata, tags, or
    publish workflows.
- `CHANGELOG.md`
  - Added a concise v1.7.0 integrator-facing delta under `Unreleased`.
- `docs/contributor/api-reference.md`
  - Added a short SDK migration note for
    `ProofBundleBuilder.minimal(subject_digest, signer)`,
    `EmptyProofBundleError`, and `IncompleteProofBundleError`.
- `docs/validation/local_codex_runner/issue-125/*.md`
  - Escaped raw issue titles such as `\[P2]\[docs]` in runner prompt/evidence
    markdown so markdownlint does not parse them as undefined reference links.
  - Added required blank lines around prompt lists and removed extra blank
    lines flagged by markdownlint.

## Scope Confirmation

No release artifacts, package versions, signing metadata, publish workflows,
tags, remotes, or release gates were changed.
