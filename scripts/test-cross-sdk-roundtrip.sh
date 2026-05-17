#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
#
# Local driver for the Py↔TS cross-SDK round-trip test (Gap G1, tier T2).
# Mirrors what `.github/workflows/cross-sdk-roundtrip.yml` does in CI so
# developers can reproduce failures locally.
#
# Prereqs:
#   - Python SDK installed in the active venv (e.g. uv pip install -e sdk/python[dev])
#   - TypeScript SDK built (pnpm -C sdk/typescript install && pnpm -C sdk/typescript build)
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"

if [ ! -f sdk/typescript/dist/index.js ]; then
  echo "::error::sdk/typescript/dist/index.js missing — run \`pnpm -C sdk/typescript build\` first." >&2
  exit 1
fi

echo "=== step 1: Python SDK emit ==="
python3 tests/cross_sdk/py_emit.py

echo "=== step 2: TypeScript SDK round-trip ==="
node tests/cross_sdk/ts_roundtrip.mjs

echo "=== step 3: Python SDK verify ==="
python3 tests/cross_sdk/py_verify.py

echo ""
echo "Cross-SDK round-trip PASSED ✓"
