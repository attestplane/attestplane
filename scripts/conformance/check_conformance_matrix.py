#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Check the checked-in canonicalization negative coverage matrix."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _load_matrix_module(repo_root: Path):
    module_name = "attestplane_canonicalization_negative_matrix"
    helper_path = (
        repo_root / "tests" / "conformance" / "canonicalization_negative_matrix.py"
    )
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"could not load canonicalization matrix helper from {helper_path}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    matrix = _load_matrix_module(repo_root)

    matrix.assert_negative_coverage_matrix_matches_disk()
    print("Canonicalization negative coverage matrix matches on-disk vectors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
