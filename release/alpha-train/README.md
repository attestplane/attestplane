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
