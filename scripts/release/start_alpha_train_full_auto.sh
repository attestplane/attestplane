#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SESSION="${ATTESTPLANE_ALPHA_TRAIN_SESSION:-attestplane-alpha-train}"
REPORTS_DIR="$ROOT/release/alpha-train/reports"
STOP_FILE="$ROOT/release/alpha-train/STOP"
PYTHON_BIN="${ATTESTPLANE_ALPHA_TRAIN_PYTHON:-$ROOT/sdk/python/.venv/bin/python}"
TMUX_BIN="${ATTESTPLANE_ALPHA_TRAIN_TMUX:-tmux}"

mkdir -p "$REPORTS_DIR"

if "$TMUX_BIN" has-session -t "$SESSION" 2>/dev/null; then
  echo "alpha train tmux session already running: $SESSION" >&2
  exit 1
fi

if [[ -f "$STOP_FILE" ]]; then
  echo "alpha train STOP file exists: $STOP_FILE" >&2
  echo "remove it explicitly before starting full-auto mode" >&2
  exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python runtime is not executable: $PYTHON_BIN" >&2
  exit 1
fi

STAMP="$(date -u +%Y%m%d-%H%M%S)"
LOG="$REPORTS_DIR/continuous-alpha-train-tmux-$STAMP.log"

"$TMUX_BIN" new-session -d -s "$SESSION" -c "$ROOT" \
  "echo STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ); exec '$PYTHON_BIN' scripts/release/alpha_release_train.py --full-auto-alpha 2>&1 | tee '$LOG'"

echo "alpha train full-auto session started: $SESSION"
echo "log: $LOG"
