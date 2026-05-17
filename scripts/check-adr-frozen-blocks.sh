#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
#
# ADR frozen-block gate (T0 invariant).
#
# Locks the `## Decision` section of every Accepted ADR — from the `## Decision`
# heading up to (but excluding) the next H2 heading or EOF. The section content
# is canonicalised (trailing whitespace trimmed, single trailing newline) before
# hashing. This is the contract: Accepted ADR Decisions are governance assets
# and may not drift silently. Editing one is allowed but requires:
#   1. an explicit ADR-0000-template supersession / amendment record, OR
#   2. an updated SHA in docs/adr/.frozen-blocks.lock that the founder signed off
#
# Usage:
#   ./scripts/check-adr-frozen-blocks.sh           # verify
#   ./scripts/check-adr-frozen-blocks.sh --update  # rewrite lock
set -uo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
adr_dir="${repo_root}/docs/adr"
lock_file="${adr_dir}/.frozen-blocks.lock"
mode="${1:-verify}"

current_hashes() {
  AP_ADR_DIR="$adr_dir" python3 - <<'PYEOF'
import hashlib
import os
import re

adr_dir = os.environ["AP_ADR_DIR"]
H2 = re.compile(r"^## (.+)$")
DECISION = re.compile(r"^## Decision\s*$")

results = []
for fn in sorted(os.listdir(adr_dir)):
    if not (fn.endswith(".md") and fn[:4].isdigit() and fn != "0000-template.md"):
        continue
    path = os.path.join(adr_dir, fn)
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()

    # Only lock ADRs marked Accepted.
    head_blob = "".join(lines[:30])
    if "Status**: Accepted" not in head_blob:
        continue

    start = None
    end = len(lines)
    for i, ln in enumerate(lines):
        if start is None:
            if DECISION.match(ln):
                start = i + 1
        else:
            if H2.match(ln):
                end = i
                break
    if start is None:
        # Accepted ADR with no Decision section — flag, do not silently skip.
        results.append((fn, "NO_DECISION_SECTION"))
        continue

    section = "".join(lines[start:end])
    # Canonicalise: strip trailing whitespace per line + single trailing newline.
    canon = "\n".join(line.rstrip() for line in section.splitlines()) + "\n"
    h = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    results.append((fn, h))

for fn, h in results:
    print(f"{h}  {fn}")
PYEOF
}

if [ "$mode" = "--update" ]; then
  {
    if [ -f "$lock_file" ]; then
      awk '/^[^#]/ && NF { exit } { print }' "$lock_file"
    else
      cat <<'HDR'
# ADR frozen-block hash lock
#
# Locks the `## Decision` section of every Accepted ADR. Recompute with:
#   ./scripts/check-adr-frozen-blocks.sh --update
# Verify with:
#   ./scripts/check-adr-frozen-blocks.sh
#
# Editing an Accepted ADR Decision is governance-level. The PR must either
# supersede the ADR (per ADR-0000-template) or carry founder sign-off in the
# commit message, AND update this lock in the same commit.
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
  echo "ADR frozen-blocks: ${count} Accepted ADR Decision sections match ✓"
  exit 0
fi

echo "::error::ADR frozen-block drift detected." >&2
echo "" >&2
echo "Expected (from docs/adr/.frozen-blocks.lock):" >&2
echo "$expected" >&2
echo "" >&2
echo "Actual (computed now):" >&2
echo "$actual" >&2
echo "" >&2
echo "Diff:" >&2
diff <(echo "$expected") <(echo "$actual") >&2 || true
echo "" >&2
echo "If this drift is intentional:" >&2
echo "  1. Either supersede the ADR (per ADR-0000-template) or amend it with founder sign-off" >&2
echo "  2. Run ./scripts/check-adr-frozen-blocks.sh --update" >&2
echo "  3. Commit the ADR edit + new lock together" >&2
exit 1
