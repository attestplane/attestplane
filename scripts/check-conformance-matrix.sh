#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
#
# Verify the checked-in conformance coverage matrix against the on-disk
# canonicalization negative vectors.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "${repo_root}/scripts/conformance/check_conformance_matrix.py"

