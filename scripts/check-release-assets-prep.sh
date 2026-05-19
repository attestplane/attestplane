#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
#
# Local release-candidate asset gate.
#
# This script builds local Python and npm artifacts, verifies their checksums
# against a prepared manifest, and checks release-claim hygiene. It never tags,
# publishes, uploads, dispatches workflows, or mutates a GitHub Release.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"

release_version="${RELEASE_VERSION:-v0.0.5-alpha}"
python_version="${PYTHON_VERSION:-0.0.5a0}"
npm_version="${NPM_VERSION:-0.0.5-alpha}"
py="${PYTHON:-sdk/python/.venv/bin/python}"

manifest="release/artifacts/${release_version}/artifact-manifest.json"
checksums="release/artifacts/${release_version}/checksums.sha256"
upload_plan="release/artifacts/${release_version}/upload-plan.md"

[ -x "$py" ] || { echo "::error::python venv missing at $py" >&2; exit 1; }
[ -f "$manifest" ] || { echo "::error::missing $manifest" >&2; exit 1; }
[ -f "$checksums" ] || { echo "::error::missing $checksums" >&2; exit 1; }
[ -f "$upload_plan" ] || { echo "::error::missing $upload_plan" >&2; exit 1; }

echo "=== build Python wheel + sdist (${python_version}) ==="
(
  cd sdk/python
  rm -rf dist build
  "$repo_root/$py" -m build >/dev/null
  "$repo_root/$py" -m twine check dist/*
)

echo ""
echo "=== build npm tarball (${npm_version}) ==="
(
  cd sdk/typescript
  find . -maxdepth 1 -name '*.tgz' -delete
  npm ci --silent >/dev/null
  npm run build --silent >/dev/null
  npm test --silent >/dev/null
  npm pack --silent >/dev/null
)

py_whl="sdk/python/dist/attestplane-${python_version}-py3-none-any.whl"
py_sdist="sdk/python/dist/attestplane-${python_version}.tar.gz"
npm_tgz="sdk/typescript/attestplane-attestplane-${npm_version}.tgz"

for f in "$py_whl" "$py_sdist" "$npm_tgz"; do
  [ -f "$f" ] || { echo "::error::expected artifact missing: $f" >&2; exit 1; }
done

echo ""
echo "=== hygiene scan ==="
forbidden_re='\.env(\s|$)|credentials?|\btoken\b|\bsecret\b|node_modules|__pycache__|\.DS_Store|/\.git/|/\.git$|private[._]key|id_rsa|id_ed25519|pypirc|\.npmrc'
hygiene_failures=0
"$repo_root/$py" -m tarfile -l "$py_sdist" > /tmp/_attestplane_release_sdist.txt
"$repo_root/$py" -m zipfile -l "$py_whl" > /tmp/_attestplane_release_whl.txt
tar -tf "$npm_tgz" > /tmp/_attestplane_release_tgz.txt
for f in /tmp/_attestplane_release_sdist.txt /tmp/_attestplane_release_whl.txt /tmp/_attestplane_release_tgz.txt; do
  hits=$(grep -iE "$forbidden_re" "$f" || true)
  if [ -n "$hits" ]; then
    echo "::error::forbidden patterns in $f:" >&2
    echo "$hits" >&2
    hygiene_failures=$((hygiene_failures + 1))
  fi
done
[ "$hygiene_failures" -eq 0 ] || { echo "::error::hygiene scan failed" >&2; exit 1; }
echo "  hygiene scan: clean"

echo ""
echo "=== sha256 verification ==="
expected_whl=$(jq -r '.artifacts[] | select(.kind=="python-wheel") | .sha256' "$manifest")
expected_sdist=$(jq -r '.artifacts[] | select(.kind=="python-sdist") | .sha256' "$manifest")
expected_npm=$(jq -r '.artifacts[] | select(.kind=="npm-tarball") | .sha256' "$manifest")
actual_whl=$(shasum -a 256 "$py_whl" | awk '{print $1}')
actual_sdist=$(shasum -a 256 "$py_sdist" | awk '{print $1}')
actual_npm=$(shasum -a 256 "$npm_tgz" | awk '{print $1}')

sha_failures=0
for pair in "wheel:$expected_whl:$actual_whl" "sdist:$expected_sdist:$actual_sdist" "npm:$expected_npm:$actual_npm"; do
  IFS=':' read -r kind exp act <<< "$pair"
  if [ "$exp" != "$act" ]; then
    echo "::error::${kind} sha256 mismatch: manifest=$exp actual=$act" >&2
    sha_failures=$((sha_failures + 1))
  else
    echo "  $kind sha256 match: $act"
  fi
done

while read -r line; do
  case "$line" in
    \#*|"") continue ;;
  esac
  sha=$(echo "$line" | awk '{print $1}')
  path=$(echo "$line" | awk '{$1=""; sub(/^ +/, ""); print}')
  [ -n "$sha" ] && [ -n "$path" ] || continue
  if [ ! -f "$path" ]; then
    echo "::error::checksums.sha256 references missing file: $path" >&2
    sha_failures=$((sha_failures + 1))
    continue
  fi
  act=$(shasum -a 256 "$path" | awk '{print $1}')
  if [ "$sha" != "$act" ]; then
    echo "::error::checksums.sha256 line mismatch for $path: declared=$sha actual=$act" >&2
    sha_failures=$((sha_failures + 1))
  fi
done < "$checksums"
[ "$sha_failures" -eq 0 ] || exit 1
echo "  checksums.sha256: all lines verified"

echo ""
echo "=== claim scan ==="
banned_re='\bproduction-ready\b|\bcompliance-ready\b|\bcertification-ready\b|\bcertified provenance\b|\bSLSA L3\b|\bproduction-grade supply-chain\b'
banned_files=("$manifest" "$upload_plan")
claim_violations=0
for f in "${banned_files[@]}"; do
  hits=$(grep -niE "$banned_re" "$f" \
    | grep -ivE '\b(no|not|never|without|does not|is not|nor|negate|negation|deferred|preserved|disclaim|fail[- ]?closed|out of scope|non-claim|non-claims)\b' \
    || true)
  if [ -n "$hits" ]; then
    echo "::error::positive banned claim in $f:" >&2
    echo "$hits" >&2
    claim_violations=$((claim_violations + 1))
  fi
done
[ "$claim_violations" -eq 0 ] || exit 1
echo "  claim scan: clean"

echo ""
echo "=== JSON and diff validation ==="
jq empty "$manifest"
git diff --check

echo ""
echo "${release_version} release-asset prep gate: PASS"
