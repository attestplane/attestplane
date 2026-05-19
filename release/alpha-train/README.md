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
