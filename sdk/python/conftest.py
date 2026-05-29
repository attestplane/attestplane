# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Pytest bootstrap for the in-tree Python SDK.

The test suite runs directly from ``sdk/python`` without an editable install,
so add ``src`` to ``sys.path`` before collection starts.
"""

from __future__ import annotations

import sys
from pathlib import Path


SDK_ROOT = Path(__file__).resolve().parent
SRC = SDK_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
