# Issue 83 Test Evidence

Plan ID: `95b8871fa762c209`

All commands were run locally in
`/Users/macworkers/Projects/attestplane-lane-p0`.

## Focused Boundary Validation

### Commit subjects for `v1.5.0..v1.5.7`

Command:

```bash
git log --no-merges --pretty=tformat:%s v1.5.0..v1.5.7
```

Result: exit 0.

Summary:

- 23 non-merge subjects total
- 10 release-prep subjects
- 13 real-work subjects

Real-work subjects:

```text
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

### Diff stat for `v1.5.0..v1.5.7`

Command:

```bash
git diff --stat v1.5.0..v1.5.7
```

Result: exit 0.

Short stat:

```text
48 files changed, 2720 insertions(+), 59 deletions(-)
```

### Diff check for `v1.5.0..v1.5.7`

Command:

```bash
git diff --check v1.5.0..v1.5.7
```

Result: exit 0. Output was empty.

## Issue-Required Root-To-HEAD Validation

### Commit subjects from root to `HEAD`

Command:

```bash
git log --no-merges --pretty=tformat:%s $(git rev-list --max-parents=0 HEAD)..HEAD
```

Result: exit 0.

Summary:

- 573 non-merge subjects
- The output is much broader than the `v1.5.0..v1.5.7` decision boundary

### Diff stat from root to `HEAD`

Command:

```bash
git diff --stat $(git rev-list --max-parents=0 HEAD)..HEAD
```

Result: exit 0.

Short stat:

```text
1569 files changed, 152680 insertions(+), 229 deletions(-)
```

### Diff check from root to `HEAD`

Command:

```bash
git diff --check $(git rev-list --max-parents=0 HEAD)..HEAD
```

Result: exit 2.

Output excerpt:

```text
CONTRIBUTING_zh.md:89: trailing whitespace.
CONTRIBUTING_zh.md:137: trailing whitespace.
CONTRIBUTING_zh.md:138: trailing whitespace.
docs/validation/local_codex_runner/issue-89/codex_review_report.md:5: trailing whitespace.
release/artifacts/v0.8.0-beta.0/artifact-manifest.json:59: new blank line at EOF.
release/artifacts/v0.8.0-beta.0/checksums.sha256:4: new blank line at EOF.
scripts/__init__.py:2: new blank line at EOF.
scripts/local_codex_runner/__init__.py:2: new blank line at EOF.
scripts/local_codex_runner/launchd/com.attestplane.local-codex-runner.plist.example:22: new blank line at EOF.
scripts/local_codex_runner/prompt_builder.py:77: new blank line at EOF.
scripts/local_codex_runner/run_once.sh:15: new blank line at EOF.
scripts/local_codex_runner/state_store.py:23: new blank line at EOF.
tests/local_codex_runner/conftest.py:10: new blank line at EOF.
tests/local_codex_runner/test_prompt_builder.py:26: new blank line at EOF.
```

These findings are historical and outside the `v1.5.0..v1.5.7` decision
boundary. They were not edited as part of this issue.

## Supplemental Sanity Check

Command:

```bash
python scripts/dev/real_commit_stats.py --window "7 days ago"
```

Result: exit 0.

Summary:

- total commits: 568
- real commits: 380
- release-prep: 185
- merge: 3

This helper was used only as a velocity sanity check. The publish decision
still comes from the tag-to-tag boundary above.
