# P3.4 Local Codex Auto-Repair Runner Report

- **Date**: 2026-05-18
- **Status**: implemented
- **Scope**: local runner, tests, launchd template, documentation, evidence
- **No merge/tag/publish/PyPI**: confirmed

## What Was Implemented

P3.4 adds `scripts/local_codex_runner/`, a local-only automation subsystem that
polls approved GitHub issues, renders staged Codex prompts, supports dry-run by
default, runs local gates, applies deterministic review guards, and can create a
branch and PR for human review when explicitly configured out of dry-run mode.

The implementation uses `gh` through a small subprocess wrapper, not direct
GitHub API clients. All write operations support dry-run. Command output is
redacted before logs or exceptions are written.

## Safety Posture

- No automatic merge.
- No tag creation or movement.
- No package publish.
- No PyPI push.
- No default live external tests.
- No default `danger-full-access`.
- No token/cookie/private-key logging.
- No P0/P1 severity downgrade.
- No release gate weakening.

## Validation

Commands run during implementation:

```bash
python -m compileall scripts/local_codex_runner
pytest tests/local_codex_runner -q
ruff check scripts/local_codex_runner tests/local_codex_runner
```

Results: `compileall` passed, `pytest` passed with 32 tests, and `ruff`
reported all checks passed. `jit_audit` completed with no findings, but the
current implementation files were still untracked during that audit, so the JIT
diff scanner reported `changed_files=0`; local compile/test/ruff results are the
primary validation for this round.

The local `ask_opus.sh architect` prerequisite was attempted, but Claude CLI was
not logged in and returned `Not logged in · Please run /login`. No Claude login
state or credential files were read.

## Dry-Run Example

```bash
python -m scripts.local_codex_runner.run_issue \
  --config .local-codex-runner.yml \
  --issue-number 123 \
  --dry-run
```

## launchd Example

```bash
cp scripts/local_codex_runner/launchd/com.attestplane.local-codex-runner.plist.example \
  ~/Library/LaunchAgents/com.attestplane.local-codex-runner.plist
launchctl load ~/Library/LaunchAgents/com.attestplane.local-codex-runner.plist
launchctl unload ~/Library/LaunchAgents/com.attestplane.local-codex-runner.plist
```

## Residual Risks

- Full CI repair loop currently records failed check summaries and bounded
  status, but full failed-log ingestion depends on GitHub CLI availability.
- Real PR creation and CI watch were not exercised in this implementation round.
- Claim-safety and P0 repairs still need human review before merge.
