# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Positive additive-optional ``schema_version`` conformance vector.

This pins the forward-compatible acceptance path for bundles that carry
unknown optional fields in ``chain_metadata`` while keeping the
compatible schema version unchanged.
"""

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
    / "vectors"
    / "schema_version"
    / "additive_optional"
    / "bundle.json"
)


def _run_verify(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object], str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, json.loads(captured.out), captured.err


def test_additive_optional_schema_version_vector_accepts_cleanly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = json.loads(ADDITIVE_OPTIONAL_FIXTURE.read_text(encoding="utf-8"))
    assert bundle["chain_metadata"]["future_metadata_field"] == "kept"

    rc, payload, stderr = _run_verify(
        ["verify", "--json", str(ADDITIVE_OPTIONAL_FIXTURE)], capsys
    )

    assert rc == 0
    assert stderr == ""
    assert payload["schema_version"] == 1
    assert payload["result"] == "pass"
    assert payload["exit_code"] == 0
    assert payload["reason_code"] is None
    assert payload["reasons"] == []
    assert payload["taxonomy_version"] == 1
    assert payload["bundle"]["schema_version"] == 1
