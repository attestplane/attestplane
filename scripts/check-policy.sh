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
issues = []
for root, dirs, files in os.walk('.'):
    if '.git' in dirs:
        dirs.remove('.git')
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
if [ $fail -eq 1 ]; then
  echo "Policy invariant checks FAILED."
  exit 1
fi
echo "All policy invariant checks passed."
