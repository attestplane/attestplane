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
    assert "schema_version" in text
    assert "negative conformance vectors" in text
    assert "CI Gating Example" in text


def test_verify_json_docs_cover_exit_code_and_reason_list() -> None:
    cli = (ROOT / "docs" / "cli" / "verify-json.md").read_text(encoding="utf-8")
    schema = (ROOT / "docs" / "schema" / "verify-json.md").read_text(
        encoding="utf-8"
    )
    policy = (ROOT / "docs" / "schema" / "schema-version-policy.md").read_text(
        encoding="utf-8"
    )

    assert "verify --json" in cli
    assert "verify --explain" in cli
    assert "result" in cli
    assert "primary_reason" in cli
    assert "secondary_reasons" in cli
    assert "schema_version_forward_compat" in cli
    assert "reasons[]" in cli
    assert "schema_version" in schema
    assert "att.verify.schema_version_unsupported" in schema
    assert "negative conformance vectors" in schema
    assert "schema_version_forward_compat" in policy
    assert "unknown_field" in policy
