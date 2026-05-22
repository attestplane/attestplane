#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

REPO_DIR="${ATTESTPLANE_REPO_DIR:-/Users/YOUR_USER/dev/attestplane}"
LOG_DIR="${LOCAL_CODEX_RUNNER_LOG_DIR:-${REPO_DIR}/release/alpha-train/reports}"
POLL_SECONDS="${LOCAL_CODEX_RUNNER_POLL_SECONDS:-300}"

LANE_SPECS=(
  "p0-1:${LOCAL_CODEX_RUNNER_P0_CONFIG:-${REPO_DIR}/.local/codex-runner-p0.yml}"
  "p1-1:${LOCAL_CODEX_RUNNER_P1_CONFIG:-${REPO_DIR}/.local/codex-runner-p1-1.yml}"
  "p1-2:${LOCAL_CODEX_RUNNER_P1_2_CONFIG:-${REPO_DIR}/.local/codex-runner-p1-2.yml}"
  "p2-docs-1:${LOCAL_CODEX_RUNNER_P2_DOCS_CONFIG:-${REPO_DIR}/.local/codex-runner-p2-docs.yml}"
)

mkdir -p "${LOG_DIR}"
export PATH="/opt/homebrew/bin:/usr/local/bin:${HOME}/.local/bin:${PATH}"

for spec in "${LANE_SPECS[@]}"; do
  lane="${spec%%:*}"
  config="${spec#*:}"
  session="local-codex-runner-${lane}"
  log="${LOG_DIR}/${session}.log"
  if [[ ! -f "${config}" ]]; then
    printf 'skip %s: missing config %s\n' "${session}" "${config}" >&2
    continue
  fi
  if tmux has-session -t "${session}" 2>/dev/null; then
    printf 'skip %s: tmux session already exists\n' "${session}" >&2
    continue
  fi
  tmux new-session -d -s "${session}" \
    "cd ${REPO_DIR@Q} && while true; do date -u '+%Y-%m-%dT%H:%M:%SZ ${session} cycle start'; python -m scripts.local_codex_runner.run_once --config ${config@Q}; date -u '+%Y-%m-%dT%H:%M:%SZ ${session} cycle end'; sleep ${POLL_SECONDS@Q}; done 2>&1 | tee -a ${log@Q}"
  printf 'started %s with %s\n' "${session}" "${config}"
done
