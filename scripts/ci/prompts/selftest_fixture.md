<!--
SPDX-FileCopyrightText: 2026 Attestplane Contributors
SPDX-License-Identifier: Apache-2.0
-->
# Opus Runner Self-Test Fixture

This is a read-only fixture used by `opus_runner_selftest.sh` to verify that
the Opus planning runner can resolve its interpreter and dependency chain
without network egress beyond the configured proxy.

The fixture is intentionally minimal. Its purpose is to exercise the runner
bootstrap, not to produce a real plan.

## Request

Verify that the local Python interpreter is reachable and that the
`ask_opus.sh` bridge resolves its `--dry-run` path without external
API calls or unproxied network access.

Print the resolved interpreter version and the dry-run exit code.
Do not call any external AI service.
Do not read, log, or expose secrets, tokens, or credentials.
Do not modify any file under the repository root.

## Acceptance

- python3.11 --version resolves without error.
- ask_opus.sh --dry-run exits 0 (or cleanly reports that the bridge
  is unavailable, without cascading into a hard failure).
- No unproxied network egress is attempted.
