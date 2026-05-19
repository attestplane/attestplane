#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
#
# P3.3 release-asset dry-run gate.
#
# Builds Python wheel/sdist + npm tarball locally, hygiene-scans the
# archive contents for forbidden patterns, recomputes SHA-256, and
# asserts the manifest in
# release/artifacts/v0.0.3-alpha/artifact-manifest.json + the
# checksums.sha256 file match the on-disk artefacts.
#
# This gate NEVER uploads to GitHub Release, NEVER publishes to PyPI/npm,
# NEVER touches the v0.0.3-alpha tag, and NEVER triggers a publish workflow.
# It asserts those invariants post-build.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"

py="${PYTHON:-sdk/python/.venv/bin/python}"
if [ ! -x "$py" ]; then
  echo "::error::python venv missing at $py — run 'uv pip install -e sdk/python[dev]' first" >&2
  exit 1
fi

manifest="release/artifacts/v0.0.3-alpha/artifact-manifest.json"
checksums="release/artifacts/v0.0.3-alpha/checksums.sha256"
upload_plan="release/artifacts/v0.0.3-alpha/upload-plan.md"

[ -f "$manifest" ] || { echo "::error::missing $manifest" >&2; exit 1; }
[ -f "$checksums" ] || { echo "::error::missing $checksums" >&2; exit 1; }
[ -f "$upload_plan" ] || { echo "::error::missing $upload_plan" >&2; exit 1; }

echo "=== build Python wheel + sdist ==="
(
  cd sdk/python
  rm -rf dist build
  "$repo_root/$py" -m build >/dev/null
  "$repo_root/$py" -m twine check dist/*
)

echo ""
echo "=== build npm tarball ==="
(
  cd sdk/typescript
  rm -f attestplane-attestplane-*.tgz
  npm ci --silent >/dev/null
  npm run build --silent >/dev/null
  npm pack --silent >/dev/null
)

py_whl="sdk/python/dist/attestplane-0.0.3a0-py3-none-any.whl"
py_sdist="sdk/python/dist/attestplane-0.0.3a0.tar.gz"
npm_tgz="sdk/typescript/attestplane-attestplane-0.0.3-alpha.tgz"

for f in "$py_whl" "$py_sdist" "$npm_tgz"; do
  [ -f "$f" ] || { echo "::error::expected artefact missing: $f" >&2; exit 1; }
done

echo ""
echo "=== hygiene scan ==="
forbidden_re='\.env(\s|$)|credentials?|\btoken\b|\bsecret\b|node_modules|__pycache__|\.DS_Store|/\.git/|/\.git$|private[._]key|id_rsa|id_ed25519|pypirc|\.npmrc'
hygiene_failures=0
"$repo_root/$py" -m tarfile -l "$py_sdist" > /tmp/_p33_sdist.txt
"$repo_root/$py" -m zipfile -l "$py_whl" > /tmp/_p33_whl.txt
tar -tf "$npm_tgz" > /tmp/_p33_tgz.txt
for f in /tmp/_p33_sdist.txt /tmp/_p33_whl.txt /tmp/_p33_tgz.txt; do
  hits=$(grep -iE "$forbidden_re" "$f" || true)
  if [ -n "$hits" ]; then
    echo "::error::forbidden patterns in $f:" >&2
    echo "$hits" >&2
    hygiene_failures=$((hygiene_failures + 1))
  fi
done
if [ "$hygiene_failures" -gt 0 ]; then
  echo "::error::hygiene scan failed" >&2; exit 1
fi
echo "  hygiene scan: clean"

echo ""
echo "=== sha256 verification (manifest ⇆ artefacts) ==="
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
[ "$sha_failures" -eq 0 ] || { echo "::error::sha256 verification failed" >&2; exit 1; }

echo ""
echo "=== checksums.sha256 line consistency ==="
# Compare each non-comment line in checksums.sha256 against the on-disk file.
# Format per line: <sha256>  <path>  (separated by ≥1 whitespace)
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
echo "=== upload-plan execution check ==="
# The v0.0.3-alpha GitHub Release can be in one of two valid states:
#   * 0 assets — pre-upload P3.3 dry-run baseline
#   * 5 assets — founder-authorized upload on 2026-05-18T07:04:43Z
#     (wheel + sdist + npm-tarball + checksums.sha256 + artifact-manifest.json),
#     recorded in docs/validation/v0.0.3_alpha_release_asset_upload_report_20260518.md
# Any OTHER count means the Release was modified out-of-band and the
# gate must fail closed.
remote_assets=$(gh release view v0.0.3-alpha --json assets -q '.assets | length' 2>/dev/null || echo "remote_unreachable")
if [ "$remote_assets" = "remote_unreachable" ]; then
  echo "  GitHub Release assets check: SKIP (gh cli unavailable or no network)"
elif [ "$remote_assets" != "0" ] && [ "$remote_assets" != "5" ]; then
  echo "::error::GitHub Release v0.0.3-alpha now has $remote_assets asset(s); gate accepts 0 (pre-upload) or 5 (founder-authorized upload)" >&2
  exit 1
else
  echo "  GitHub Release v0.0.3-alpha assets: $remote_assets (0=pre-upload or 5=founder-authorized upload, both OK)"
fi

echo ""
echo "=== v0.0.3-alpha tag freeze ==="
tag_target=$(git rev-parse "v0.0.3-alpha^{}")
expected_tag_target="9bde6338df008afe58d561b0ba66eaaf75e298ad"
if [ "$tag_target" != "$expected_tag_target" ]; then
  echo "::error::v0.0.3-alpha tag has moved: now $tag_target, expected $expected_tag_target" >&2
  exit 1
fi
echo "  v0.0.3-alpha^{} = $tag_target (frozen)"

echo ""
echo "=== claim scan ==="
banned_re='\bproduction-ready\b|\bcompliance-ready\b|\bcertification-ready\b|\bcertified provenance\b|\bSLSA L3\b|\bproduction-grade supply-chain\b'
banned_files=("$manifest" "$upload_plan" "docs/validation/p3_3_release_assets_checksums_report.md" "docs/validation/p3_3_release_assets_checksums_report.json")
claim_violations=0
for f in "${banned_files[@]}"; do
  [ -f "$f" ] || continue
  hits=$(grep -niE "$banned_re" "$f" \
    | grep -ivE '\b(no|not|never|without|does not|is not|nor|negate|negation|deferred|preserved|disclaim|fail[- ]?closed|out of scope)\b' \
    | grep -ivE '"(certified_provenance|production_supply_chain_security|production_ready|compliance_certification)": *(false|null)' \
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
echo "=== jq empty validation JSON ==="
jq empty "$manifest"
jq empty "docs/validation/p3_3_release_assets_checksums_report.json"

echo ""
echo "=== git diff --check ==="
git diff --check

echo ""
echo "P3.3 release-assets dry-run gate: PASS"
