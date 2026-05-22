# Issue 96 Validation Evidence

Plan ID: `9c2ebb04228d4d8e`

All commands were run locally in
`/Users/macworkers/Projects/attestplane-lane-p0`.

## Issue-Required Commands

### Root-to-HEAD commit subjects

Command:

```bash
git log --no-merges --pretty=tformat:%s $(git rev-list --max-parents=0 HEAD)..HEAD
```

Result: exit 0. The command returned 564 non-merge commit subjects. The
output includes the `v1.5.0..v1.5.10` subjects but also includes the
entire repository history after the root commit, so it is broader than
the issue's named release boundary.

Relevant excerpt around the focused boundary:

```text
chore(release): prepare v1.5.10
test: cover opus planning levels
chore(release): prepare v1.5.9
fix: consult opus for stable planning
chore(release): prepare v1.5.8
fix: make stable train git proxy strategy explicit
chore(release): prepare v1.5.7
ci: ignore transient scorecard link failures
chore(release): prepare v1.5.7
fix: reload planned issues from github
fix: include open issues in release planning
chore(release): prepare v1.5.6
fix: fan out daily architecture plans
fix: generate daily architecture audit plans
chore(release): prepare v1.5.5
fix: make release planning scripts importable in CI
chore(release): prepare v1.5.5
fix: satisfy markdownlint and plan parser test
chore(release): prepare v1.5.5
Add structured autodev train events
Unify release planning schema and fanout
chore(release): prepare v1.5.4
Unify plan issuance across release tiers
chore(release): prepare v1.5.3
ci: auto-accept major architecture plans
chore(release): prepare v1.5.2
ci: convert accepted plans into task issues
chore(release): prepare v1.5.1
fix(release): skip idle cadence before remote probe
chore(release): prepare v1.5.0
```

### Root-to-HEAD diff stat

Command:

```bash
git diff --stat $(git rev-list --max-parents=0 HEAD)..HEAD
```

Result: exit 0. Shortstat:

```text
1489 files changed, 148090 insertions(+), 229 deletions(-)
```

This confirms root-to-HEAD is a repository-lifetime range and is not the
same scope as `v1.5.0..v1.5.10`.

### Root-to-HEAD diff check

Command:

```bash
git diff --check $(git rev-list --max-parents=0 HEAD)..HEAD
```

Result: exit 2. Output:

```text
CONTRIBUTING_zh.md:89: trailing whitespace.
+常用 type：`feat` / `fix` / `test` / `docs` / `refactor` / `chore` / `perf`。[two trailing spaces in command output]
CONTRIBUTING_zh.md:137: trailing whitespace.
+**安全漏洞**：**不要在公开 Issue 中披露。**[two trailing spaces in command output]
CONTRIBUTING_zh.md:138: trailing whitespace.
+请遵循 [`SECURITY.md`](SECURITY.md) 中的负责任披露流程，通过私有渠道报告。[two trailing spaces in command output]
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

These findings are outside the focused `v1.5.0..v1.5.10` release
boundary. They were not edited as part of Issue 96.

## Focused Release Boundary Commands

### v1.5.0..v1.5.10 commit subjects

Command:

```bash
git log --no-merges --pretty=tformat:%s v1.5.0..v1.5.10
```

Result: exit 0. Output:

```text
chore(release): prepare v1.5.10
test: cover opus planning levels
chore(release): prepare v1.5.9
fix: consult opus for stable planning
chore(release): prepare v1.5.8
fix: make stable train git proxy strategy explicit
chore(release): prepare v1.5.7
ci: ignore transient scorecard link failures
chore(release): prepare v1.5.7
fix: reload planned issues from github
fix: include open issues in release planning
chore(release): prepare v1.5.6
fix: fan out daily architecture plans
fix: generate daily architecture audit plans
chore(release): prepare v1.5.5
fix: make release planning scripts importable in CI
chore(release): prepare v1.5.5
fix: satisfy markdownlint and plan parser test
chore(release): prepare v1.5.5
Add structured autodev train events
Unify release planning schema and fanout
chore(release): prepare v1.5.4
Unify plan issuance across release tiers
chore(release): prepare v1.5.3
ci: auto-accept major architecture plans
chore(release): prepare v1.5.2
ci: convert accepted plans into task issues
chore(release): prepare v1.5.1
fix(release): skip idle cadence before remote probe
```

Classification: 29 non-merge subjects total; 16 subjects are not
release-prep subjects and count as real work under the cadence limiter.

### v1.5.0..v1.5.10 diff stat

Command:

```bash
git diff --stat v1.5.0..v1.5.10
```

Result: exit 0. Shortstat:

```text
60 files changed, 3606 insertions(+), 87 deletions(-)
```

The full stat includes workflow, runbook, release-note, release artifact,
script, SDK version, and test changes.

### v1.5.0..v1.5.10 diff check

Command:

```bash
git diff --check v1.5.0..v1.5.10
```

Result: exit 0. Output was empty.

## Policy Cross-Check Commands

Command:

```bash
rg -n "real work|idle cadence|stable: no real work|FORCE_CADENCE|release-prep" \
  docs/runbooks/autodev-train.md scripts/release/stable_auto_train.py
