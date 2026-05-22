# Issue 96 Code Evidence

Plan ID: `9c2ebb04228d4d8e`

## Scope

This evidence confirms the real-change boundary for `v1.5.0..v1.5.10`
using only local repository state and local command output. No release
automation, package metadata, tags, registry state, release gates, or
release-CD policy were changed.

## Boundary Under Review

The release boundary for the issue is:

```bash
git log --no-merges --pretty=tformat:%s v1.5.0..v1.5.10
git diff --stat v1.5.0..v1.5.10
git diff --check v1.5.0..v1.5.10
```

The focused range contains 29 non-merge commit subjects. Sixteen subjects
do not match the stable train release-prep regex
`^chore\(release\): prepare v\d+\.\d+\.\d+(-\S+)?$`:

```text
test: cover opus planning levels
fix: consult opus for stable planning
fix: make stable train git proxy strategy explicit
ci: ignore transient scorecard link failures
fix: reload planned issues from github
fix: include open issues in release planning
fix: fan out daily architecture plans
fix: generate daily architecture audit plans
fix: make release planning scripts importable in CI
fix: satisfy markdownlint and plan parser test
Add structured autodev train events
Unify release planning schema and fanout
Unify plan issuance across release tiers
ci: auto-accept major architecture plans
ci: convert accepted plans into task issues
fix(release): skip idle cadence before remote probe
```

The focused diff stat is:

```text
60 files changed, 3606 insertions(+), 87 deletions(-)
```

`git diff --check v1.5.0..v1.5.10` exits cleanly.

## Policy Cross-Check

`docs/runbooks/autodev-train.md` documents the cadence limiter. It skips
only when every non-merge subject since the latest published stable tag
matches the release-prep regex, or when the range is empty. It proceeds
when at least one `feat`, `fix`, `docs`, `test`, `ci`, or non-release
`chore` subject is present.

`scripts/release/stable_auto_train.py` implements the same rule in
`commits_since_tag_have_real_work(tag)`: the function returns `True`
when at least one subject in `tag..HEAD` does not match
`RELEASE_PREP_SUBJECT_REGEX`, and returns `False` when the range is empty
or every subject is release-prep.

The local evidence for `v1.5.0..v1.5.10` therefore satisfies the train's
real-work condition. The range includes test, fix, ci, schema, planning,
runbook, release-note, artifact, and queue behavior changes, not just
`chore(release): prepare ...` commits.

## Publish Decision

The v1.5.10 stable train should publish rather than skip. The actual
release boundary contains real human work under both the runbook policy
and the local implementation rule.

This decision does not authorize moving tags, creating tags, dispatching
release-CD, publishing packages, pushing to registries, or weakening any
release gate. It only records that the skip condition is not met for the
`v1.5.0..v1.5.10` range.

## Root-To-HEAD Scope Note

The issue also lists root-to-HEAD validation commands. Those commands
inspect the whole repository history from the root commit through current
`HEAD`, not the v1.5.10 release boundary. Local root-to-HEAD
`git diff --check` currently reports historical whitespace and EOF
findings outside the focused boundary. This task records that result
without editing unrelated historical files to manufacture a pass.
