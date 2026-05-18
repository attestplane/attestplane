#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR="$(mktemp -d "${TMPDIR:-/tmp}/attestplane-api.XXXXXX")"
trap 'rm -rf "$TMPDIR"' EXIT

python "$ROOT/scripts/api/extract_python_public_api.py" \
  --out "$TMPDIR/python_current.json"
python "$ROOT/scripts/api/extract_typescript_public_api.py" \
  --out "$TMPDIR/typescript_current.json"

python "$ROOT/scripts/api/check_public_api_manifest.py" \
  --python-current "$TMPDIR/python_current.json" \
  --typescript-current "$TMPDIR/typescript_current.json" \
  --python-baseline "$ROOT/api/public/python_v1.json" \
  --typescript-baseline "$ROOT/api/public/typescript_v1.json" \
  --allowlist "$ROOT/api/public/py_ts_allowlist_v1.json"
