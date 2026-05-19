# Alpha Release Train

This directory defines finite alpha release-train candidates for Attestplane.
It is intentionally queue-based and bounded. The train does not invent product
scope, generate code, or publish an unprepared version.

## Contract

- Each candidate is one alpha release.
- Each candidate must already have release notes, package versions, local
  artifacts, release manifest, and checksums.
- The runner stops on the first failed gate or platform verification failure.
- After npm alpha publishing succeeds, the runner synchronizes npm `latest` to
  the same alpha version. This is an explicit installability policy, not a GA or
  production-readiness claim.
- The runner does not retag existing releases.
- The runner does not claim production readiness, compliance readiness,
  certification, SLSA level, or signed provenance unless those artifacts are
  actually present and verified.

## Version Cadence

Alpha versions are grouped into ten-patch milestone bands. After ten patch
alphas, the train rolls to the next minor milestone alpha:

```text
v0.0.1-alpha ... v0.0.10-alpha -> v0.1.0-alpha
v0.1.1-alpha ... v0.1.10-alpha -> v0.2.0-alpha
v0.2.1-alpha ... v0.2.10-alpha -> v0.3.0-alpha
```

In package registries the same release is represented as PEP 440 and npm
SemVer:

```text
Git tag v0.1.0-alpha -> PyPI 0.1.0a0 -> npm 0.1.0-alpha
```

The train treats these as SemVer segments, not decimal numbers. `0.1.10-alpha`
is the tenth patch alpha in the `0.1` band; it is not `0.110`.

When the train is about to create a milestone alpha with patch `0`, it calls
Opus for a version-number decision advisory. That advisory is written under
`release/alpha-train/proposals/version-evaluation-*.md` with
`SCOPE: VERSION_NUMBER_EVALUATION_ONLY`. Opus may select the milestone version
by emitting a line like:

```text
SELECTED_VERSION: v0.2.0-alpha
```

The local train accepts that selected version only after deterministic
validation: it must be an alpha SemVer tag, must be greater than the latest
release note, must remain in major version `0`, and must not authorize
publishing, tagging, release creation, or npm dist-tag changes. If Opus omits a
selected version or selects an invalid version, the train fails closed instead
of silently falling back.

## Queue

The first step for the next alpha cycle is advisory planning:

```bash
python scripts/release/alpha_release_train.py --plan-next-alpha --execute
```

That command calls `ask_opus.sh architect` and writes a proposal under
`release/alpha-train/proposals/`. The proposal is explicitly marked
`STATUS: ADVISORY` and `NOT_AUTHORIZED_FOR_PUBLISH`. It must be reviewed and
converted into issues manually. It is not a queue entry.

The connected pipeline form is:

```bash
python scripts/release/alpha_release_train.py --pipeline --execute --max-count 1
```

This runs advisory planning first, writes a machine-readable pipeline report
under `release/alpha-train/reports/`, then consumes at most one prepared queue
candidate. If the queue is empty, it stops after planning and does not publish.

The continuous local watcher form is:

```bash
python scripts/release/alpha_release_train.py \
  --pipeline \
  --continuous \
  --execute \
  --max-count 1
```

This keeps running until a human stops the process. It periodically writes an
Opus advisory issue plan, watches `queue.json`, releases only prepared
unprocessed candidates, marks released candidates in local ignored state, and
continues sleeping when the queue is empty. Any failed gate or platform
verification remains fail-closed and stops the process.

The higher-automation local watcher form is:

```bash
python scripts/release/alpha_release_train.py \
  --pipeline \
  --continuous \
  --auto-promote-prepared \
  --execute \
  --max-count 1
```

This still does not promote Opus advisory text into a release. It only
discovers fully prepared local alpha artifacts already present in the repo,
adds unreleased candidates to `queue.json`, and then runs the same gated train.
Create `release/alpha-train/STOP` to stop before the next cycle. The default
continuous execution cap is one alpha per UTC day; use
`--max-releases-per-day 0` only after explicitly accepting unlimited daily
release cadence.

To avoid healthy empty loops, the train can also write a local draft candidate
bundle when no release-ready artifacts exist:

```bash
python scripts/release/alpha_release_train.py \
  --pipeline \
  --continuous \
  --auto-promote-prepared \
  --auto-prepare-next-alpha \
  --execute \
  --max-count 1
```

`--auto-prepare-next-alpha` is intentionally conservative. It writes a draft
bundle under `release/alpha-train/prepared/`, records the advisory reference and
source commit, and leaves `queue.json` unchanged. It does not bump package
versions, build publishable artifacts, create tags, dispatch workflows, or
publish. A release still requires the normal release-prep artifacts and gates.

The fully automated local release-prep form is:

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

When the queue is empty, `--auto-finalize-next-alpha` bumps the local Python and
TypeScript alpha versions, writes release notes, builds local artifacts, writes
manifest/checksum/upload-plan files, runs the release-prep gate, commits the
release-prep files, and then hands the candidate to the existing release train.
It still does not bypass gates, force-push, rewrite tags, or treat advisory
output as authority. npm `latest` movement is restricted to the deterministic
post-publish synchronization step for the same alpha version.

The preferred tmux entrypoint for that mode is:

```bash
scripts/release/start_alpha_train_full_auto.sh
```

The wrapper starts the `attestplane-alpha-train` tmux session with
`--full-auto-alpha`, refuses to start if another train session is running, and
refuses to start while `release/alpha-train/STOP` exists. The Python shortcut
expands to:

```bash
python scripts/release/alpha_release_train.py --full-auto-alpha
```

`--full-auto-alpha` is intentionally explicit and local-only. It means:
`--pipeline --continuous --auto-promote-prepared --auto-finalize-next-alpha
--execute --max-count 1 --max-releases-per-day 0 --max-prepares-per-day 0`.
It still stops fail-closed on release-prep, gate, tag, GitHub Release, PyPI,
npm, or registry verification failure.

Create `queue.json` from `queue.example.json` when an alpha candidate is ready.
The queue is finite; use `--max-count 1` for the standard "one alpha per run"
release train.

```bash
cp release/alpha-train/queue.example.json release/alpha-train/queue.json
python scripts/release/alpha_release_train.py --queue release/alpha-train/queue.json
python scripts/release/alpha_release_train.py --queue release/alpha-train/queue.json --execute --max-count 1
```

The default invocation is dry-run. `--execute` is required for tag, release,
workflow dispatch, and registry publication.
