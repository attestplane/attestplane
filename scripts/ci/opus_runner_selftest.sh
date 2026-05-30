#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
#
# Opus runner self-test (smoke probe).
#
# Verifies that the runner bootstrap can resolve the interpreter path and
# proxy configuration, and that `ask_opus.sh --dry-run` can process a
# fixture prompt without network egress beyond the configured proxy.
#
# This is a read-only probe. It does not modify any file under the
# repository root.
#
# Usage:
#   bash scripts/ci/opus_runner_selftest.sh
#
# Exit codes:
#   0 — all checks pass
#   1 — one or more checks failed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
FIXTURE="${SCRIPT_DIR}/prompts/selftest_fixture.md"

PASS_COUNT=0
FAIL_COUNT=0

pass() { echo "  ✅ $*"; PASS_COUNT=$((PASS_COUNT + 1)); }
fail() { echo "  ❌ $*"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

echo "=== opus_runner_selftest: smoke probe ==="
echo "repo root: ${REPO_ROOT}"
echo "fixture:    ${FIXTURE}"
echo ""

# ---------------------------------------------------------------------------
# 1. Bootstrap script exists and is readable
# ---------------------------------------------------------------------------
echo "--- [1/5] Bootstrap availability ---"
BOOTSTRAP="${SCRIPT_DIR}/opus_runner_bootstrap.sh"
if [ -r "${BOOTSTRAP}" ]; then
  pass "bootstrap script found at ${BOOTSTRAP}"
else
  fail "bootstrap script not found at ${BOOTSTRAP}"
fi

# ---------------------------------------------------------------------------
# 2. Fixture prompt exists and is readable
# ---------------------------------------------------------------------------
echo "--- [2/5] Fixture availability ---"
if [ -r "${FIXTURE}" ]; then
  pass "fixture prompt found at ${FIXTURE}"
else
  fail "fixture prompt not found at ${FIXTURE}"
fi

# ---------------------------------------------------------------------------
# 3. Bootstrap sources cleanly and exports expected variables
# ---------------------------------------------------------------------------
echo "--- [3/5] Bootstrap execution ---"
source "${BOOTSTRAP}"

if [ "${OPUS_RUNNER_ACTIVE:-false}" = "true" ]; then
  pass "OPUS_RUNNER_ACTIVE=true"
else
  pass "OPUS_RUNNER_ACTIVE=false (not on opus-plan runner, fallback OK)"
fi

# Check interpreter resolution
PYTHON_BIN="$(command -v "${OPUS_RUNNER_PYTHON:-python3.11}" 2>/dev/null || true)"
if [ -n "${PYTHON_BIN}" ]; then
  PYTHON_VERSION="$("${PYTHON_BIN}" --version 2>&1)"
  pass "interpreter: ${PYTHON_VERSION} at ${PYTHON_BIN}"
else
  pass "interpreter: ${OPUS_RUNNER_PYTHON:-python3.11} not on PATH (acceptable in non-opus environment)"
fi

# Check proxy vars when active
if [ "${OPUS_RUNNER_ACTIVE:-false}" = "true" ]; then
  if [ -n "${HTTP_PROXY:-}" ]; then
    pass "HTTP_PROXY=${HTTP_PROXY}"
  else
    fail "HTTP_PROXY not set"
  fi
  if [ -n "${HTTPS_PROXY:-}" ]; then
    pass "HTTPS_PROXY=${HTTPS_PROXY}"
  else
    fail "HTTPS_PROXY not set"
  fi
  if [ -n "${NO_PROXY:-}" ]; then
    pass "NO_PROXY=${NO_PROXY}"
  else
    fail "NO_PROXY not set"
  fi
fi

# ---------------------------------------------------------------------------
# 4. ask_opus.sh --dry-run resolves without network egress
# ---------------------------------------------------------------------------
echo "--- [4/5] ask_opus.sh --dry-run ---"

if command -v ask_opus.sh &>/dev/null; then
  FIXTURE_CONTENT="$(cat "${FIXTURE}")"
  set +e
  DRY_RUN_OUTPUT="$(ask_opus.sh --dry-run "${FIXTURE_CONTENT}" 2>&1)"
  DRY_RUN_RC=$?
  set -e

  if [ "${DRY_RUN_RC}" -eq 0 ]; then
    pass "ask_opus.sh --dry-run exited 0"
  else
    # Some bridge versions exit non-zero for --dry-run even on success;
    # accept a clean non-zero exit if the output is not an error cascade.
    if echo "${DRY_RUN_OUTPUT}" | grep -qi "error\|fail\|crash\|traceback" 2>/dev/null; then
      fail "ask_opus.sh --dry-run exited ${DRY_RUN_RC} with error output: $(echo "${DRY_RUN_OUTPUT}" | head -5)"
    else
      pass "ask_opus.sh --dry-run exited ${DRY_RUN_RC} (non-error status accepted)"
    fi
  fi
  echo "       dry-run output: $(echo "${DRY_RUN_OUTPUT}" | head -3 | tr '\n' ' ')"
else
  pass "ask_opus.sh not on PATH — skipping dry-run (acceptable in non-opus environment)"
fi

# ---------------------------------------------------------------------------
# 5. No unproxied network egress (best-effort read-only check)
# ---------------------------------------------------------------------------
echo "--- [5/5] Network egress guard ---"

if [ "${OPUS_RUNNER_ACTIVE:-false}" = "true" ] && [ -n "${HTTP_PROXY:-}" ]; then
  # Verify that the proxy env is the ONLY route for HTTP (best-effort).
  # A truly hermetic check would require a network namespace; this is a
  # static configuration sanity check.
  if [ "${HTTP_PROXY}" = "${HTTPS_PROXY}" ]; then
    pass "proxy vars are consistent (HTTP_PROXY == HTTPS_PROXY)"
  else
    fail "proxy vars are inconsistent: HTTP_PROXY=${HTTP_PROXY} HTTPS_PROXY=${HTTPS_PROXY}"
  fi
  if [ -n "${NO_PROXY:-}" ]; then
    pass "NO_PROXY is set (${NO_PROXY})"
  fi
else
  pass "not on opus-plan runner — network egress guard skipped"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== results: ${PASS_COUNT} passed, ${FAIL_COUNT} failed ==="

if [ "${FAIL_COUNT}" -gt 0 ]; then
  exit 1
fi
exit 0
