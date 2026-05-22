# Issue 92 Validation

Plan ID: `1c6c43895e7a304f`

## Boundary Validation

Command:

```bash
git tag --list 'v1.5.*' | sort -V
```

Exit status: `0`

Result: local tags `v1.5.0` through `v1.5.10` are present, including the target
boundary tags `v1.5.0` and `v1.5.9`.

Command:

```bash
git log --no-merges --pretty=tformat:'%h %s' v1.5.0..v1.5.9
```

Exit status: `0`

Result: 27 non-merge commit subjects were returned. The range includes
non-release-prep work such as `fix: consult opus for stable planning`,
`fix: make stable train git proxy strategy explicit`, `ci: ignore transient
scorecard link failures`, and release planning automation changes.

Command:

```bash
git diff --stat v1.5.0..v1.5.9
```

Exit status: `0`

Result: `56 files changed, 3428 insertions(+), 87 deletions(-)`.

Command:

```bash
git diff --check v1.5.0..v1.5.9
```

Exit status: `0`

Result: no output.

## Cadence Classification

Command:

```bash
python - <<'PY'
import re, subprocess
rx = re.compile(r'^chore\(release\): prepare v\d+\.\d+\.\d+(-\S+)?$')
subjects = subprocess.check_output(
    ['git', 'log', '--no-merges', '--pretty=tformat:%s', 'v1.5.0..v1.5.9'],
    text=True,
).splitlines()
release = [s for s in subjects if rx.match(s)]
real = [s for s in subjects if not rx.match(s)]
print(f'total_subjects={len(subjects)}')
print(f'release_prep_subjects={len(release)}')
print(f'non_release_prep_subjects={len(real)}')
PY
```

Exit status: `0`

Output:

```text
total_subjects=27
release_prep_subjects=12
non_release_prep_subjects=15
```

Result: the range is not idle cadence.

## Issue-Provided Commands

Command:

```bash
git log --no-merges --pretty=tformat:%s $(git rev-list --max-parents=0 HEAD)..HEAD
```

Exit status: `0`

Result: command returned 559 commit subjects. The output includes the
`v1.5.0..v1.5.9` subjects but covers the full repository history after the root
commit, so it is broader than the release decision boundary.

Command:

```bash
git diff --stat $(git rev-list --max-parents=0 HEAD)..HEAD
```

Exit status: `0`

Result: `1467 files changed, 146027 insertions(+), 229 deletions(-)`.

Command:

```bash
git diff --check $(git rev-list --max-parents=0 HEAD)..HEAD
```

Exit status: `2`

Result: failed on historical root-to-HEAD whitespace findings in files such as
`CONTRIBUTING_zh.md`, `release/artifacts/v0.8.0-beta.0/artifact-manifest.json`,
`scripts/local_codex_runner/prompt_builder.py`, and
`tests/local_codex_runner/test_prompt_builder.py`. The release-boundary command
`git diff --check v1.5.0..v1.5.9` passed, so this does not change the
`v1.5.9` publish decision.

## Script Compatibility Note

Command:

```bash
python scripts/dev/real_commit_stats.py v1.5.0..v1.5.9
```

Exit status: `2`

Result: the script rejected the rev range because it only accepts `--window`,
`--format`, and `--write`. The cadence classification was therefore performed
with the same documented release-prep regex against `git log` output.

## Local Evidence File Checks

Command:

```bash
git diff --check -- docs/validation/local_codex_runner/issue-92
```

Exit status: `0`

Result: no output. This command did not inspect untracked evidence files until
they are visible to the git index.

Command:

```bash
git add -N docs/validation/local_codex_runner/issue-92 && \
  git diff --check -- docs/validation/local_codex_runner/issue-92
```

Exit status: `128`

Result: blocked by the sandbox because the linked-worktree index lock is outside
the writable root:

```text
fatal: Unable to create '/Users/macworkers/Projects/attestplane/.git/worktrees/attestplane-local-runner/index.lock': Operation not permitted
```

Fallback command:

```bash
rg -n '[ \t]$' docs/validation/local_codex_runner/issue-92/*.md
```

Exit status: `1`

Result: no trailing whitespace found in local evidence Markdown files.

Fallback command:

```bash
for f in docs/validation/local_codex_runner/issue-92/*.md; do
  printf '%s ' "$f"
  tail -c 1 "$f" | od -An -t x1
done
```

Exit status: `0`

Result: every checked Markdown file ended with `0a`.

## Test-Fix Gate

Command:

```bash
sdk/python/.venv/bin/pytest -q sdk/python/tests/test_local_codex_runner_queue.py tests/local_codex_runner/test_models.py
```

Exit status: `0`

Output:

```text
12 passed in 0.07s
```

Command:

```bash
sdk/python/.venv/bin/python -m compileall scripts
```

Exit status: `0`

Result: scripts compiled successfully.

Command:

```bash
sdk/python/.venv/bin/pytest -q
```

Exit status: `0`

Output:

```text
1306 passed in 118.10s (0:01:58)
```
