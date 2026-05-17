#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
#
# AP-EVD/1.0 schema hash gate (T0 invariant).
#
# Verifies every schemas/v1/*.schema.json against schemas/v1/SCHEMA_HASHES.lock
# using canonical-JSON SHA-256 (sort_keys=True, separators=(',',':'), no BOM).
#
# Canonical-form awareness: pure-formatting edits do not trip the gate; semantic
# edits do. Bumping a hash is a deliberate ADR-0014 v2 §9 protocol decision and
# MUST be paired with a $schema_version bump in the affected file.
#
# Usage:
#   ./scripts/check-schema-hashes.sh           # verify (CI default)
#   ./scripts/check-schema-hashes.sh --update  # rewrite SCHEMA_HASHES.lock from current files
set -uo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
lock_file="${repo_root}/schemas/v1/SCHEMA_HASHES.lock"
schema_dir="${repo_root}/schemas/v1"

mode="${1:-verify}"

current_hashes() {
  AP_SCHEMA_DIR="$schema_dir" python3 - <<'PYEOF'
import hashlib
import json
import os

schema_dir = os.environ["AP_SCHEMA_DIR"]
files = sorted(f for f in os.listdir(schema_dir) if f.endswith(".schema.json"))
for fn in files:
    with open(os.path.join(schema_dir, fn), encoding="utf-8") as fh:
        canon = json.dumps(
            json.load(fh),
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
    # Preserve the original header (everything up to and including the blank
    # comment line right before the hash list).
    awk '/^[^#]/ && NF { exit } { print }' "$lock_file"
    current_hashes
  } > "${lock_file}.tmp"
  mv "${lock_file}.tmp" "$lock_file"
  echo "Updated ${lock_file}"
  exit 0
fi

# Verify mode.
expected="$(grep -v '^[[:space:]]*#' "$lock_file" | grep -v '^[[:space:]]*$' | sort)"
actual="$(current_hashes | sort)"

if [ "$expected" = "$actual" ]; then
  echo "AP-EVD/1.0 schemas: 8 files, all canonical hashes match ✓"
  exit 0
fi

echo "::error::AP-EVD/1.0 schema hash drift detected." >&2
echo "" >&2
echo "Expected (from schemas/v1/SCHEMA_HASHES.lock):" >&2
echo "$expected" >&2
echo "" >&2
echo "Actual (computed now):" >&2
echo "$actual" >&2
echo "" >&2
echo "Diff:" >&2
diff <(echo "$expected") <(echo "$actual") >&2 || true
echo "" >&2
echo "If this drift is intentional:" >&2
echo "  1. Bump the affected file's \$schema_version (or anchor_schema_version / signature_schema_version)" >&2
echo "  2. Run ./scripts/check-schema-hashes.sh --update" >&2
echo "  3. Commit both the schema edit and the new SCHEMA_HASHES.lock together" >&2
echo "  4. Reference the relevant ADR (typically ADR-0014 v2 §9) in the PR description" >&2
exit 1
