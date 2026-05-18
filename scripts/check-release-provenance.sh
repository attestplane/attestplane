#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python scripts/release/check_release_artifact_manifest.py release/artifacts/*.manifest.json

if [ -d release/artifacts/files ]; then
  mapfile -t files < <(find release/artifacts/files -type f | sort)
  if [ "${#files[@]}" -gt 0 ]; then
    python scripts/release/generate_checksums.py --base release/artifacts/files "${files[@]}" >/tmp/attestplane-release-checksums.json
    echo "Checksum dry-run PASS: ${#files[@]} file(s)"
  else
    echo "Checksum dry-run SKIP: release/artifacts/files exists but has no files"
  fi
else
  echo "Checksum dry-run SKIP: release/artifacts/files not present"
fi

echo "Release provenance gate PASS"
