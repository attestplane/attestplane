#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
#
# Opus runner bootstrap — consolidate interpreter path (b000b56) and proxy
# configuration (28127b7) into a single, source-able script.
#
# Usage:
#   source scripts/ci/opus_runner_bootstrap.sh
#   ./scripts/ci/opus_runner_bootstrap.sh   # dry-run probe
#
# Environment variables (all optional):
#   OPUS_RUNNER_PYTHON          Python interpreter name/path (default: python3.11)
#   OPUS_RUNNER_PROXY_URL       Proxy URL (default: http://127.0.0.1:7897)
#   OPUS_RUNNER_NO_PROXY        NO_PROXY value (default: 127.0.0.1,localhost)
#   OPUS_RUNNER_SKIP_PROXY      Set to "1" to skip proxy configuration
#   OPUS_RUNNER_SKIP_INTERPRETER  Set to "1" to skip interpreter PATH setup
#   OPUS_RUNNER_LABEL_CHECK     Set to "0" to skip the runner-label guard
#
# When sourced, this script exports the proxy and interpreter environment
# for the calling shell. When executed directly, it runs a read-only probe
# and exits 0 if the environment is usable.

set -euo pipefail

# ---------------------------------------------------------------------------
# Guard: only configure on an opus-plan runner unless explicitly overridden.
# ---------------------------------------------------------------------------
OPUS_RUNNER_LABEL_CHECK="${OPUS_RUNNER_LABEL_CHECK:-1}"
if [ "${OPUS_RUNNER_LABEL_CHECK}" = "1" ]; then
  if [ -z "${RUNNER_LABELS:-}" ] && [ -z "${GITHUB_ACTIONS:-}" ]; then
    # Not running inside a GitHub Actions runner at all — assume local dev
    # and proceed without the runner-label guard.
    :
  elif [ -n "${RUNNER_LABELS:-}" ]; then
    # Inside a runner — verify the opus-plan label is present.
    case ",${RUNNER_LABELS}," in
      *,opus-plan,*) ;;
      *)
        echo "[opus_runner_bootstrap] WARNING: runner labels (${RUNNER_LABELS}) lack 'opus-plan'; skipping opus-specific setup" >&2
        export OPUS_RUNNER_ACTIVE="false"
        return 0 2>/dev/null || exit 0
        ;;
    esac
  fi
fi

export OPUS_RUNNER_ACTIVE="true"

# ---------------------------------------------------------------------------
# Interpreter path (b000b56)
# ---------------------------------------------------------------------------
if [ "${OPUS_RUNNER_SKIP_INTERPRETER:-0}" != "1" ]; then
  OPUS_RUNNER_PYTHON="${OPUS_RUNNER_PYTHON:-python3.11}"
  OPUS_RUNNER_HOMEBREW_PREFIX="${OPUS_RUNNER_HOMEBREW_PREFIX:-/opt/homebrew}"

  # Prepend Homebrew bin so the interpreter is found even when the runner
  # image does not have it on the default PATH.
  if [ -d "${OPUS_RUNNER_HOMEBREW_PREFIX}/bin" ]; then
    PATH="${OPUS_RUNNER_HOMEBREW_PREFIX}/bin:${PATH}"
  fi

  if command -v "${OPUS_RUNNER_PYTHON}" &>/dev/null; then
    export OPUS_RUNNER_PYTHON
    export PATH
    export ARCHITECTURE_AUDIT_PYTHON="${OPUS_RUNNER_PYTHON}"
  else
    echo "[opus_runner_bootstrap] WARNING: ${OPUS_RUNNER_PYTHON} not found on PATH" >&2
  fi
fi

# ---------------------------------------------------------------------------
# Proxy configuration (28127b7)
# ---------------------------------------------------------------------------
if [ "${OPUS_RUNNER_SKIP_PROXY:-0}" != "1" ]; then
  OPUS_RUNNER_PROXY_URL="${OPUS_RUNNER_PROXY_URL:-http://127.0.0.1:7897}"
  OPUS_RUNNER_NO_PROXY="${OPUS_RUNNER_NO_PROXY:-127.0.0.1,localhost}"

  export HTTP_PROXY="${OPUS_RUNNER_PROXY_URL}"
  export HTTPS_PROXY="${OPUS_RUNNER_PROXY_URL}"
  export ALL_PROXY="${OPUS_RUNNER_PROXY_URL}"
  export NO_PROXY="${OPUS_RUNNER_NO_PROXY}"
fi

# ---------------------------------------------------------------------------
# Dry-run mode (direct execution, not sourced)
# ---------------------------------------------------------------------------
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  echo "[opus_runner_bootstrap] OPUS_RUNNER_ACTIVE=${OPUS_RUNNER_ACTIVE}"
  echo "[opus_runner_bootstrap] python=$(command -v "${OPUS_RUNNER_PYTHON:-python3.11}" 2>/dev/null || echo 'not found')"
  echo "[opus_runner_bootstrap] proxy=${OPUS_RUNNER_PROXY_URL:-<skipped>}"
  echo "[opus_runner_bootstrap] PATH=${PATH}"
fi
