# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Coverage matrix for canonicalization negative edge cases."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _load_matrix_module():
    module_name = "attestplane_canonicalization_negative_matrix"
    helper_path = Path(__file__).with_name("canonicalization_negative_matrix.py")
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load canonicalization matrix helper from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


matrix = _load_matrix_module()


def test_canonicalization_negative_edge_matrix_matches_disk() -> None:
    matrix.assert_negative_coverage_matrix_matches_disk()


def test_canonicalization_negative_edge_matrix_covers_every_landed_vector() -> None:
    inventory = matrix.load_vector_inventory()
    labels = {entry["label"] for entry in inventory}
    for row in matrix.EDGE_ROWS:
        assert set(row.covered_labels) <= labels, row.edge_id
    assert labels == {
        label
        for row in matrix.EDGE_ROWS
        for label in row.covered_labels
    }


def test_canonicalization_negative_edge_matrix_reason_codes_are_known() -> None:
    inventory = matrix.load_vector_inventory()

    assert all(
        matrix.is_known_negative_reason_code(entry["expected_reason_code"])
        for entry in inventory
    )
