# Release Rollback Runbook

Published package versions are immutable enough that rollback means correcting
visibility and routing, not deleting history.

This runbook is for scoped release recovery after a bad or incomplete
Attestplane prerelease or stable release.

## First Response

1. Stop new publication attempts.
2. Preserve the GitHub Actions run URL, release tag, package versions, and
   registry observations.
3. Do not reuse the failed version.
4. Do not force-push, retag, or delete registry artifacts as a substitute for
   a new corrected release.

## npm Recovery

Use npm recovery only for the minimum correction:

- wrong dist-tag: move the dist-tag back to the intended version through the
  dedicated npm-management path;
- bad prerelease package: publish a new prerelease with the next ordinal;
- bad stable package: publish a patch release and move `latest` after
  validation;
- harmful package: deprecate the bad version with a clear reason.

Do not run ad-hoc local `npm publish` or local `npm dist-tag` mutation as the
normal path.

## PyPI Recovery

PyPI versions must not be deleted and re-uploaded under the same version.

Use the narrowest recovery:

- bad file or version: yank it;
- bad prerelease: publish the next prerelease ordinal;
- bad stable package: publish a patch release;
- metadata or documentation issue: correct release notes and publish a
  follow-up only if package behavior changed.

## GitHub Release Recovery

For GitHub Release assets:

1. Preserve the existing release and workflow run evidence.
2. Add a correction note.
3. Upload corrected assets only when the release tag still identifies the same
   package version and the asset correction is allowed by the release policy.
4. Otherwise cut the next prerelease or patch version.

## Verification After Recovery

After any recovery:

- check PyPI JSON for the expected version;
- check npm `versions` and `dist-tags`;
- install from a clean environment;
- run the verifier conformance and cross-SDK roundtrip gates;
- record the final registry state in release notes or validation evidence.
