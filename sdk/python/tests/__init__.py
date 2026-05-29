# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
from pathlib import Path

_TESTS_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _TESTS_ROOT / "src"
_REPO_ROOT = Path(__file__).resolve().parents[3]
for path in (str(_REPO_ROOT), str(_SRC_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)
