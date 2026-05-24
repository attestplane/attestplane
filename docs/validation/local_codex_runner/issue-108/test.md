# Issue 108 Local Validation Transcript

Plan ID: `52b4e25efe3a15b7`

## Required Commands

```bash
git log --oneline v1.6.0..v1.6.1
```

```text
f2a55d4 chore(release): prepare v1.6.1
28127b7 ci: proxy architecture audit runner network
```

```bash
git show --no-patch --format='%H%n%s%n%D' v1.6.1
```

```text
tag v1.6.1
Tagger: merchloubna70-dot <258170091+merchloubna70-dot@users.noreply.github.com>

v1.6.1
f2a55d4baea9d27bfac2ea40fd835c0f3e237048
chore(release): prepare v1.6.1
tag: v1.6.1
```

```bash
git show --name-status --oneline f181c6d
```

```text
f181c6d fix: fetch opus planned issues after creation
M  scripts/release/plan_to_issues.py
M  sdk/python/tests/test_plan_to_issues.py
```

```bash
git show --name-status --oneline f2a55d4
```

```text
f2a55d4 chore(release): prepare v1.6.1
A  docs/release-notes/v1.6.1.draft.md
A  release/artifacts/v1.6.1/artifact-manifest.json
A  release/artifacts/v1.6.1/checksums.sha256
A  release/artifacts/v1.6.1/upload-plan.md
M  sdk/python/pyproject.toml
M  sdk/python/src/attestplane/__init__.py
M  sdk/python/tests/test_import_surface.py
M  sdk/python/uv.lock
M  sdk/typescript/package-lock.json
M  sdk/typescript/package.json
M  sdk/typescript/src/index_version.ts
```

```bash
python -m scripts.release.classify_commits --anchor v1.5.0 --head v1.6.1
```

```text
/opt/homebrew/opt/python@3.14/bin/python3.14: No module named scripts.release.classify_commits
```

```bash
UV_CACHE_DIR=/private/tmp/uv-cache uv run pytest tests/release -k boundary
```

```text
ERROR: file or directory not found: tests/release

============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.0.3, pluggy-1.6.0
rootdir: /Users/macworkers/Projects/attestplane-lane-p0
configfile: pytest.ini
plugins: cov-7.1.0, typeguard-4.5.1, asyncio-1.3.0, httpx-0.36.2, langsmith-0.7.36, anyio-4.13.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 0 items

============================ no tests ran in 0.00s =============================
```

## Substitute Boundary Evidence

```bash
python - <<'PY'
import subprocess
from pathlib import Path
import sys
sys.path.insert(0, str(Path('.').resolve()))
from scripts.dev.real_commit_stats import classify
proc = subprocess.run(['git', 'log', '--no-merges', '--pretty=tformat:%H|%s', 'v1.5.0..v1.6.1'], check=True, capture_output=True, text=True)
rows = [line.split('|', 1) for line in proc.stdout.splitlines() if line]
print('window: v1.5.0..v1.6.1')
print(f'total commits: {len(rows)}')
for sha, subject in rows:
    print(f'{sha[:7]} {classify(subject)} {subject}')
print('release-prep:', sum(1 for _, subject in rows if classify(subject) == 'release-prep'))
print('real:', sum(1 for _, subject in rows if classify(subject) != 'release-prep'))
PY
```

```text
window: v1.5.0..v1.6.1
total commits: 34
f2a55d4 release-prep chore(release): prepare v1.6.1
28127b7 ci ci: proxy architecture audit runner network
f1b6241 release-prep chore(release): prepare v1.6.0
b000b56 ci ci: use local python on opus runner
0cf4660 ci ci: run architecture planning on opus runner
bfeb6ae release-prep chore(release): prepare v1.5.10
a029c06 test test: cover opus planning levels
add1854 release-prep chore(release): prepare v1.5.9
fd35d10 fix fix: consult opus for stable planning
982edab release-prep chore(release): prepare v1.5.8
8415001 fix fix: make stable train git proxy strategy explicit
06f8104 release-prep chore(release): prepare v1.5.7
6b3e59a ci ci: ignore transient scorecard link failures
f16c1dd release-prep chore(release): prepare v1.5.7
ccc1e42 fix fix: reload planned issues from github
31aa211 fix fix: include open issues in release planning
43c12a4 release-prep chore(release): prepare v1.5.6
dceefbd fix fix: fan out daily architecture plans
4c43d96 fix fix: generate daily architecture audit plans
2627258 release-prep chore(release): prepare v1.5.5
05c9cb2 fix fix: make release planning scripts importable in CI
e47e186 release-prep chore(release): prepare v1.5.5
42119e4 fix fix: satisfy markdownlint and plan parser test
5dbc2c2 release-prep chore(release): prepare v1.5.5
ba569a9 other Add structured autodev train events
5b5ec86 other Unify release planning schema and fanout
c7f0d06 release-prep chore(release): prepare v1.5.4
8167261 other Unify plan issuance across release tiers
991c69a release-prep chore(release): prepare v1.5.3
3af24b1 ci ci: auto-accept major architecture plans
ec7666c release-prep chore(release): prepare v1.5.2
5c238d3 ci ci: convert accepted plans into task issues
3248972 release-prep chore(release): prepare v1.5.1
df1f062 fix fix(release): skip idle cadence before remote probe
release-prep: 15
real: 19
```

