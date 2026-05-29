<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Gate Report: PARTIAL

Gate: `local-direct-verification`

## Commands

- `sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'release_gate or stable_auto_train' -x`: exit=1, `No module named pytest`
- `UV_CACHE_DIR=/private/tmp/uv-cache uv run --directory sdk/python pytest tests -k 'release_gate or stable_auto_train' -x`: exit=2, dependency fetch blocked by restricted network/cache access
- `git diff --check`: exit=0
- `python3` direct assertion script for the changed release-gate and stable-train regressions: exit=0

## Status

The repository changes are verified by direct in-repo assertions, but the exact
project pytest command could not execute in this lane because the required
Python test dependencies were not available without network access.
