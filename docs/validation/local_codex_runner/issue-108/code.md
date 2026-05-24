# Issue 108 Implementation Note

Plan ID: `52b4e25efe3a15b7`

## Outcome

Updated the release boundary documentation so the local `v1.6.1` record names
the actual product-impacting change and preserves the tag pointer.

- [`CHANGELOG.md`](/Users/macworkers/Projects/attestplane-lane-p0/CHANGELOG.md)
  now has a `v1.6.1 boundary note` that links the fix commit and states that
  `v1.6.1` still points at `f2a55d4`.
- [`docs/release-notes/v1.6.1.draft.md`](/Users/macworkers/Projects/attestplane-lane-p0/docs/release-notes/v1.6.1.draft.md)
  now mirrors the same boundary note and separates the CI-only infrastructure
  item from the user-visible fix.

## Boundary Conclusion

Local git evidence shows `v1.6.1` is still tagged at
`f2a55d4baea9d27bfac2ea40fd835c0f3e237048` with subject
`chore(release): prepare v1.6.1`.

The only product-impacting commit in the audited release-prep window is
`f181c6d4af6d6b792e53b17c8d5426cb2c9d805f`:
`fix: fetch opus planned issues after creation`.

Because the issue-required classifier module is absent in this checkout, the
boundary was confirmed with local git evidence plus the existing
`scripts/dev/real_commit_stats.py` release-prep classification logic.

