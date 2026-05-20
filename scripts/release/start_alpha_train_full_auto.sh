#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export AUTODEV_TRAIN_SESSION="${ATTESTPLANE_ALPHA_TRAIN_SESSION:-autodev-train}"
export AUTODEV_TRAIN_PYTHON="${ATTESTPLANE_ALPHA_TRAIN_PYTHON:-$ROOT/sdk/python/.venv/bin/python}"
export AUTODEV_TRAIN_TMUX="${ATTESTPLANE_ALPHA_TRAIN_TMUX:-tmux}"

echo "start_alpha_train_full_auto.sh is a compatibility wrapper; use start_autodev_train.sh for new runs." >&2
exec "$ROOT/scripts/release/start_autodev_train.sh"
