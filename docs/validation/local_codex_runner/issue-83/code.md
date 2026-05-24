# Issue 83 Code Evidence

Plan ID: `95b8871fa762c209`

## Scope implemented

- Confirmed the local `v1.5.0..v1.5.7` release boundary contains real human
  work and therefore does not satisfy the stable-train idle-cadence skip
  condition.
- Confirmed the release note draft already reflects the real boundary by
  listing the non-release-prep commits that should ship with `v1.5.7`.
- Kept the release train, release notes, release-cd policy, tags, registry
  state, and package metadata unchanged.

## Boundary Decision

The focused boundary is:

```bash
git log --no-merges --pretty=tformat:%s v1.5.0..v1.5.7
git diff --stat v1.5.0..v1.5.7
git diff --check v1.5.0..v1.5.7
```

The local commit subjects in that range are not all release-prep commits.
The range contains 23 non-merge subjects total, 10 release-prep subjects, and
13 real-work subjects.

Real-work subjects in the range:

- `ci: ignore transient scorecard link failures`
- `fix: reload planned issues from github`
- `fix: include open issues in release planning`
- `fix: fan out daily architecture plans`
- `fix: generate daily architecture audit plans`
- `fix: make release planning scripts importable in CI`
- `fix: satisfy markdownlint and plan parser test`
- `Add structured autodev train events`
- `Unify release planning schema and fanout`
- `Unify plan issuance across release tiers`
- `ci: auto-accept major architecture plans`
- `ci: convert accepted plans into task issues`
- `fix(release): skip idle cadence before remote probe`

The local stable-train rule in `scripts/release/stable_auto_train.py` returns
`True` when at least one subject in `tag..HEAD` does not match the release-prep
regex, and `False` only when the range is empty or every subject matches the
release-prep regex. This boundary therefore should publish rather than skip.

## Release-note Alignment

`docs/release-notes/v1.5.7.draft.md` already names the real work in the
boundary:

- `ci: ignore transient scorecard link failures`
- `fix: reload planned issues from github`
- `fix: include open issues in release planning`

That draft supports the publish decision without any release artifact edits.

## Safety Boundary

This issue did not change release tags, package versions, registry state, or
release automation. It only records the real-change boundary and the publish
decision.
