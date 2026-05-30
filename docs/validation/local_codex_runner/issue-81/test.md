# Issue 81 Validation Evidence

## Command 1

```bash
git diff --check -- docs/release-notes/v1.5.6.draft.md release/artifacts/v1.5.6/artifact-manifest.json docs/runbooks/autodev-train.md
```

Result:

- No output.
- Exit status: `0`.

## Command 2

```bash
rg -n "v1\\.5\\.6|#78|#81|User-Visible Delta|Changes Since Previous Stable|Explicit Boundaries" \
  docs/release-notes/v1.5.6.draft.md release/artifacts/v1.5.6/artifact-manifest.json docs/runbooks/autodev-train.md
```

Result:

```text
docs/release-notes/v1.5.6.draft.md:1:# v1.5.6
docs/release-notes/v1.5.6.draft.md:3:`v1.5.6` is an automated suffix-free stable package cut from autodev-train.
docs/release-notes/v1.5.6.draft.md:6:[#78](https://github.com/attestplane/attestplane/issues/78) and planned-task
docs/release-notes/v1.5.6.draft.md:7:issue [#81](https://github.com/attestplane/attestplane/issues/81).
docs/release-notes/v1.5.6.draft.md:9:## User-Visible Delta
docs/release-notes/v1.5.6.draft.md:11:The user-visible delta in `v1.5.6` is the stable package cut itself: the
docs/release-notes/v1.5.6.draft.md:25:## Explicit Boundaries
docs/release-notes/v1.5.6.draft.md:43:- `release/artifacts/v1.5.6/checksums.sha256`
docs/release-notes/v1.5.6.draft.md:44:- `release/artifacts/v1.5.6/artifact-manifest.json`
release/artifacts/v1.5.6/artifact-manifest.json:28:  "checksums_file": "release/artifacts/v1.5.6/checksums.sha256",
release/artifacts/v1.5.6/artifact-manifest.json:42:  "release": "v1.5.6",
release/artifacts/v1.5.6/artifact-manifest.json:43:  "release_notes_file": "docs/release-notes/v1.5.6.draft.md",
release/artifacts/v1.5.6/artifact-manifest.json:49:  "upload_plan_file": "release/artifacts/v1.5.6/upload-plan.md"
```

## Scope Check

- `git diff --stat` showed one changed file: `docs/release-notes/v1.5.6.draft.md`.
- `release/artifacts/v1.5.6/artifact-manifest.json` remained unchanged and still points to the draft note.
- `docs/runbooks/autodev-train.md` remained unchanged.
