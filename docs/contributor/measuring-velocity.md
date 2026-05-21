<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Measuring development velocity (filtering autorelease noise)

A naive `git log --since="7 days ago" | grep -c '^commit '` against this
repository overstates the actual cadence of development work. The cause is
the autodev-train: every autorelease cycle pushes a
`chore(release): prepare vX.Y.Z` commit. In a busy week the train can account
for a large fraction of the total commit count, which makes the raw number
useless for "is the project actually moving?" reading.

The repository ships a small read-only utility,
[`scripts/dev/real_commit_stats.py`](../../scripts/dev/real_commit_stats.py),
that filters the train signature out and reports "real" velocity instead.

## What gets filtered

The script classifies each commit's first-line subject by Conventional
Commits type and labels train-generated commits as `release-prep`:

| Class          | Matches                                              | Counts as "real"? |
| -------------- | ---------------------------------------------------- | ----------------- |
| `release-prep` | exactly `chore(release): prepare vX.Y.Z[-pre]`       | no                |
| `merge`        | starts with `Merge `                                 | no                |
| `feat`, `fix`, `docs`, `test`, `ci`, `chore`, `refactor`, `revert` | their Conventional Commits prefix | yes |
| `other`        | anything not matching the above                      | yes               |

A hand-authored `chore(release): note ...` is NOT misclassified as
auto-noise — the `release-prep` regex is anchored to the exact subject the
train produces.

## Invocation

Pure stdlib, Python 3.10+, no install step:

```bash
python3 scripts/dev/real_commit_stats.py --window "7 days ago"
```

Other useful invocations:

```bash
python3 scripts/dev/real_commit_stats.py --window "30 days ago" --format json
python3 scripts/dev/real_commit_stats.py --window "7 days ago" \
    --write reports/real-commit-stats.json
```

## Expected output

Running `--window "7 days ago"` against `main` at the time this document was
written produced the following (numbers will drift; the shape is stable):

```
real_commit_stats — window: 7 days ago
────────────────────────────────────────
total commits:    445
real commits:     295  (66%)
release-prep:     148
merge:              2
────────────────────────────────────────
By class (real only, descending):
  fix        99
  feat       61
  docs       56
  chore      49
  ci         24
  test        3
  other       3
────────────────────────────────────────
By day (real commits / total):
  2026-05-21:   46 / 107  (43%)
  2026-05-20:   57 / 131  (44%)
  2026-05-19:   54 /  68  (79%)
  2026-05-18:   48 /  49  (98%)
  2026-05-17:   90 /  90  (100%)
────────────────────────────────────────
Recent 10 real commits:
  2026-05-21T11:43 5a7c13a ci: ignore unstable contributor covenant translations link
  ...
```

Read the third block ("By day") as the most informative one: the
"real / total" ratio tells you how much of a given day's activity was actual
development versus train churn.

## Weekly artifact

The [`real-commit-report` workflow](../../.github/workflows/real-commit-report.yml)
runs every Monday at 07:37 UTC and uploads the 30-day JSON report as a
workflow artifact named `real-commit-stats-week` with 90-day retention.
Maintainers download it from the Actions tab — there is no commit, no tag
movement, and no gating attached to this job. It is read-only telemetry.

The script is also safe to run locally at any time; it does not mutate the
working tree or hit the network.
