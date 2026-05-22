# Issue 125 Review Evidence

Plan ID: `f9ab1b6b3254613c`

## Acceptance Review

- Release note states that v1.7.0 is the first stable since v1.5.0 to carry
  user-visible product changes.
- Release note enumerates:
  - non-empty proof-bundle rejection from `3f551d9`;
  - Issue 1 minimum signed-attestation schema tightening;
  - Issue 3 `ProofBundleBuilder.minimal(...)` migration path and typed
    `EmptyProofBundleError` / `IncompleteProofBundleError` handling.
- Release note includes the required three-line "What Integrators Must Do"
  block.
- Release note links the issue references for Issue #120 and Issue #125.
- SDK migration wording is present in `docs/contributor/api-reference.md`.
- Wording remains docs-only and does not state that packages were republished,
  tags moved, or release assets regenerated.
- No secrets, signing keys, private credentials, or internal runner hostnames
  were added.
