# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Positive schema-version conformance coverage for additive optional fields."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main


ROOT = Path(__file__).resolve().parents[3]
ADDITIVE_OPTIONAL_FIXTURE = (
    ROOT
    / "tests"
    / "conformance"
    / "schema_version"
    / "additive_with_unknown_field_ok"
    / "bundle.json"
)


def _bundle() -> dict:
    return json.loads(ADDITIVE_OPTIONAL_FIXTURE.read_text(encoding="utf-8"))


def test_schema_version_additive_optional_field_bundle_is_accepted_cleanly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = _bundle()
    assert bundle["chain_metadata"]["schema_version"] == 1
    assert bundle["chain_metadata"]["future_metadata_field"] == "kept"

    path = ADDITIVE_OPTIONAL_FIXTURE
    rc = main(["verify", "--json", str(path)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert captured.err == ""
    assert payload["schema_version"] == 1
    assert payload["result"] == "pass"
    assert payload["exit_code"] == 0
    assert payload["reason_code"] is None
    assert payload["reasons"] == []
