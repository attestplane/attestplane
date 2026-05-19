#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

REPO_DIR="${ATTESTPLANE_REPO_DIR:-/Users/YOUR_USER/dev/attestplane}"
CONFIG_PATH="${LOCAL_CODEX_RUNNER_CONFIG:-${REPO_DIR}/.local-codex-runner.yml}"
LOG_DIR="${LOCAL_CODEX_RUNNER_LOG_DIR:-${HOME}/Library/Logs}"

mkdir -p "${LOG_DIR}"
cd "${REPO_DIR}"
export PATH="/opt/homebrew/bin:/usr/local/bin:${HOME}/.local/bin:${PATH}"

python -m scripts.local_codex_runner.run_once --config "${CONFIG_PATH}" "$@"

