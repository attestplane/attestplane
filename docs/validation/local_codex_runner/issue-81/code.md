# Issue 81 Code Evidence

Implemented the release-note update for v1.5.6 by editing
`docs/release-notes/v1.5.6.draft.md`.

## What Changed

- Replaced the old `Changes Since Previous Stable` section with `User-Visible Delta`.
- Added bounded wording that describes the stable package cut as the visible
  release delta.
- Linked the note to source planning issue [#78](https://github.com/attestplane/attestplane/issues/78)
  and planned-task issue [#81](https://github.com/attestplane/attestplane/issues/81).

## Scope Check

- `release/artifacts/v1.5.6/artifact-manifest.json` was not changed.
- `docs/runbooks/autodev-train.md` was not changed.
- The release note stays within the documented claim boundary and does not add
  compliance, production-readiness, registry-policy, or provenance claims.
