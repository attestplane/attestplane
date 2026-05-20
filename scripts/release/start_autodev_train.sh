#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SESSION="${AUTODEV_TRAIN_SESSION:-autodev-train}"
REPORTS_DIR="$ROOT/release/alpha-train/reports"
STOP_FILE="$ROOT/release/alpha-train/STOP"
PYTHON_BIN="${AUTODEV_TRAIN_PYTHON:-$ROOT/sdk/python/.venv/bin/python}"
TMUX_BIN="${AUTODEV_TRAIN_TMUX:-tmux}"
MODE="${AUTODEV_TRAIN_MODE:-rc-watch}"

mkdir -p "$REPORTS_DIR"

if "$TMUX_BIN" has-session -t "$SESSION" 2>/dev/null; then
  echo "autodev-train tmux session already running: $SESSION" >&2
  exit 1
fi

if [[ -f "$STOP_FILE" ]]; then
  echo "autodev-train STOP file exists: $STOP_FILE" >&2
  echo "remove it explicitly before starting autodev-train" >&2
  exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python runtime is not executable: $PYTHON_BIN" >&2
  exit 1
fi

STAMP="$(date -u +%Y%m%d-%H%M%S)"
LOG="$REPORTS_DIR/continuous-autodev-train-tmux-$STAMP.log"

case "$MODE" in
  rc-watch)
    CMD="exec '$PYTHON_BIN' scripts/release/rc_release_watch.py 2>&1 | tee '$LOG'"
    ;;
  full-auto-alpha)
    CMD="exec '$PYTHON_BIN' scripts/release/alpha_release_train.py --full-auto-alpha 2>&1 | tee '$LOG'"
    ;;
  full-auto-rc)
    CMD="exec '$PYTHON_BIN' scripts/release/rc_auto_train.py --continuous 2>&1 | tee '$LOG'"
    ;;
  *)
    echo "unsupported AUTODEV_TRAIN_MODE: $MODE" >&2
    echo "supported modes: rc-watch, full-auto-alpha, full-auto-rc" >&2
    exit 1
    ;;
esac

"$TMUX_BIN" new-session -d -s "$SESSION" -c "$ROOT" \
  "echo STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ); echo MODE='$MODE'; $CMD"

echo "autodev-train session started: $SESSION"
echo "mode: $MODE"
echo "log: $LOG"
