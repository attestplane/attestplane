#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
#
# Register runner instances 2-5 on this Mac alongside the existing runner-1.
# The token auto-fetches via gh CLI (requires GITHUB_TOKEN or gh auth).
#
# Usage: ./scripts/setup/register-runners.sh
#   or:  TOKEN=xxx ./scripts/setup/register-runners.sh

set -euo pipefail

REPO_URL="https://github.com/attestplane/attestplane"
RUNNER_BASE="${HOME}"
SOURCE_RUNNER="${RUNNER_BASE}/actions-runner-attestplane-opus"
RUNNER_TAR="${SOURCE_RUNNER}/actions-runner-osx-arm64-2.334.0.tar.gz"

# Fetch fresh registration token automatically
TOKEN="${TOKEN:-$(gh api repos/attestplane/attestplane/actions/runners/registration-token \
  --method POST --jq .token)}"

echo "Registration token: ${TOKEN:0:8}…"

for i in 2 3 4 5; do
  RUNNER_DIR="${RUNNER_BASE}/actions-runner-attestplane-opus-${i}"

  if [ -d "${RUNNER_DIR}/.runner" ]; then
    echo "Runner ${i}: already configured at ${RUNNER_DIR}, skipping"
    continue
  fi

  echo "Setting up runner ${i} at ${RUNNER_DIR} …"
  mkdir -p "${RUNNER_DIR}"
  tar xzf "${RUNNER_TAR}" -C "${RUNNER_DIR}" --strip-components=0 2>/dev/null || \
    tar xzf "${RUNNER_TAR}" -C "${RUNNER_DIR}"

  "${RUNNER_DIR}/config.sh" \
    --url    "${REPO_URL}" \
    --token  "${TOKEN}" \
    --name   "macworkers-opus-plan-${i}" \
    --labels "self-hosted,macOS,ARM64,opus-plan" \
    --work   "_work" \
    --unattended \
    --replace

  # Install and start as a launchd service
  pushd "${RUNNER_DIR}" > /dev/null
  sudo ./svc.sh install
  sudo ./svc.sh start
  popd > /dev/null

  echo "✅ Runner ${i} (macworkers-opus-plan-${i}) registered and started"
done

echo ""
echo "Done. Active runners:"
gh api repos/attestplane/attestplane/actions/runners \
  --jq '.runners[] | "  \(.name) [\(.status)] labels=\([.labels[].name] | join(","))"'
