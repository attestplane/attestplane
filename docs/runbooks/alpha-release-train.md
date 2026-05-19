# Alpha Release Train Runbook

The alpha release train packages the manual Attestplane alpha release sequence
into a finite, deterministic workflow.

It is not an autonomous product loop. It only releases prepared alpha
candidates whose scope, versions, release notes, artifacts, manifest, and
checksums already exist.

## Why Finite

An unbounded release loop would be unsafe for PyPI, npm, and GitHub Releases.
It could publish empty or duplicate alphas, move public trust surfaces without
review, and blur alpha/no-go claims. The supported loop is therefore:

1. Ask Opus for advisory next-alpha issue planning.
2. Review the advisory plan and create or curate issues manually.
3. Implement and validate exactly one alpha candidate.
4. Put the prepared candidate in `release/alpha-train/queue.json`.
5. Run the train with `--max-count 1`.
6. Verify GitHub Release, PyPI, npm, and issue status.
7. Prepare the next candidate only after the previous one is complete.

## Version Cadence

The default train cadence is ten patch alphas per milestone alpha band:

```text
v0.0.1-alpha ... v0.0.10-alpha -> v0.1.0-alpha
v0.1.1-alpha ... v0.1.10-alpha -> v0.2.0-alpha
v0.2.1-alpha ... v0.2.10-alpha -> v0.3.0-alpha
```

The registry equivalents are:

```text
Git tag v0.1.0-alpha -> PyPI 0.1.0a0 -> npm 0.1.0-alpha
```

These are SemVer segments, not decimal notation. After `v0.1.10-alpha`, the
next default release is `v0.2.0-alpha`, not `v0.1.11-alpha`.

Every milestone alpha with patch `0` triggers an Opus version-number decision
advisory. The advisory is written as
`release/alpha-train/proposals/version-evaluation-*.md` with
`SCOPE: VERSION_NUMBER_EVALUATION_ONLY`. Opus may choose the milestone version
by emitting:

```text
SELECTED_VERSION: v0.2.0-alpha
```

The deterministic train then validates the selected version. It must be an
alpha SemVer tag, greater than the latest release note, and still in major
version `0`. The advisory is not authorization to publish, tag, merge, create
a release, or change npm dist-tags. If the advisory omits `SELECTED_VERSION`,
the train falls back to the deterministic release number and records the
limitation; invalid selected versions still fail closed.

## Advisory Planning First

```bash
python scripts/release/alpha_release_train.py --plan-next-alpha --execute
```

This first step calls `ask_opus.sh architect` and writes an advisory issue plan
under `release/alpha-train/proposals/`. The file is marked:

```text
STATUS: ADVISORY
AUTHORITY: NOT_AUTHORIZED_FOR_PUBLISH
SCOPE: ISSUE_PLANNING_ONLY
```

The plan is not a queue entry. It cannot authorize publish, tag, release,
merge, issue closure, or npm `latest` changes. The runner rejects advisory
files if they are accidentally used as release notes, manifest, or checksum
inputs.

## Command

```bash
python scripts/release/alpha_release_train.py \
  --queue release/alpha-train/queue.json \
  --execute \
  --max-count 1
```

The connected advisory-to-release pipeline command is:

```bash
python scripts/release/alpha_release_train.py --pipeline --execute --max-count 1
```

It always runs Opus advisory issue planning first, writes a JSON stage report
under `release/alpha-train/reports/`, then consumes at most one prepared queue
candidate. An empty queue is a successful no-op after planning, not a release.

For a local process that runs until a human stops it:

```bash
python scripts/release/alpha_release_train.py \
  --pipeline \
  --continuous \
  --execute \
  --max-count 1
```

Continuous mode is still queue-gated. It does not invent release candidates.
It periodically writes advisory issue plans, watches `queue.json`, processes
only prepared unprocessed candidates, writes local ignored state under
`release/alpha-train/reports/`, and sleeps when no candidate is ready. A failed
gate or registry verification stops the process.

For a higher-automation local loop that promotes only already prepared local
artifacts:

```bash
python scripts/release/alpha_release_train.py \
  --pipeline \
  --continuous \
  --auto-promote-prepared \
  --execute \
  --max-count 1
```

`--auto-promote-prepared` scans release notes and artifact directories, rejects
incomplete candidates, skips already tagged releases, and appends only
deterministic prepared candidates to `queue.json`. Opus advisory output remains
issue-planning material and is never promoted into a queue candidate. Create
`release/alpha-train/STOP` to request a clean stop before the next cycle. The
default execution cap is one alpha per UTC day; `--max-releases-per-day 0`
means unlimited daily cadence and should only be used for an explicitly
accepted release window.

If the train should make progress when no candidate exists, add the local draft
prepare stage:

```bash
python scripts/release/alpha_release_train.py \
  --pipeline \
  --continuous \
  --auto-promote-prepared \
  --auto-prepare-next-alpha \
  --execute \
  --max-count 1
```

This stage writes `release/alpha-train/prepared/<release>-<commit>/` with a
draft manifest, draft notes, checksums, and a `READY` marker that explicitly
says the bundle is not release-ready. It does not modify package versions,
does not build publishable artifacts, does not commit, does not tag, does not
dispatch workflows, and does not publish. The normal queue remains the only
release input.

For a fully automated local release-prep loop:

```bash
python scripts/release/alpha_release_train.py \
  --pipeline \
  --continuous \
  --auto-promote-prepared \
  --auto-finalize-next-alpha \
  --execute \
  --max-count 1 \
  --max-releases-per-day 0
```

