#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root/sdk/python"

PYTHONPATH=src python3.11 -m pytest tests/cli/test_verify_json_contract.py -q
PYTHONPATH=src python3.11 -m pytest tests/conformance -k "exit_code or unknown_required" -q

echo "exit-code pinning gate: PASS"
