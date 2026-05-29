# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Test-path bootstrap for the sdk/python suite.

Pytest runs this suite from ``sdk/python`` without an installed wheel, so
the package source tree needs to be on ``sys.path`` for direct imports.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