```

Result: exit 0. Relevant local matches:

```text
docs/runbooks/autodev-train.md:136:subject line against the train's own release-prep regex:
docs/runbooks/autodev-train.md:147:autodev-train stable: no real work since vX.Y.Z; skipping cadence cycle
docs/runbooks/autodev-train.md:161:Set `ATTESTPLANE_AUTODEV_TRAIN_FORCE_CADENCE=1` in the train's
scripts/release/stable_auto_train.py:126:# stable tag are the train's own release-prep commits. The train was
scripts/release/stable_auto_train.py:133:# range are release-prep commits. Documented in
scripts/release/stable_auto_train.py:135:FORCE_CADENCE_ENV = "ATTESTPLANE_AUTODEV_TRAIN_FORCE_CADENCE"
scripts/release/stable_auto_train.py:774:    """Return True if the range ``tag..HEAD`` contains any non-release-prep commit.
scripts/release/stable_auto_train.py:780:    so a PR-merge into main does not by itself count as real work.
scripts/release/stable_auto_train.py:783:      - at least one commit subject does NOT match the release-prep regex; or
scripts/release/stable_auto_train.py:788:      - every subject in the range matches the release-prep regex; or
scripts/release/stable_auto_train.py:1737:            f"autodev-train stable: no real work since {previous.tag}; skipping cadence cycle",
```

Command:

```bash
rg -n "v1\\.5\\.10|cover opus planning levels" docs/release-notes/v1.5.10.draft.md
```

Result: exit 0. Output:

```text
1:# v1.5.10
3:`v1.5.10` is an automated suffix-free stable package cut from autodev-train.
7:- test: cover opus planning levels
34:- `release/artifacts/v1.5.10/checksums.sha256`
35:- `release/artifacts/v1.5.10/artifact-manifest.json`
```

## Validation Conclusion

Acceptance criterion 1 is satisfied: `v1.5.0..v1.5.10` contains real
human work.

Acceptance criterion 2 is satisfied: the release train should publish
rather than skip, because the skip condition only applies to empty ranges
or ranges containing only release-prep subjects.

Acceptance criterion 3 is satisfied by the local follow-up draft in
`docs/validation/local_codex_runner/issue-96/followup_idle_cadence.md`.

## Default Gate Rerun

The initial local runner gate failed because root `pytest -q` collected the
nested Python SDK test suite under `sdk/python/tests` without the SDK
`dev`/`anchor` extras installed. The root gate is repo-level validation, while
the Python SDK package keeps its own pytest configuration and dependency
declarations in `sdk/python/pyproject.toml`.

The repository root now has an explicit pytest collection boundary:

```ini
[pytest]
testpaths = tests
addopts = -ra --strict-markers --strict-config
xfail_strict = true
```

Rerun results:

```text
python -m compileall scripts: exit 0
pytest -q: exit 0
314 passed in 43.70s
```
