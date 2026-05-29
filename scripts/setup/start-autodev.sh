#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
#
# Install and start both launchd services (Temporal server + autodev worker).
# Run once after cloning on a new machine, or after OS reboot.
#
# Usage: ./scripts/setup/start-autodev.sh [stop|restart|status]

set -euo pipefail

LAUNCHD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../deploy/launchd" && pwd)"
PLIST_SERVER="com.attestplane.temporal-server"
PLIST_WORKER="com.attestplane.autodev-worker"
LAUNCH_AGENTS="${HOME}/Library/LaunchAgents"

cmd="${1:-start}"

_load() {
  local name="$1"
  local src="${LAUNCHD_DIR}/${name}.plist"
  local dst="${LAUNCH_AGENTS}/${name}.plist"
  cp -f "${src}" "${dst}"
  launchctl bootout "gui/$(id -u)" "${dst}" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "${dst}"
  echo "✅ ${name} loaded"
}

_unload() {
  local name="$1"
  local dst="${LAUNCH_AGENTS}/${name}.plist"
  launchctl bootout "gui/$(id -u)" "${dst}" 2>/dev/null || true
  echo "⏹  ${name} unloaded"
}

_status() {
  local name="$1"
  launchctl print "gui/$(id -u)/${name}" 2>/dev/null | grep -E "state|pid" || \
    echo "${name}: not loaded"
}

mkdir -p "${LAUNCH_AGENTS}"

case "${cmd}" in
  start)
    echo "Starting Temporal server + autodev worker …"
    _load "${PLIST_SERVER}"
    # Give Temporal server 5 s to bind before starting worker
    sleep 5
    _load "${PLIST_WORKER}"
    echo ""
    echo "Temporal Web UI → http://localhost:8233"
    echo "Logs:"
    echo "  tail -f /Users/macworkers/projects/attestplane/data/temporal-server.log"
    echo "  tail -f /Users/macworkers/projects/attestplane/data/autodev-worker.log"
    ;;
  stop)
    _unload "${PLIST_WORKER}"
    _unload "${PLIST_SERVER}"
    ;;
  restart)
    "$0" stop
    sleep 2
    "$0" start
    ;;
  status)
    _status "${PLIST_SERVER}"
    _status "${PLIST_WORKER}"
    ;;
  *)
    echo "Usage: $0 [start|stop|restart|status]"
    exit 1
    ;;
esac
