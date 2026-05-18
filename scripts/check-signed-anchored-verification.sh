#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
#
# P3.2 signed / anchored verification gate.
#
# Exercises the alpha extension interface (--verify-signature / --verify-anchor)
# fail-closed paths end-to-end:
#   * unit tests under sdk/python/tests/cli/test_proofbundle_alpha.py
#   * CLI smoke for each new fixture under tests/fixtures/proofbundle/
#   * stdout JSON validity via jq
#   * claim scan ensures no production/compliance/certification-ready
#     positive claim leaked into the report
#
# The gate is fail-closed:
# * unit-test failure → exit 1
# * CLI exit code mismatch → exit 1
# * stdout not parseable as JSON → exit 1
# * claim scan finds banned positive claim → exit 1
#
# This gate does NOT perform cryptographic signature verification or
# RFC-3161 anchor verification. Those are out of scope for P3.2; see
# docs/validation/p3_2_signed_anchored_verification_report.md.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"

py="${PYTHON:-sdk/python/.venv/bin/python}"
if [ ! -x "$py" ]; then
  echo "::error::python venv missing at $py — run 'uv pip install -e sdk/python[dev]' first" >&2
  exit 1
fi

echo "=== P3.2 unit tests (signature + anchor extensions) ==="
"$py" -m pytest sdk/python/tests/cli/test_proofbundle_alpha.py -q --no-cov

echo ""
echo "=== P3.2 CLI smoke matrix ==="
fix_dir="tests/fixtures/proofbundle"

# Each row: <fixture> <flags> <expected_exit>
# Flags are space-separated; pass empty string for none.
declare -a CASES=(
  "valid_minimal.json|0"
  "valid_minimal.json|--verify-signature|2"
  "valid_minimal.json|--verify-anchor|2"
  "signature_shape_valid_but_not_requested.json|0"
  "signature_shape_valid_but_not_requested.json|--verify-signature|2"
  "missing_signature_material.json|--verify-signature|2"
  "tampered_dsse_signature.json|--verify-signature|2"
  "unsupported_signature_algorithm.json|--verify-signature|2"
  "anchor_shape_valid_but_not_requested.json|0"
  "anchor_shape_valid_but_not_requested.json|--verify-anchor|2"
  "missing_anchor_material.json|--verify-anchor|2"
  "expired_tsa_timestamp.json|--verify-anchor|2"
  "invalid_anchor_chain.json|--verify-anchor|2"
  "unsupported_anchor_type.json|--verify-anchor|2"
  "signature_and_anchor_requested_missing_material.json|--verify-signature --verify-anchor|2"
)

failures=0
for case in "${CASES[@]}"; do
  IFS='|' read -r fixture flags_or_exit expected_exit <<< "$case"
  if [ -z "${expected_exit:-}" ]; then
    expected_exit="$flags_or_exit"
    flags=""
  else
    flags="$flags_or_exit"
  fi

  # shellcheck disable=SC2086
  rc=0
  out=$("$py" -m attestplane.cli.main verify-proofbundle "${fix_dir}/${fixture}" $flags 2>/dev/null) || rc=$?
  if [ "$rc" != "$expected_exit" ]; then
    echo "::error::FAIL ${fixture} flags=[$flags] expected_exit=${expected_exit} actual=${rc}" >&2
    failures=$((failures + 1))
    continue
  fi
  if ! echo "$out" | jq empty 2>/dev/null; then
    echo "::error::FAIL ${fixture} flags=[$flags] — stdout is not valid JSON" >&2
    failures=$((failures + 1))
    continue
  fi
  # Hard claim assertions: no positive certified/production/SLSA claim slipped in.
  bad=$(
    echo "$out" \
      | jq -r '. | tojson' \
      | grep -oE '"(certified_provenance|production_supply_chain_security|production_ready|compliance_certification|signature_verification_performed|anchor_verification_performed)":true' \
      || true
  )
  if [ -n "$bad" ]; then
    echo "::error::FAIL ${fixture} flags=[$flags] — banned positive claim in report: $bad" >&2
    failures=$((failures + 1))
    continue
  fi
  echo "  ok ${fixture} flags=[$flags] exit=${rc}"
done

echo ""
if [ "$failures" -gt 0 ]; then
  echo "::error::${failures} P3.2 CLI smoke case(s) failed" >&2
  exit 1
fi

echo "=== P3.2 validation JSON ==="
report_json="docs/validation/p3_2_signed_anchored_verification_report.json"
if [ ! -f "$report_json" ]; then
  echo "::error::${report_json} missing" >&2
  exit 1
fi
jq empty "$report_json"

echo ""
echo "=== P3.2 claim scan ==="
# Banned positive claims must not appear in the new P3.2 surfaces.
banned_files=(
  "docs/validation/p3_2_signed_anchored_verification_report.md"
  "docs/validation/p3_2_signed_anchored_verification_report.json"
  "docs/usage/cli_proofbundle_verifier_alpha.md"
  "sdk/python/src/attestplane/cli/proofbundle_alpha.py"
)
# Match real positive claims; whitelist "not X" / "no X" / negation contexts.
banned_pattern='\bproduction-ready\b|\bcompliance-ready\b|\bcertification-ready\b|\bcertified provenance\b|\bSLSA L3\b|\bproduction-grade supply-chain\b'
for f in "${banned_files[@]}"; do
  [ -f "$f" ] || continue
  # Strip any line that carries a negation/deferral/no-go context near the
  # banned token — those are honest disclaimers, not positive claims.
  hits=$(grep -niE "$banned_pattern" "$f" \
    | grep -ivE '\b(no|not|never|without|does not|is not|nor|negate|negation|deferred|preserved|disclaim|fail[- ]?closed|out of scope)\b' \
    | grep -ivE '\bnot[- ]?[a-z-]*(production-ready|compliance-ready|certification-ready|certified provenance|SLSA L3|production-grade supply-chain)\b' \
    | grep -ivE '"(certified_provenance|production_supply_chain_security|production_ready|compliance_certification)": *(false|null)' \
    || true)
  if [ -n "$hits" ]; then
    echo "::error::positive banned claim in $f:" >&2
    echo "$hits" >&2
    failures=$((failures + 1))
  fi
done

if [ "$failures" -gt 0 ]; then
  echo "::error::${failures} claim scan violation(s)" >&2
  exit 1
fi

echo "=== git diff --check ==="
git diff --check

echo ""
echo "P3.2 signed-anchored verification gate: PASS"