This mode turns the next alpha into a release-ready candidate before invoking
the existing train: it bumps local package versions, writes release notes,
builds Python/npm artifacts, writes manifest/checksum/upload-plan files, runs
the release-prep gate, commits the release-prep files, and then releases via
the same candidate execution stage. It remains fail-closed and still does not
force-push, rewrite tags, or treat Opus advisory output as authority. npm
`latest` movement is restricted to the deterministic post-publish
synchronization step for the same alpha version.

The preferred operational entrypoint is the tmux wrapper:

```bash
scripts/release/start_alpha_train_full_auto.sh
```

That wrapper starts the `attestplane-alpha-train` session using:

```bash
python scripts/release/alpha_release_train.py --full-auto-alpha
```

`--full-auto-alpha` expands to the same explicit full-auto local mode:
`--pipeline --continuous --auto-promote-prepared --auto-finalize-next-alpha
--execute --max-count 1 --max-releases-per-day 0 --max-prepares-per-day 0`.
It exists to avoid accidentally launching the older queue-only watcher, which
can stay healthy while making no release progress when the queue is empty.
The wrapper refuses to start if the tmux session is already running or if
`release/alpha-train/STOP` exists.

The runner performs:

- optional Opus advisory issue planning when `--plan-next-alpha` is passed,
- optional local draft candidate bundle creation when
  `--auto-prepare-next-alpha` is passed,
- optional release-ready candidate preparation when
  `--auto-finalize-next-alpha` is passed,
- clean working tree check,
- Python full tests, ruff, mypy,
- TypeScript tests, typecheck, lint,
- public API, schema hash, fixture hash, ProofBundle verifier gates,
- release artifact prep gate,
- gitleaks,
- `git -c http.version=HTTP/1.1 push origin main`,
- annotated release tag push,
- GitHub prerelease creation with artifacts,
- PyPI trusted publishing workflow,
- npm alpha-tag publishing workflow,
- registry verification.

After a candidate reaches `registry_verified`, the runner writes an
integration evidence packet through
`scripts/release/alpha_train_integrations.py`. That packet reads GitHub,
registry, Linear, Sentry, CodeRabbit availability, local Codex Security
surface facts, and the SQLite `git_push_tasks` queue, then generates JSON plus
Markdown reports under `release/alpha-train/reports/`. Those reports are for
observation and human review only; they do not authorize publish, tag,
release, workflow dispatch, npm dist-tag movement, or git push scheduling.

See [Alpha Release Integration Evidence](alpha-release-integrations.md).

## Stop Conditions

The train stops on:

- missing candidate files,
- dirty working tree,
- failed local gate,
- failed claim scan,
- gitleaks finding,
- existing conflicting tag or GitHub Release,
- workflow failure,
- PyPI/npm registry verification failure,
- npm `latest` not pointing at the alpha candidate after the post-publish
  synchronization step.

Continuous mode still stops on candidate validation, local-gate, release,
workflow, or registry failures. By contrast, `git push` is queue-backed and
transport-normalized to `http.version=HTTP/1.1`:
transient push failures are recorded in `git_push_tasks` and do not block later
queued candidates from running. The queue is retried opportunistically on later
cycles. This avoids the GitHub 443/H2 proxy stall seen on this workstation.

When a candidate's tag push is still queued, GitHub Release creation waits for
that prerequisite rather than failing the whole train. If the dependency is not
yet met, the candidate remains pending and later candidates may continue.

Continuous mode also exits cleanly if `release/alpha-train/STOP` exists before
the next cycle. Remove the file to resume later.

## Human Ownership

The founder/maintainer remains the release owner. The release train is only a
deterministic executor for a prepared alpha candidate. It does not approve its
own scope, downgrade findings, invent release notes, or close release blockers.

Operational owner for the current single-maintainer phase:

- GitHub owner: `@merchloubna70-dot`
- Registry owner: the authenticated PyPI/npm publisher for the project
- Manual review point: periodic inspection of proposals, queue state, train
  reports, registry state, and any newly auto-promoted prepared candidates

## Rollback and Recovery

Published registry artifacts are immutable. Do not delete or rewrite published
alpha artifacts as a normal rollback path.

If a run fails before publication:

1. Leave the tag unreleased if it was not pushed.
2. Delete only local, unpublished build artifacts if needed.
3. Fix the candidate and rerun from a clean working tree.

If a run fails after tag or GitHub Release creation but before registry publish:

1. Do not retag.
2. Mark the GitHub Release notes with the failed platform state.
3. Prepare a new alpha candidate if code changes are required.

If `git push` is temporarily unavailable, the train records the queued push
task and continues with later candidates. That failure does not imply a
release-state rollback; it is a transport limitation, not a release
authorization change.

If a registry publish succeeds and a later platform fails:

1. Do not overwrite the published package.
2. Record the partial release in the issue/release notes.
3. Publish a new alpha with a higher version for fixes.

## Code Ownership

`.github/CODEOWNERS` currently applies a catch-all owner rule to all files,
including:

- `release/alpha-train/**`
- `scripts/release/**`
- `.github/workflows/alpha-release-train.yml`

Branch protection should require that owner review once the project has more
than one maintainer. The current single-maintainer phase avoids self-locking.

## Explicit Non-Goals

- No autonomous code generation.
- No release scope invention.
- No advisory-authorized or out-of-band npm `latest` promotion.
- No tag rewriting.
- No force push.
- No production/compliance/certification claim.
- No signed provenance claim unless signature artifacts are actually present.
