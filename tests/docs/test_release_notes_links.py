# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Docs-link checks for the v1.7.x delta and verifier JSON pages."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_v17x_delta_covers_requested_user_visible_surface() -> None:
    text = (ROOT / "docs" / "release-notes" / "v1.7.x-delta.md").read_text(
        encoding="utf-8"
    )

    assert "Issue #172" in text
    assert "verify --explain" in text
    assert "verify --json" in text
    assert "reason_code_version" in text
    assert "schema_version" in text
    assert "negative conformance vectors" in text
    assert "CI Gating Example" in text
    assert "tests/conformance/README.md" in text
    assert "tests/conformance/canonicalization_negative_matrix.md" in text


def test_verify_json_docs_cover_failed_gate_output() -> None:
    cli = (ROOT / "docs" / "cli" / "verify-json.md").read_text(encoding="utf-8")
    schema = (ROOT / "docs" / "schema" / "verify-json.md").read_text(
        encoding="utf-8"
    )

    assert "verify --json" in cli
    assert "verify --explain" in cli
    assert "schema_version" in cli
    assert "failed_gates[]" in cli
    assert "bundle_id" in cli
    assert "vector_id" in cli
    assert "schema_version" in schema
    assert "E_EMPTY_BUNDLE" in schema
    assert "E_SCHEMA_INVALID" in schema
    assert "negative conformance vectors" in schema
