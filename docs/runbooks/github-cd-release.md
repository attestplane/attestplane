# GitHub CD Release Runbook

GitHub Actions CD is the only supported package publication path for
Attestplane releases.

Local machines may prepare code, update package versions, run gates, commit,
push, create an intentional release tag, and manually dispatch the release CD
workflow. Local machines must not run `npm publish`, `twine upload`, direct
PyPI upload commands, or ad-hoc npm dist-tag mutation as a substitute for CD.

## Release Workflow

The unified entrypoint is:

```text
.github/workflows/release-cd.yml
```

`release-cd` is the GitHub Actions publication stage connected to
[`autodev-train`](autodev-train.md). `autodev-train` may prepare and validate a
release, but registry publication still runs here.

It coordinates the existing SDK publication workflows:

- `.github/workflows/publish-python.yml`
- `.github/workflows/publish-typescript.yml`

The CD workflow validates the requested release tag, validates Python and npm
package versions, computes the npm dist-tag policy, runs build-only package
gates, publishes through GitHub-hosted runners when `dry_run=false`, and then
verifies PyPI and npm registry visibility.

## Version Mapping

| Git tag | PyPI version | npm version | npm dist-tag |
|---|---|---|---|
| `v0.8.0-alpha.0` | `0.8.0a0` | `0.8.0-alpha.0` | `alpha` |
| `v0.8.0-beta.0` | `0.8.0b0` | `0.8.0-beta.0` | `beta` |
| `v0.8.0-rc.1` | `0.8.0rc1` | `0.8.0-rc.1` | `rc` |
| `v0.8.0` | `0.8.0` | `0.8.0` | `latest` |

Pre-release packages must publish under their matching `alpha`, `beta`, or
`rc` dist-tag. A pre-release must not be published with npm `latest` unless a
separate maintainer decision is recorded before dispatch. The default CD path
does not provide that override.

The detailed npm dist-tag policy and the current `0.8.0-beta.0` latest
decision are recorded in
[`npm-dist-tag-policy.md`](../release/npm-dist-tag-policy.md).

## Manual Dispatch

Dry-run validation:

```bash
gh workflow run release-cd.yml \
  -f release_tag=v0.8.0-rc.1 \
  -f channel=rc \
  -f dry_run=true
```

Real publication:

```bash
gh workflow run release-cd.yml \
  -f release_tag=v0.8.0-rc.1 \
  -f channel=rc \
  -f dry_run=false
```

The real publication path publishes to PyPI and npm only after the CD preflight
and build gates pass. It does not force-push, move existing tags, or create
unrelated tags.

## Required Pre-Dispatch Checks

Before dispatching a real release:

1. Package versions in `sdk/python/pyproject.toml` and
   `sdk/typescript/package.json` must match the intended tag.
2. Release notes must describe the claim boundary and registry policy.
3. Local gates for conformance, cross-SDK behavior, fixture hashes, and public
   API drift must pass.
4. The release tag must point at the reviewed commit.
5. The maintainer must confirm the npm dist-tag is correct for the channel.

## Trusted Publishing

PyPI publication uses GitHub OIDC trusted publishing through
`pypa/gh-action-pypi-publish`.

npm publication first attempts trusted publishing with provenance from a
GitHub-hosted runner. `NPM_TOKEN` is only a fallback for the existing npm
workflow and must never be printed, echoed, or embedded in logs.

## Rollback

Do not delete or reuse a published version.

- npm: move or remove an incorrect dist-tag with the dedicated npm-management
  workflow, and deprecate a bad version when needed.
- PyPI: yank a bad file or version; do not delete and re-upload the same
  version.
- GitHub workflow: revert the release workflow change and re-dispatch only
  after review.
- Broken RC: publish a new `v0.8.0-rc.N+1` with a changelog entry.

Use the scoped recovery checklist in
[`release-rollback.md`](release-rollback.md) before mutating registry state.

## Explicit Non-Goals

The CD path does not make the pre-GA line production-ready, GA, certified,
legally compliant, or SLSA L3. Registry publication proves package availability
and reproducible release process hygiene; it does not prove regulatory
admissibility.
