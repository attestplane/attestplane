<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Current State Gap Sweep — 2026-05-19

## Scope

This sweep records the state after the FreeTSA recovery commit that fixed
SHA-512 ECDSA timestamp verification, manually dispatching the
`nightly-anchor` workflow, closing #11, and posting a conservative
design response on #7.

No tag, release, publish, deploy, or package upload was performed.

## Repository State

- Branch: `main`
- HEAD: `0ba5b323217fd6d1dbcdf63a48b08ad1e60826d1`
- `origin/main`: `0ba5b323217fd6d1dbcdf63a48b08ad1e60826d1`

## Remote CI State

Verified push workflows for the FreeTSA recovery commit completed successfully:

- `ci`
- `sdk-python`
- `sdk-typescript`
- `cross-sdk-roundtrip`
- `invariants`
- `codeql`
- `reproducible-build`
- `ossf-scorecard`
- `osv-scanner`
- `sbom`

Manual live FreeTSA verification:

- Workflow: `nightly-anchor`
- Event: `workflow_dispatch`
- Run: <https://github.com/attestplane/attestplane/actions/runs/26085036796>
- HEAD: `0ba5b323217fd6d1dbcdf63a48b08ad1e60826d1`
- Conclusion: `success`
- Result: `cert_status=VALID`, `ok=true`, `chain_ok=true`

## Issue State

### Closed

- [#11](https://github.com/attestplane/attestplane/issues/11)
  was closed after the remote live `nightly-anchor` verification
  passed on the fix commit.

### Still Open

- [#7](https://github.com/attestplane/attestplane/issues/7)
  remains open. A conservative design response was posted:
  <https://github.com/attestplane/attestplane/issues/7#issuecomment-4485790505>

Keeping #7 open is intentional. It requires owner confirmation before
turning the response into implementation work or public-facing claims.

## Package / Release Surface

- PyPI contains pre-release `attestplane==0.0.3a0`.
- `pip index versions attestplane` without `--pre` reports no stable
  matching distribution because `0.0.3a0` is a pre-release.
- TestPyPI contains `0.0.1` and `0.0.3a0`.
- npm `latest` remains `0.0.1-alpha.1`.
- npm `alpha` points to `0.0.3-alpha`.
- GitHub Release `v0.0.3-alpha` remains a prerelease with 5 assets.
- No release asset, tag, or package state was modified by this sweep.

## Remaining Tasks

1. **P0:** Owner-confirm #7 public stance before implementing AIA-12
   profile or GDPR deletion-proof language.
2. **P1:** Add an AIA-12 aligned profile document with explicit
   non-certification wording.
3. **P1:** Document verifier independence: OSS verifier and versioned
   schemas are the trust root; API is convenience only.
4. **P1:** Draft retention/deletion proof ADR for PII minimization plus
   commit-then-redact.
5. **P1:** Decide whether to cut a new alpha release that includes the
   FreeTSA verifier fix. This would require a new release artifact
   generation/freeze flow rather than modifying frozen
   `v0.0.3-alpha` artifacts.

## Claim Safety

- Production-ready claim: false
- Compliance certification claim: false
- EU AI Act compliance claim: false
- GDPR compliance claim: false
- Release or publish performed: false

## Explicit Non-Actions

- tag: not performed
- release: not performed
- publish: not performed
- deploy: not performed
- workflow_dispatch: performed only for `nightly-anchor` verification
  run `26085036796`
- secrets printed: false

## Final Status

`current_state_gap_sweep_recorded`
