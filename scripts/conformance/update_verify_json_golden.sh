#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
#
# Explicit golden update step for the versioned `verify --json` contract.
#
# Usage:
#   ./scripts/conformance/update_verify_json_golden.sh
#
# This regenerates fixtures/golden/verify_json_v1.json from the canonical
# valid bundle fixture at fixtures/valid_bundle.att.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
out_file="${repo_root}/fixtures/golden/verify_json_v1.json"
bundle_file="${repo_root}/fixtures/valid_bundle.att"

mkdir -p "$(dirname "${out_file}")"
PYTHONPATH="${repo_root}/sdk/python/src" python3.11 -m attestplane.cli.main verify --json "${bundle_file}" > "${out_file}"
