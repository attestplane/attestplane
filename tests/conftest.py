# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Top-level test import setup for repository-local SDK tests."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SDK_SRC = REPO_ROOT / "sdk" / "python" / "src"

for path in (REPO_ROOT, SDK_SRC):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)
