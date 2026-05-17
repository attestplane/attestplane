#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
# Project policy invariants. Run by CI; safe to run locally too.
set -uo pipefail

fail=0

echo "=== check: registered-mark symbol restricted to NOTICE and TRADEMARK.md ==="
# Until USPTO + EUIPO registration confirms, the ® symbol may only appear in
# NOTICE and TRADEMARK.md (and only there as policy-explanation text).
# In every other doc, marks must use the ™ symbol.
allowed_files=("NOTICE" "TRADEMARK.md")
while IFS= read -r -d '' f; do
  basename_f=$(basename "$f")
  is_allowed=false
  for allow in "${allowed_files[@]}"; do
    if [ "$basename_f" = "$allow" ]; then is_allowed=true; break; fi
  done
  if [ "$is_allowed" = false ] && grep -q '®' "$f"; then
    echo "::error file=${f}::contains ® symbol; should be ™ until USPTO/EUIPO registration confirmed (see TRADEMARK.md section 6)"
    grep -n '®' "$f" | sed 's/^/    /'
    fail=1
  fi
done < <(find . -maxdepth 2 -type f \( -name '*.md' -o -name 'NOTICE' -o -name 'LICENSE' -o -name 'DCO.txt' \) -not -path './.git/*' -print0)

echo ""
echo "=== check: Cyrillic homoglyphs in latin-script content ==="
python3 <<'PYEOF'
import os, sys
_SKIP_DIRS = {'.git', 'node_modules', 'dist', '.venv', 'venv',
              '.mypy_cache', '.ruff_cache', '.pytest_cache',
              '__pycache__', 'htmlcov', '.coverage'}
issues = []
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
    for fn in files:
        if not (fn.endswith(('.md', '.txt', '.yml', '.yaml', '.jsonc', '.json', '.toml', '.sh'))
                or fn in ('LICENSE', 'NOTICE')):
            continue
        path = os.path.join(root, fn)
        try:
            with open(path, 'rb') as fh:
                data = fh.read()
        except Exception:
            continue
        for utf8, name, codepoint in [
            (b'\xd0\xb0', 'a', 'U+0430'),
            (b'\xd0\xb5', 'e', 'U+0435'),
            (b'\xd0\xbe', 'o', 'U+043E'),
            (b'\xd1\x80', 'p', 'U+0440'),
            (b'\xd1\x81', 'c', 'U+0441'),
            (b'\xd1\x85', 'x', 'U+0445'),
        ]:
            n = data.count(utf8)
            if n:
                issues.append((path, name, codepoint, n))
if issues:
    print("::error::Cyrillic homoglyphs found (look identical to Latin letters):")
    for path, name, cp, n in issues:
        print(f"  {path}: Cyrillic '{name}' ({cp}) x{n}")
    sys.exit(1)
PYEOF
if [ $? -ne 0 ]; then fail=1; fi

