# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Repository-root import shim for local ``python -m attestplane...`` commands."""

from __future__ import annotations

from pathlib import Path

_SDK_PACKAGE = (
    Path(__file__).resolve().parents[1] / "sdk" / "python" / "src" / "attestplane"
)
__path__.insert(0, str(_SDK_PACKAGE))  # type: ignore[name-defined]

_SDK_INIT = _SDK_PACKAGE / "__init__.py"
exec(compile(_SDK_INIT.read_text(encoding="utf-8"), str(_SDK_INIT), "exec"))  # noqa: S102
