<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Issue 73 Validation Evidence

Plan ID: `fe23fa36d63771bf`

## Required Commands

### Required Pytest Command

Command:

```bash
sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'release_gate or stable_auto_train' -x
```

Result: blocked in this lane environment.

Exit code: `1`

Output:

```text
/opt/homebrew/opt/python@3.14/bin/python3.14: No module named pytest
```

### uv Fallback Attempt

Command:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache uv run --directory sdk/python pytest tests -k 'release_gate or stable_auto_train' -x
```

Result: blocked by restricted network/cache access while resolving build and wheel
dependencies.

Exit code: `2`

Relevant output:

```text
Failed to download `uuid-utils==0.16.0`
Failed to fetch `https://files.pythonhosted.org/.../uuid_utils-0.16.0-...whl`
```

### Whitespace Check

Command:

```bash
git diff --check
```

Result: pass.

Exit code: `0`

Output: no output.

## Focused Direct Verification

Command:

```bash
python3 - <<'PY'
...direct assertion script for release_gate.classify_product_delta and
stable_auto_train.commits_since_tag_have_real_work...
PY
```

Result: pass.

Exit code: `0`

Output:

```text
{
  "release_gate_product_support_files": [
    "sdk/python/tests/test_import_surface.py",
    "sdk/python/tests/test_release_gate.py"
  ],
  "release_gate_reason": "product_support_delta",
  "release_gate_support_only_count": 23,
  "stable_auto_train_subject_count": 7
}
```

No regression was weakened to manufacture a pass.
