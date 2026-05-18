#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
#
# Conformance fixture hash gate (T1 invariant — Gap G7).
#
# Locks every sdk/python/tests/conformance/*_vectors.json and vectors.json
# by canonical-JSON SHA-256. Fixtures are the cross-SDK contract: the TS SDK
# replays them byte-for-byte (see sdk/typescript/test/conformance.test.ts
# and siblings). Silent edits would cause TS to silently accept new bytes
# without anyone noticing the contract changed.
#
# Complements existing sdk/python conformance-vectors-frozen job (which
# regenerates vectors.json from the Python generator and compares).
# That job proves the *generator* still reproduces vectors.json; this
# gate proves *no fixture file was edited* without recording the change.
#
# Usage:
#   ./scripts/check-fixture-hashes.sh           # verify
#   ./scripts/check-fixture-hashes.sh --update  # rewrite lock from current state
set -uo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
lock_file="${repo_root}/sdk/python/tests/conformance/FIXTURE_HASHES.lock"
fix_dir="${repo_root}/sdk/python/tests/conformance"

mode="${1:-verify}"

current_hashes() {
  AP_FIX_DIR="$fix_dir" python3 - <<'PYEOF'
import hashlib
import json
import os

fix_dir = os.environ["AP_FIX_DIR"]
files = sorted(f for f in os.listdir(fix_dir) if f.endswith(".json"))
for fn in files:
    with open(os.path.join(fix_dir, fn), encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"::error::{fn} is not valid JSON: {exc}") from exc
    canon = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    h = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    print(f"{h}  {fn}")
PYEOF
}

if [ "$mode" = "--update" ]; then
  {
    if [ -f "$lock_file" ]; then
      awk '/^[^#]/ && NF { exit } { print }' "$lock_file"
    else
      cat <<'HDR'
# Conformance fixture hash lock (Gap G7).
#
# Canonical-JSON SHA-256 of every sdk/python/tests/conformance/*.json
# fixture. Fixtures are the cross-SDK contract — TS replays them
# byte-for-byte. Recompute with:
#   ./scripts/check-fixture-hashes.sh --update
# Verify with:
#   ./scripts/check-fixture-hashes.sh
#
# Editing a fixture is a deliberate cross-SDK conformance event. The PR
# must bump the affected fixture's $schema_version (and the matching
# generator if one exists), and update this lock in the same commit.
#
# Format: <sha256>  <filename>
#

HDR
    fi
    current_hashes
  } > "${lock_file}.tmp"
  mv "${lock_file}.tmp" "$lock_file"
  echo "Updated ${lock_file}"
  exit 0
fi

if [ ! -f "$lock_file" ]; then
  echo "::error::${lock_file} missing. Run --update on first install." >&2
  exit 1
fi

expected="$(grep -v '^[[:space:]]*#' "$lock_file" | grep -v '^[[:space:]]*$' | sort)"
actual="$(current_hashes | sort)"

if [ "$expected" = "$actual" ]; then
  count="$(echo "$actual" | wc -l | tr -d ' ')"
  echo "Conformance fixtures: ${count} files, all canonical hashes match ✓"
  exit 0
fi

echo "::error::Conformance fixture drift detected." >&2
echo "" >&2
echo "Expected (from sdk/python/tests/conformance/FIXTURE_HASHES.lock):" >&2
echo "$expected" >&2
echo "" >&2
echo "Actual (computed now):" >&2
echo "$actual" >&2
echo "" >&2
echo "Diff:" >&2
diff <(echo "$expected") <(echo "$actual") >&2 || true
echo "" >&2
echo "If this drift is intentional:" >&2
echo "  1. Bump the affected fixture's \$schema_version" >&2
echo "  2. Update the generator (if applicable, e.g. tests/conformance/generate_vectors.py)" >&2
echo "  3. Run ./scripts/check-fixture-hashes.sh --update" >&2
echo "  4. Commit the fixture edit + new lock together" >&2
echo "  5. Reference the originating ADR in the PR description (ADR-0008/0009/0010/0011/0012)" >&2
exit 1
