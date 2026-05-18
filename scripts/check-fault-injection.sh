#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python scripts/fault/check_fault_matrix.py
sdk/python/.venv/bin/pytest sdk/python/tests/fault_injection
(cd sdk/typescript && npm test -- fault_injection)
