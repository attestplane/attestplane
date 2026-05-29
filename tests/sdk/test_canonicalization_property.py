# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Compatibility selector for the canonicalization property suite."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "canonicalization"
    / "test_canonicalization_properties.py"
)
spec = importlib.util.spec_from_file_location(
    "attestplane_canonicalization_property_suite", SOURCE
)
if spec is None or spec.loader is None:
    raise RuntimeError(f"could not load canonicalization property suite from {SOURCE}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

for name, value in vars(module).items():
    if name.startswith("test_"):
        globals()[name] = value
