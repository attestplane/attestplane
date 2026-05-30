# Opus CI Runner Runbook

> Part of consolidation for [#103] — v1.6.0 stabilization.
> Extends `architecture-audit.yml` and `release-planning.yml` runner
> configuration. Not a new automation track.

This runbook documents the Opus planning runner network and interpreter
configuration for the Attestplane CI sidecar workflows
(`architecture-audit.yml`, `release-planning.yml`) and the local runner
bootstrap scripts under `scripts/ci/`.

## Change History

| Commit | Change | Rationale |
|---|---|---|
| `b000b56` | Local Python interpreter path | The self-hosted opus-plan runner requires `/opt/homebrew/bin` on `PATH` so that `python3.11` (the `ARCHITECTURE_AUDIT_PYTHON` interpreter) resolves without relying on the GitHub-hosted runner tool cache. |
| `28127b7` | Proxy env vars | All outbound HTTP/S traffic from the opus-plan runner routes through a local forward proxy (`127.0.0.1:7897`) to avoid GitHub H2 proxy stalls and to provide a single observability egress point. Traffic to `127.0.0.1,localhost` is excluded from the proxy. |

Both changes are consolidated into the bootstrap script at
`scripts/ci/opus_runner_bootstrap.sh` so that workflows no longer need inline
shell heredocs for interpreter or proxy configuration.

## Architecture

```text
GitHub Actions runner (self-hosted, macOS, ARM64, opus-plan)
  │
  ├─ Bootstrap: scripts/ci/opus_runner_bootstrap.sh
  │   ├─ PATH += /opt/homebrew/bin          (b000b56)
  │   ├─ HTTP_PROXY / HTTPS_PROXY / ALL_PROXY  (28127b7)
  │   └─ NO_PROXY = 127.0.0.1,localhost
  │
  ├─ Interpreter: $OPUS_RUNNER_PYTHON (default: python3.11)
  │   └─ Used by architecture-audit / release-planning steps
  │
  ├─ Proxy: $OPUS_RUNNER_PROXY_URL (default: http://127.0.0.1:7897)
  │   └─ All outbound HTTP/S; localhost/GitHub API excluded
  │
  ├─ ask_opus.sh --dry-run  (selftest, read-only)
  └─ ask_opus.sh architect  (live planning, workflow_dispatch only)
```

## Environment Variables

These variables are defined in the CI workflow `env:` block (not inline
heredocs) and respected by `opus_runner_bootstrap.sh`:

| Variable | Default | Purpose |
|---|---|---|
| `ARCHITECTURE_AUDIT_PYTHON` | `python3.11` | Python interpreter for audit scripts |
| `HTTP_PROXY` | `http://127.0.0.1:7897` | HTTP forward proxy |
| `HTTPS_PROXY` | `http://127.0.0.1:7897` | HTTPS forward proxy |
| `ALL_PROXY` | `http://127.0.0.1:7897` | All-protocol forward proxy |
| `NO_PROXY` | `127.0.0.1,localhost` | Bypass proxy for local addresses |

### Opus runner bootstrap overrides

| Variable | Default | Purpose |
|---|---|---|
| `OPUS_RUNNER_PYTHON` | `python3.11` | Override interpreter name or path |
| `OPUS_RUNNER_PROXY_URL` | `http://127.0.0.1:7897` | Override proxy URL |
| `OPUS_RUNNER_NO_PROXY` | `127.0.0.1,localhost` | Override no-proxy list |
| `OPUS_RUNNER_SKIP_PROXY` | unset / `0` | Set to `1` to skip proxy config |
| `OPUS_RUNNER_SKIP_INTERPRETER` | unset / `0` | Set to `1` to skip interpreter PATH setup |
| `OPUS_RUNNER_LABEL_CHECK` | `1` | Set to `0` to skip the runner-label guard |

### Guarded fallback

When `RUNNER_LABELS` does not contain `opus-plan`, the bootstrap script sets
`OPUS_RUNNER_ACTIVE=false` and skips all opus-specific setup. This prevents
the proxy or interpreter changes from affecting non-opus runner environments.
When `GITHUB_ACTIONS` is not set (local development), the guard passes
through without warning — the script is safe to source in any context.

## Files

| Path | Purpose |
|---|---|
| `scripts/ci/opus_runner_bootstrap.sh` | Consolidated interpreter + proxy bootstrap |
| `scripts/ci/opus_runner_selftest.sh` | Read-only smoke probe (exit 0 = healthy) |
| `scripts/ci/prompts/selftest_fixture.md` | Minimal dry-run fixture for selftest |

## Selftest Procedure

Run the smoke probe locally or in CI to verify the runner bootstrap:

```bash
bash scripts/ci/opus_runner_selftest.sh
```

The probe performs five checks:

1. Bootstrap script exists and is readable.
2. Fixture prompt exists and is readable.
3. Bootstrap sources cleanly; interpreter and proxy env vars are exported.
4. `ask_opus.sh --dry-run` resolves against the fixture prompt without
   calling an external AI service.
5. Proxy configuration is internally consistent (best-effort static check).

Expected output for a healthy non-opus environment:

```text
=== opus_runner_selftest: smoke probe ===
--- [1/5] Bootstrap availability ---
  ✅ bootstrap script found at ...
--- [2/5] Fixture availability ---
  ✅ fixture prompt found at ...
--- [3/5] Bootstrap execution ---
  ✅ OPUS_RUNNER_ACTIVE=false (not on opus-plan runner, fallback OK)
  ✅ interpreter: python3.11 not on PATH (acceptable in non-opus environment)
--- [4/5] ask_opus.sh --dry-run ---
  ✅ ask_opus.sh not on PATH — skipping dry-run (acceptable)
--- [5/5] Network egress guard ---
  ✅ not on opus-plan runner — network egress guard skipped
=== results: 5 passed, 0 failed ===
```

## Failure Mode: #106

Issue [#106] reported that the `architecture-audit` workflow failed during the
v1.6.0 audit run because:

1. The inline shell heredoc for the "Use local Python on Opus runner" step
   was duplicated across multiple steps and workflows, making it impossible
   to update consistently.
2. When the proxy URL changed (e.g., during a runner re-registration), the
   inline proxy env vars in the workflow had to be updated independently from
   the interpreter configuration — there was no single source of truth.
3. The failure was silent: the heredoc ran but `set -euo pipefail` was absent
   from the inline block, so a missing interpreter did not fail the step.

The fix (consolidated in this runbook):

- **Single source**: `opus_runner_bootstrap.sh` owns both the interpreter path
  and proxy configuration.
- **Explicit env vars**: Workflows declare `ARCHITECTURE_AUDIT_PYTHON`,
  `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, and `NO_PROXY` in the `env:`
  block, not in inline shell heredocs.
- **Guarded fallback**: The script exits cleanly (no-op) when the runner
  label is not `opus-plan`.
- **Selftest**: `opus_runner_selftest.sh` exercises the bootstrap in a
  read-only smoke probe.

To reproduce #106 under the new config:

```bash
# Simulate a non-opus runner to test the guarded fallback
RUNNER_LABELS="self-hosted,macOS,ARM64" bash scripts/ci/opus_runner_selftest.sh

# Simulate the opus runner to test full bootstrap
RUNNER_LABELS="self-hosted,macOS,ARM64,opus-plan" bash scripts/ci/opus_runner_selftest.sh
```

Under the old config, the second command would have failed if python3.11 was
missing on PATH (the heredoc had no guard). Under the new config, the
bootstrap logs a warning and continues without hard-failing the workflow.

## Rollout Plan

1. Land the bootstrap and selftest scripts behind `workflow_dispatch` only
   (no scheduled trigger).
2. Update `architecture-audit.yml` and `release-planning.yml` to source
   `opus_runner_bootstrap.sh` instead of inline heredocs. (This step requires
   a separate PR since this runbook documents the intended state.)
3. Run the workflow manually twice. Verify both runs succeed.
4. Flip the scheduled trigger on.

No secrets are added during this rollout. The proxy URL stays in repository
variables; proxy credentials remain in the existing runner secret.

## Validation

```bash
# Lint workflow files
yamllint .github/workflows/architecture-audit.yml .github/workflows/release-planning.yml

# Dry-run the audit workflow locally (requires act)
act -W .github/workflows/architecture-audit.yml -j plan --dryrun

# Run the self-test probe
bash scripts/ci/opus_runner_selftest.sh
```

[#103]: https://github.com/attestplane/attestplane/issues/103
[#106]: https://github.com/attestplane/attestplane/issues/106
