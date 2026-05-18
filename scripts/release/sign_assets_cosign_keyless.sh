#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

execute=false
require_cosign=false
files=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    --execute)
      execute=true
      shift
      ;;
    --require-cosign)
      require_cosign=true
      shift
      ;;
    --)
      shift
      while [ "$#" -gt 0 ]; do
        files+=("$1")
        shift
      done
      ;;
    -*)
      echo "unknown option: $1" >&2
      exit 2
      ;;
    *)
      files+=("$1")
      shift
      ;;
  esac
done

if [ "${#files[@]}" -eq 0 ]; then
  echo "usage: $0 [--execute] [--require-cosign] <artifact>..." >&2
  exit 2
fi

if ! command -v cosign >/dev/null 2>&1; then
  if [ "$require_cosign" = true ]; then
    echo "cosign is required but not installed" >&2
    exit 1
  fi
  echo "cosign unavailable; keyless signing dry-run skipped"
  exit 0
fi

if [ "$execute" != true ]; then
  echo "DRY-RUN: would keyless sign ${#files[@]} artifact(s) with cosign sign-blob"
  printf '  %s\n' "${files[@]}"
  exit 0
fi

if [ "${CI:-}" != "true" ] && [ "${ATTESTPLANE_ALLOW_LOCAL_SIGN:-}" != "1" ]; then
  echo "refusing local execute mode without ATTESTPLANE_ALLOW_LOCAL_SIGN=1" >&2
  exit 1
fi

export COSIGN_YES=true
for file in "${files[@]}"; do
  if [ ! -f "$file" ]; then
    echo "artifact not found: $file" >&2
    exit 1
  fi
  cosign sign-blob \
    --bundle "${file}.cosign.bundle" \
    --output-signature "${file}.sig" \
    --output-certificate "${file}.pem" \
    "$file"
done
