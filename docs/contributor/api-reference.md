# API reference (auto-generated)

This page explains how Attestplane generates API reference material for both SDKs from the
source code itself, and how to consume the artifact-only and published surfaces.

Until 2026-05-21 all SDK reference material lived inside ADRs and prose docs and was
hand-maintained. Audit agent 16 noted: "no auto API reference for either Python or TypeScript
SDK; all reference material is in ADRs/docs but not derived from code". This workflow closes
that gap by rendering reference material straight from the published symbols on every PR and
every push to `main`.

## What is generated

Two static HTML bundles, produced on every triggering run:

- **Python SDK** &mdash; rendered by [`pdoc`](https://pdoc.dev/) from
  `sdk/python/src/attestplane/`. Output directory: `api-ref-python/`.
- **TypeScript SDK** &mdash; rendered by [`typedoc`](https://typedoc.org/) from
  `sdk/typescript/src/index.ts` (the public entry point). Output directory:
  `api-ref-typescript/`.

The workflow that drives both renders is
[`.github/workflows/api-ref.yml`](../../.github/workflows/api-ref.yml). It is read-only:
it does not push to any branch, move any tag, or publish anywhere. A separate
post-release staging step publishes stable release-line docs after release CD succeeds.

## How to download the artifact

1. Open the PR or commit you want the reference for.
2. Click the **Checks** tab → `api-ref` workflow run.
3. Scroll to the **Artifacts** section at the bottom of the run summary.
4. Download `api-ref-python-<sha>.zip` or `api-ref-typescript-<sha>.zip`.
5. Unzip locally and open `index.html` in a browser.

Artifacts are retained for 60 days and remain the debugging path when you need the raw
render output for a specific commit or pull request.

## Per-PR rendering vs `main` rendering

- **Pull requests** &mdash; the workflow runs whenever a PR touches anything under `sdk/**`,
  so reviewers can preview how a change reads in the rendered API reference before merge.
- **`main` push** &mdash; the same workflow runs on every push to `main`, so the latest
  reference for `main` is always one click away from the most recent commit.
- **Manual** &mdash; the workflow also accepts `workflow_dispatch` for ad-hoc renders.

## Published stable docs

Stable release API reference is published to GitHub Pages after the release CD gate passes.
The stable surface is versioned by release line and exact stable release:

- The `latest` Pages surface redirects to the latest suffix-free stable release.
- The exact release snapshot path uses `vX.Y.Z` for stable tags such as `v1.5.0`.
- The stable line alias path uses `vX.Y` for a release line such as `v1.5`.

Prerelease tags may still render artifacts through the read-only workflow, but they do not
move the public `latest` pointer or publish to the stable Pages surface.

## Limitations

- **Artifact-only remains available.** The HTML artifact output still exists for debugging
  and review even though stable releases are published to GitHub Pages.
- **Quality follows docstrings.** The API reference is auto-generated from docstrings
  (Python) and TSDoc comments (TypeScript). Gaps in the rendered output are not bugs in this
  workflow &mdash; they are missing or thin docstrings in the SDK source. If you spot a gap,
  the fix is to improve the docstring; see
  [`first-pr-walkthrough.md`](first-pr-walkthrough.md) for how to land that change.
- **Public surface only.** TypeScript rendering starts from `src/index.ts`, so anything not
  re-exported there is invisible. Python rendering starts at the `attestplane` package, so
  underscore-prefixed names are excluded.
- **SDK convenience namespace.** Python also exposes additive convenience imports from
  `attestplane.sdk`, including `ProofBundleBuilder`, `EmptyProofBundleError`, and
  `IncompleteProofBundleError`. These names render from their source docstrings and must stay
  listed in the relevant module `__all__` values when changed.

## v1.7.0 proof-bundle migration note

Strict proof-bundle callers should migrate construction to
`attestplane.sdk.ProofBundleBuilder.minimal(subject_digest, signer)` when they
need the minimum signed-attestation bundle shape accepted by the v1.7.0
non-empty verifier contract. SDK integrations that raise on verification
failures should catch `EmptyProofBundleError` for bundles with no proof events
and `IncompleteProofBundleError` for bundles that are non-empty but lack the
minimum signed-attestation schema.

## Future work

The published surface currently targets stable release tags only. If a future release train
needs a preview or branch-specific API reference, that should land as a separate surface so
the stable `latest` pointer stays pinned to suffix-free stable releases.
