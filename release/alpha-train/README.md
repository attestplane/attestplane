# Alpha Release Train

This directory defines finite alpha release-train candidates for Attestplane.
It is intentionally queue-based and bounded. The train does not invent product
scope, generate code, or publish an unprepared version.

## Contract

- Each candidate is one alpha release.
- Each candidate must already have release notes, package versions, local
  artifacts, release manifest, and checksums.
- The runner stops on the first failed gate or platform verification failure.
- The runner never promotes npm `latest`.
- The runner does not retag existing releases.
- The runner does not claim production readiness, compliance readiness,
  certification, SLSA level, or signed provenance unless those artifacts are
  actually present and verified.

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
