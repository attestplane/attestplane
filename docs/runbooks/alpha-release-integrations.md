# Alpha Release Integration Evidence

The alpha train can now write a local integration status packet after a release
candidate reaches `registry_verified`.

This is an observability layer. It is not an authority layer.

## Integrated Surfaces

| Surface | Role | Authority |
| --- | --- | --- |
| Linear | Record optional issue-train status for release bugs, blockers, and version decisions | Non-authoritative |
| Sentry | Record optional runtime failure source facts for regressions and exception tracking | Non-authoritative |
| GitHub | Read branch, tag, GitHub Release, assets, and recent workflow facts | Non-authoritative |
| CodeRabbit | Record CLI/auth availability for optional advisory review | Advisory-only |
| Codex Security | Inventory local security scan surfaces such as gitleaks and verifier gates | Advisory-only |
| Documents | Generate a Markdown evidence packet for human review | Non-authoritative |

The integration adapter does not:

- publish packages,
- create or edit GitHub Releases,
- dispatch workflows,
- create tags,
- move npm dist-tags,
- approve release scope,
- mark blockers as resolved, or
- print secrets.

## Command

```bash
python scripts/release/alpha_train_integrations.py \
  --release v0.1.5-alpha \
  --json
```

The command writes:

```text
release/alpha-train/reports/integration-status-<release>.json
release/alpha-train/reports/integration-status-<release>.md
```

The JSON schema is `attestplane_alpha_integration_status.v1`.

## Evidence Contents

The packet records:

- Linear workspace/availability facts,
- Sentry workspace/availability facts,
- local and remote `main` convergence,
- remote tag observation,
- GitHub Release observation,
- recent GitHub Actions runs,
- PyPI and npm publication observation,
- npm `latest` and `alpha` dist-tag alignment,
- SQLite release stage state,
- SQLite `git_push_tasks` queue state,
- CodeRabbit availability/auth status,
- Codex Security local check inventory, and
- explicit non-actions.

## Failure Semantics

Integration failures are limitations, not release authorization changes. A
missing CodeRabbit CLI, temporary GitHub query failure, or registry propagation
delay is recorded in the packet. A queued or temporarily failed `git push`
records transport state only; it does not block later candidates or grant new
authority. The release train remains governed by the deterministic release
stages and registry verification.

## Human Review Use

Use the Markdown packet to quickly answer:

1. Did GitHub observe the release and tag?
2. Did PyPI and npm observe the intended versions?
3. Did npm `latest` and `alpha` point at the same alpha?
4. Which SQLite stage rows were marked `done`?
5. Were any optional advisory surfaces unavailable?

The packet is intentionally concise so it can be pasted into issue comments,
release logs, or post-run summaries without carrying raw terminal logs.
