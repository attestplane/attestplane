# Issue 104 Validation Evidence

## Release Boundary

Command:

```sh
git log --no-merges --pretty=tformat:'%h %s' v1.5.0..v1.6.0
```

Output:

```text
f1b6241 chore(release): prepare v1.6.0
b000b56 ci: use local python on opus runner
0cf4660 ci: run architecture planning on opus runner
bfeb6ae chore(release): prepare v1.5.10
a029c06 test: cover opus planning levels
add1854 chore(release): prepare v1.5.9
fd35d10 fix: consult opus for stable planning
982edab chore(release): prepare v1.5.8
8415001 fix: make stable train git proxy strategy explicit
06f8104 chore(release): prepare v1.5.7
6b3e59a ci: ignore transient scorecard link failures
f16c1dd chore(release): prepare v1.5.7
ccc1e42 fix: reload planned issues from github
31aa211 fix: include open issues in release planning
43c12a4 chore(release): prepare v1.5.6
dceefbd fix: fan out daily architecture plans
4c43d96 fix: generate daily architecture audit plans
2627258 chore(release): prepare v1.5.5
05c9cb2 fix: make release planning scripts importable in CI
e47e186 chore(release): prepare v1.5.5
42119e4 fix: satisfy markdownlint and plan parser test
5dbc2c2 chore(release): prepare v1.5.5
ba569a9 Add structured autodev train events
5b5ec86 Unify release planning schema and fanout
c7f0d06 chore(release): prepare v1.5.4
8167261 Unify plan issuance across release tiers
991c69a chore(release): prepare v1.5.3
3af24b1 ci: auto-accept major architecture plans
ec7666c chore(release): prepare v1.5.2
5c238d3 ci: convert accepted plans into task issues
3248972 chore(release): prepare v1.5.1
df1f062 fix(release): skip idle cadence before remote probe
```

Result: the release summary groups the 18 non-release-prep commits into the
three issue-required user-visible buckets.

## Required Validation

Command:

```sh
markdownlint docs/releases/v1.6.0.md CHANGELOG.md
```

Output:

```text
zsh:1: command not found: markdownlint
```

Result: blocked by this local runner environment. `command -v markdownlint`
returned exit `1`. The repository has `.markdownlint.jsonc`, but this checkout
does not have a `markdownlint` binary or local `node_modules/.bin` install.

Command:

```sh
python -m scripts.release.docs_lint --milestone v1.6.0
```

Output:

```text
/opt/homebrew/opt/python@3.14/bin/python3.14: No module named scripts.release.docs_lint
```

Result: blocked by missing local module. `scripts/release/docs_lint.py` is not
present in this checkout.

## Focused Local Checks

Command:

```sh
git diff --check -- docs/releases/v1.6.0.md docs/release-notes/v1.6.0.draft.md CHANGELOG.md
```

Output: no output.

Result: pass for tracked modified files. The new untracked
`docs/releases/v1.6.0.md` was also checked with:

```sh
git diff --check --no-index -- /dev/null docs/releases/v1.6.0.md
```

Output: no output. Exit code was `1` because `--no-index` reports a file
difference against `/dev/null`; no whitespace errors were emitted.

Command:

```sh
rg -n "v1\\.6\\.0|Issue #100|Issue #104|breaking|API surface|ISSUE 1|ISSUE 2" \
  docs/releases/v1.6.0.md docs/release-notes/v1.6.0.draft.md CHANGELOG.md
```

Result: pass. Matches confirm the final summary, aligned draft, and changelog
include the v1.6.0 heading, Issue #100, Issue #104, ISSUE 1, ISSUE 2, no
breaking changes, and no API surface change language.

Command:

```sh
rg -n "production-ready|compliance certification|SLSA L3|certified provenance" \
  docs/releases/v1.6.0.md docs/release-notes/v1.6.0.draft.md CHANGELOG.md
```

Result: pass. Matches are limited to the preserved claim-safety exclusions in
the v1.6.0 release docs and pre-existing changelog language.

Command:

```sh
git diff --stat -- docs/releases/v1.6.0.md docs/release-notes/v1.6.0.draft.md CHANGELOG.md
```

Output:

```text
 CHANGELOG.md                       | 25 ++++++++++++++++
 docs/release-notes/v1.6.0.draft.md | 59 ++++++++++++++++++++++++++++++++++----
 2 files changed, 79 insertions(+), 5 deletions(-)
```

Note: `git diff --stat` does not show the new untracked
`docs/releases/v1.6.0.md` until staged. `git status --short` reports it as
`?? docs/releases/v1.6.0.md`.
