#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${ROOT}/sdk/python/.venv/bin/python"
PYTEST="${ROOT}/sdk/python/.venv/bin/pytest"
TMPDIR="$(mktemp -d "${TMPDIR:-/tmp}/attestplane-proofbundle.XXXXXX")"
trap 'rm -rf "$TMPDIR"' EXIT

echo "=== check: alpha ProofBundle verifier unit tests ==="
"${PYTEST}" "${ROOT}/sdk/python/tests/cli/test_proofbundle_alpha.py" -q

echo ""
echo "=== check: alpha ProofBundle verifier fixture exit codes and JSON reports ==="
declare -A expected=(
  ["valid_minimal.json"]=0
  ["missing_required_field.json"]=2
  ["malformed.json"]=2
  ["invalid_hash_format.json"]=2
  ["tampered_artifact_hash.json"]=1
  ["broken_hash_chain.json"]=1
  ["unsupported_version.json"]=2
  ["missing_dsse_shape.json"]=2
  ["missing_storage_compat.json"]=2
)

for fixture in "${!expected[@]}"; do
  out="${TMPDIR}/${fixture}.report.json"
  set +e
  PYTHONPATH="${ROOT}/sdk/python/src" "${PYTHON}" -c \
    'import sys; from attestplane.cli.main import main; raise SystemExit(main(sys.argv[1:]))' \
    verify-proofbundle "${ROOT}/tests/fixtures/proofbundle/${fixture}" >"${out}"
  rc=$?
  set -e
  if [ "${rc}" -ne "${expected[$fixture]}" ]; then
    echo "::error file=tests/fixtures/proofbundle/${fixture}::expected rc ${expected[$fixture]}, got ${rc}" >&2
    cat "${out}" >&2 || true
    exit 1
  fi
  jq empty "${out}"
  jq -e '.verification_scope == "proofbundle_alpha_local"' "${out}" >/dev/null
  jq -e '.signature_verification_performed == false and .anchor_verification_performed == false and .compliance_certification == false' "${out}" >/dev/null
done

echo ""
echo "=== check: proofbundle verifier validation JSON ==="
jq empty "${ROOT}/docs/validation/p3_1_cli_proofbundle_verifier_report.json"

echo ""
echo "=== check: proofbundle verifier claim scan ==="
ROOT="${ROOT}" python3 <<'PYEOF'
from __future__ import annotations

import os
import re
from pathlib import Path

root = Path(os.environ["ROOT"])
paths = [
    root / "docs/usage/cli_proofbundle_verifier_alpha.md",
    root / "docs/validation/p3_1_cli_proofbundle_verifier_report.md",
    root / "docs/validation/p3_1_cli_proofbundle_verifier_report.json",
    root / "sdk/python/src/attestplane/cli/proofbundle_alpha.py",
    root / "sdk/python/src/attestplane/cli/main.py",
]
phrases = [
    "production-ready",
    "compliance-ready",
    "certification-ready",
    "certified provenance",
    "SLSA L3",
    "production-grade",
    "full CLI ProofBundle verification",
    "default signed verification",
    "default anchored verification",
]
allowed_markers = (
    "not ",
    "no ",
    "does not ",
    "must not ",
    "without ",
    "no-go",
    "not-in-scope",
    "not in scope",
)
violations: list[str] = []
for path in paths:
    text = path.read_text(encoding="utf-8")
    for line_no, line in enumerate(text.splitlines(), start=1):
        lower = line.lower()
        for phrase in phrases:
            if phrase.lower() not in lower:
                continue
            window = lower[max(0, lower.find(phrase.lower()) - 40):]
            if any(marker in window for marker in allowed_markers):
                continue
            violations.append(f"{path.relative_to(root)}:{line_no}: {line}")
if violations:
    print("::error::positive over-claim wording found")
    for violation in violations:
        print(f"  {violation}")
    raise SystemExit(1)
PYEOF

echo "alpha ProofBundle verifier gate: PASS"
