<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Verifying Attestplane release signatures and provenance

Attestplane signs new release artifacts with Sigstore keyless cosign and
attaches SLSA Build L3 provenance through the upstream
[slsa-github-generator](https://github.com/slsa-framework/slsa-github-generator).
This document gives the end-to-end commands a downstream consumer or
third-party auditor can run to verify a published release.

## Scope and disclaimers

- **Forward-only.** Signing and provenance apply to new releases
  published after [ADR-0018](../adr/0018-keyless-signing-and-slsa-provenance.md)
  lands. Releases tagged before that decision (including all of
  `v0.0.x`, `v0.7.x`, `v0.8.x`, and the early `v0.9.x` line) are not
  retroactively signed and were never retagged for signing.
- **No legal compliance claim.** Verifying a signature confirms the
  artifact was produced by the Attestplane release workflow on
  GitHub Actions. It does not assert EU AI Act compliance,
  certification, or any regulatory conclusion for any deployment
  that consumes the artifact.
- **No production-readiness claim.** The substrate remains alpha
  while pre-`1.0` versions are published; signature evidence does not
  change that.

## Prerequisites

Install the verification tooling once:

```sh
# cosign for signature verification (https://docs.sigstore.dev/cosign/installation/)
brew install cosign        # macOS
# or follow upstream install docs for Linux / Windows

# slsa-verifier for provenance verification
go install github.com/slsa-framework/slsa-verifier/v2/cli/slsa-verifier@v2.7.1
```

## Step 1 — Download the release assets

Pick the release tag you intend to verify and download every published
asset for it. Example for tag `vX.Y.Z`:

```sh
TAG=vX.Y.Z
mkdir -p attestplane-${TAG} && cd attestplane-${TAG}

gh release download "${TAG}" \
  --repo attestplane/attestplane \
  --pattern "*"
ls -1
```

A signed release contains, at minimum:

| Asset class            | Examples                                      |
|------------------------|-----------------------------------------------|
| Python wheel + sdist   | `attestplane-X.Y.Z-py3-none-any.whl`, `attestplane-X.Y.Z.tar.gz` |
| npm tarball            | `attestplane-attestplane-X.Y.Z.tgz`           |
| CycloneDX SBOMs        | `*.cdx.json`, `*.cdx.xml`                      |
| Sigstore bundles       | `*.cosign.bundle`, `*.sig`, `*.pem`            |
| SLSA provenance        | `attestplane-${TAG}.intoto.jsonl`              |

If the signature bundles or the `.intoto.jsonl` provenance file are
absent, the release pre-dates ADR-0018 and is not covered by this
document.

## Step 2 — Verify each artifact with cosign keyless

For every primary artifact (wheel, sdist, npm tarball, SBOM file),
verify the keyless signature bundle:

```sh
TAG=vX.Y.Z
REPO=attestplane/attestplane

for artifact in *.whl *.tar.gz *.tgz *.cdx.json *.cdx.xml; do
  [ -e "$artifact" ] || continue
  cosign verify-blob \
    --bundle "${artifact}.cosign.bundle" \
    --certificate-identity-regexp \
      "^https://github.com/${REPO}/\.github/workflows/sign-release\.yml@refs/tags/${TAG}\$" \
    --certificate-oidc-issuer \
      "https://token.actions.githubusercontent.com" \
    "$artifact"
done
```

A successful run prints `Verified OK` for each artifact. Any failure
must be treated as a verification failure for the whole release: do
not selectively trust partial results.

The `--certificate-identity-regexp` value pins the verifier to
**signatures produced by Attestplane's own `sign-release.yml` workflow
at the exact requested tag**. Substituting a different workflow,
repository, or tag breaks verification by design.

## Step 3 — Verify SLSA Build L3 provenance

The `*.intoto.jsonl` file is the in-toto attestation produced by the
upstream slsa-github-generator. Validate it with slsa-verifier against
each artifact:

```sh
TAG=vX.Y.Z
PROVENANCE="attestplane-${TAG}.intoto.jsonl"

for artifact in *.whl *.tar.gz *.tgz *.cdx.json *.cdx.xml; do
  [ -e "$artifact" ] || continue
  slsa-verifier verify-artifact "$artifact" \
    --provenance-path "${PROVENANCE}" \
    --source-uri github.com/attestplane/attestplane \
    --source-tag "${TAG}"
done
```

`slsa-verifier` checks that:

- The artifact's SHA-256 digest appears as a subject in the
  attestation.
- The attestation was issued by the pinned upstream generator
  workflow at the recorded commit.
- The source repository and tag match what was requested.

If any of those checks fail, the artifact is not provenance-bound to
this release and must not be deployed on the basis of this attestation.

## Step 4 — (Optional) Reproduce the CycloneDX SBOM digest

Each release attaches CycloneDX SBOMs for the Python and TypeScript
SDKs. Independent reproduction is out of scope for this guide, but
the SBOMs are themselves signed (Step 2) and provenance-bound (Step 3)
so downstream consumers can reason about the build inputs without
trusting any Attestplane-hosted service.

## What signature evidence does and does not buy you

| Question                                                        | Answer                                                                                   |
|-----------------------------------------------------------------|------------------------------------------------------------------------------------------|
| Was this artifact built by the Attestplane release workflow?    | Yes, if cosign verify-blob passes against the pinned identity.                            |
| Was it built from the tagged source tree?                       | Yes, if slsa-verifier passes against the source-tag.                                      |
| Is the artifact safe to deploy in a high-risk AI system?        | Out of scope. Provenance is supply-chain evidence, not a deployment safety conclusion.    |
| Does Attestplane certify EU AI Act compliance for the consumer? | No. See [`docs/spec/aia-12-aligned-profile.md`](../spec/aia-12-aligned-profile.md) — Attestplane provides Article-12-aligned evidence substrate primitives, not compliance certification. |
| Can I rely on a hosted Attestplane API for verification?        | No. Verification must use the offline tooling above; hosted endpoints are convenience only, per [`docs/architecture/verifier_independence.md`](../architecture/verifier_independence.md). |

## Worked example: v1.0.9

Tag `v1.0.9` is the first Attestplane release whose assets carry the
**complete** supply-chain evidence chain — both Sigstore keyless
cosign bundles and SLSA Build L3 provenance — attached to a single
release. The release was tagged at 2026-05-20T21:32:20Z, after both
[ADR-0018](../adr/0018-keyless-signing-and-slsa-provenance.md) and the
SLSA generator pin fix
([PR #32](https://github.com/attestplane/attestplane/pull/32),
merged 2026-05-20T21:55:37Z) landed, so it is the first tag the
corrected workflow could populate end-to-end.

Inventory on `v1.0.9` after the
[`sign-release.yml` execute run](https://github.com/attestplane/attestplane/actions/runs/26192598447)
and the
[`slsa-provenance.yml` execute run](https://github.com/attestplane/attestplane/actions/runs/26192349031):

```
artifact-manifest.json
artifact-manifest.json.cosign.bundle
checksums.sha256
checksums.sha256.cosign.bundle
upload-plan.md
upload-plan.md.cosign.bundle
attestplane-v1.0.9.intoto.jsonl
attestplane-v1.0.9.intoto.jsonl.cosign.bundle
```

Reproducible verification on any workstation with `cosign v3.0.6+`
and `slsa-verifier v2.7.1+`:

```sh
TAG=v1.0.9
REPO=attestplane/attestplane
mkdir -p attestplane-${TAG} && cd attestplane-${TAG}
gh release download "${TAG}" --repo "${REPO}"

# Step A — cosign keyless on each primary artifact
for asset in artifact-manifest.json checksums.sha256 upload-plan.md; do
  cosign verify-blob \
    --bundle "${asset}.cosign.bundle" \
    --certificate-identity-regexp \
      "^https://github.com/${REPO}/\.github/workflows/sign-release\.yml@refs/heads/main\$" \
    --certificate-oidc-issuer \
      "https://token.actions.githubusercontent.com" \
    "${asset}"
done

# Step B — SLSA Build L3 provenance on the same artifacts
for asset in artifact-manifest.json checksums.sha256 upload-plan.md; do
  slsa-verifier verify-artifact "${asset}" \
    --provenance-path "attestplane-${TAG}.intoto.jsonl" \
    --source-uri github.com/${REPO}
done
```

Expected output:

- Step A prints `Verified OK` for each of the three primary artifacts.
- Step B prints `PASSED: SLSA verification passed` for each of the
  three primary artifacts and reports the builder identity
  `https://github.com/slsa-framework/slsa-github-generator/.github/workflows/generator_generic_slsa3.yml@refs/tags/v2.1.0`.

Two notes on the identity-pinning choices in this example:

- The cosign `--certificate-identity-regexp` pins to `refs/heads/main`
  because the `workflow_dispatch` that produced `v1.0.9`'s signatures
  was triggered from `main`. Once signing is wired into
  `release-cd.yml` per ADR-0018, the identity will pin to
  `refs/tags/${TAG}` and this example will switch to that form.
- The slsa-verifier call omits `--source-tag` for the same reason —
  the provenance was generated from a `main`-dispatched run, not a
  tag-triggered one. The source repository is still pinned via
  `--source-uri`, and the upstream generator identity is verified
  inside slsa-verifier. Once the workflow path is tag-triggered the
  example will add `--source-tag "${TAG}"`.

Either form is a complete verification — the pinning is what binds the
evidence to a specific workflow definition and source repository, not
to any single branch or tag form.

### Historical: v1.0.8 (cosign-only)

Tag `v1.0.8` was the project's first cosign-signed release
([`sign-release.yml` execute run `26191173510`](https://github.com/attestplane/attestplane/actions/runs/26191173510)),
but it carries cosign bundles **only**. The SLSA generator pin fix
in [PR #32](https://github.com/attestplane/attestplane/pull/32)
(reconciling ADR-0018 §"Tag-ref vs SHA-pin caveat") merged after
`v1.0.8` was signed, so the SLSA leg was never attempted in execute
mode against that tag. `v1.0.9` is the first tag with the complete
chain; `v1.0.8` remains in the release inventory as historical
cosign-only evidence and is not retroactively re-signed for SLSA.

## Reporting verification failures

If `cosign verify-blob` or `slsa-verifier verify-artifact` fails on a
published release with this evidence attached, open an issue on
`https://github.com/attestplane/attestplane/issues` with:

- The release tag.
- The exact command invocation and its error output.
- The artifact filename and its SHA-256 digest.
- Whether the `.cosign.bundle` and `*.intoto.jsonl` files were
  present and downloaded successfully.

Treat any unexplained verification failure as a release-integrity
incident until proven otherwise.