echo ""
echo "=== check: cross-file markdown references resolve ==="
for f in *.md; do
  [ -f "$f" ] || continue
  refs=$(grep -oE '\]\(([A-Za-z_./-]+\.(md|txt|yml|yaml)|LICENSE|NOTICE)(#[^)]*)?\)' "$f" || true)
  while IFS= read -r ref; do
    [ -z "$ref" ] && continue
    ref_clean=$(printf '%s' "$ref" | sed -E 's/^\]\(([^)#]+).*$/\1/')
    [ -z "$ref_clean" ] && continue
    if [[ "$ref_clean" =~ ^(http|mailto:|/|\#) ]]; then continue; fi
    if [ ! -e "$ref_clean" ]; then
      echo "::error file=${f}::references non-existent path: ${ref_clean}"
      fail=1
    fi
  done <<<"$refs"
done

echo ""
echo "=== check: entity in-formation date present on key documents ==="
required_date_files=("NOTICE" "TRADEMARK.md" "GOVERNANCE.md" "SECURITY.md")
for f in "${required_date_files[@]}"; do
  if [ -f "$f" ]; then
    if ! grep -q 'in formation as of 2026-05-17' "$f"; then
      echo "::warning file=${f}::does not mention 'in formation as of 2026-05-17'; check whether entity descriptor is consistent"
    fi
  fi
done

echo ""
echo "=== check: NOTICE follows Apache convention ==="
if [ -f NOTICE ]; then
  if ! grep -q 'This product includes software' NOTICE; then
    echo "::warning file=NOTICE::missing canonical Apache 'This product includes software developed by' attribution line"
  fi
fi

echo ""
echo "=== check: CONTRIBUTING.md describes DCO (not CLA) ==="
if [ -f CONTRIBUTING.md ]; then
  if grep -qi 'contributor license agreement\|signed CLA\|授权给 .* 公司\|版权转让' CONTRIBUTING.md; then
    echo "::error file=CONTRIBUTING.md::contains language consistent with CLA, not DCO; project policy is DCO-only (see GOVERNANCE.md)"
    fail=1
  fi
fi

echo ""
echo "=== check: INV-NEW-1 (ADR-0009) — schemas/v1 \$id discipline ==="
# Every JSON Schema under schemas/v1/ MUST have $id starting with
# https://attestplane.io/schemas/v1/ — never https://aios.dev/.
if [ -d schemas/v1 ]; then
  while IFS= read -r -d '' f; do
    id_line=$(grep -E '"\$id"\s*:' "$f" | head -1 || true)
    if [ -z "$id_line" ]; then
      echo "::error file=${f}::INV-NEW-1: schema missing \"\$id\" field"
      fail=1
      continue
    fi
    if ! echo "$id_line" | grep -q '"https://attestplane.io/schemas/v1/'; then
      echo "::error file=${f}::INV-NEW-1: \$id must start with https://attestplane.io/schemas/v1/ (ADR-0009 § 3 invariant 13)"
      echo "    got: ${id_line}"
      fail=1
    fi
    if echo "$id_line" | grep -q 'aios\.dev'; then
      echo "::error file=${f}::INV-NEW-1: \$id MUST NOT reference aios.dev (ADR-0009 § 3 invariant 13)"
      fail=1
    fi
  done < <(find schemas/v1 -type f -name '*.schema.json' -print0)
fi

echo ""
echo "=== check: INV-NEW-3 (ADR-0009) — no AIOS Rust crate names in sdk/ ==="
# Attestplane sdk/ must not reference AIOS crate names. The docstring-only stub
# at sdk/python/src/attestplane/adapters/aios_spec.py is the single permitted
# exception per ADR-0004 § 4.
if [ -d sdk ]; then
  pattern='\b(aios_sdk_evidence|aios_sdk_protocol|aios_canonical|aios_audit|aios_cp|aios_runtime|aios_protocol)\b'
  hits=$(grep -rnE "$pattern" sdk/ \
    --include='*.py' --include='*.ts' --include='*.toml' \
    2>/dev/null \
    | grep -v 'sdk/python/src/attestplane/adapters/aios_spec.py' \
    || true)
  if [ -n "$hits" ]; then
    echo "::error::INV-NEW-3: AIOS Rust crate names found in sdk/ (ADR-0009 § 3 invariant 15)"
    echo "$hits" | sed 's/^/    /'
    fail=1
  fi
fi

echo ""
echo "=== check: INV-NEW-3b (ADR-0009 C.18/C.19) — no AIOS-named example or adapter impl ==="
# Migration-plan #5 (AIOSAdapter concrete impl) and #24 (aios_run_to_proof_bundle example)
# are permanently out of scope per memory/feedback_attestplane_aios_boundary.md.
# Detect: any file under examples/ or sdk/ named *aios* (other than the docstring-only stub).
hits=$(find examples sdk -type f \( -name '*aios*' -o -name '*AIOS*' \) 2>/dev/null \
  | grep -vE '__pycache__|\.pyc$|node_modules|dist/' \
  | grep -v 'sdk/python/src/attestplane/adapters/aios_spec.py' \
  | grep -v 'aios_to_attestplane_migration_plan' \
  || true)
if [ -n "$hits" ]; then
  echo "::error::INV-NEW-3b: AIOS-named files found in examples/ or sdk/ (ADR-0009 C.18/C.19; migration tickets #5 + #24 are out of scope)"
  echo "$hits" | sed 's/^/    /'
  fail=1
fi

echo ""
echo "=== check: INV-NEW-4 (ADR-0009) — proof-type allowlist on adapter ingress ==="
# Adapters that reference AIOS-side ProofType values MUST drop authority-flavoured
# variants (LiveRuntimeInvariant / ProductionLive). This check looks for these
# variant names appearing anywhere in sdk/, which would indicate a leak.
if [ -d sdk ]; then
  hits=$(grep -rnE '\b(LiveRuntimeInvariant|ProductionLive)\b' sdk/ \
    --include='*.py' --include='*.ts' \
    2>/dev/null || true)
  if [ -n "$hits" ]; then
    echo "::error::INV-NEW-4: authority-flavoured ProofType variants found in sdk/ (ADR-0009 § 3 invariant 16)"
    echo "$hits" | sed 's/^/    /'
    fail=1
  fi
fi

echo ""
if [ $fail -eq 1 ]; then
  echo "Policy invariant checks FAILED."
  exit 1
fi
echo "All policy invariant checks passed."
