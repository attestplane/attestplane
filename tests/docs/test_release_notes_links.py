# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Docs-link checks for the v1.7.x and v1.8.x release-note surfaces."""

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


def test_verify_json_docs_cover_exit_code_and_reason_list() -> None:
    cli = (ROOT / "docs" / "cli" / "verify-json.md").read_text(encoding="utf-8")
    schema = (ROOT / "docs" / "schema" / "verify-json.md").read_text(
        encoding="utf-8"
    )

    assert "verify --json" in cli
    assert "verify --explain" in cli
    assert "schema_version" in cli
    assert "exit_code" in cli
    assert "reasons[]" in cli
    assert "bundle.digest" in cli
    assert "schema_version" in schema
    assert "att.verify.schema_version_missing" in schema
    assert "att.verify.schema_version_unsupported" in schema
    assert "negative conformance vectors" in schema


def test_v18x_delta_links_open_docs_issues_and_contract_pages() -> None:
    text = (ROOT / "docs" / "release-notes" / "v1.8.4.draft.md").read_text(
        encoding="utf-8"
    )

    assert "issues/211" in text
    assert "issues/157" in text
    assert "issues/246" in text
    assert "positive forward-compat path" in text
    assert "taxonomy_version = 1" in text
    assert "exit_code" in text
    assert "docs/cli/verify-json.md" in text
    assert "docs/schema/verify-json.md" in text
    assert "docs/errors.md" in text
