# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Minimal PyYAML stub for mypy in the optional signing path."""

from typing import Any

class YAMLError(Exception): ...


def safe_load(stream: str | bytes | Any) -> Any: ...
