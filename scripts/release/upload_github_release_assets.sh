#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

execute=false
clobber=false
tag=""
files=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    --execute)
      execute=true
      shift
      ;;
    --clobber)
      clobber=true
      shift
      ;;
    --tag)
      tag="${2:-}"
      shift 2
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

if [ -z "$tag" ] || [ "${#files[@]}" -eq 0 ]; then
  echo "usage: $0 --tag <release-tag> [--execute] [--clobber] <asset>..." >&2
  exit 2
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "gh unavailable; GitHub Release asset upload skipped"
  exit 0
fi

upload_args=(release upload "$tag")
if [ "$clobber" = true ]; then
  upload_args+=(--clobber)
fi
upload_args+=("${files[@]}")

if [ "$execute" != true ]; then
  echo "DRY-RUN: would run gh ${upload_args[*]}"
  exit 0
fi

gh auth status >/dev/null
gh "${upload_args[@]}"
