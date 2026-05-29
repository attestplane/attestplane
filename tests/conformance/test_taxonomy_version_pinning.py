# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Conformance vectors for ``attestplane verify --require-taxonomy-version``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verify_reason_codes import (
    VERIFY_REASON_SCHEMA_VERSION_MISSING,
    VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
)

ROOT = Path(__file__).resolve().parents[2]
ADDITIVE_SCHEMA_BUNDLE = (
    ROOT / "tests" / "conformance" / "schema_version" / "additive_with_unknown_field_ok" / "bundle.json"
)
TAXONOMY_STALE_DIR = ROOT / "fixtures" / "neg" / "taxonomy-stale"


def _run_verify(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, object]]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, json.loads(captured.out)


@pytest.mark.parametrize(
    ("fixture_name", "expected_reason_code"),
    [
        ("missing.json", VERIFY_REASON_SCHEMA_VERSION_MISSING),
        ("older.json", VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED),
    ],
)
def test_taxonomy_version_pinning_rejects_stale_bundles(
    fixture_name: str,
    expected_reason_code: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload = _run_verify(
        [
            "verify",
            "--json",
            "--require-taxonomy-version",
            "1",
            str(TAXONOMY_STALE_DIR / fixture_name),
        ],
        capsys,
    )

    assert rc == 1
    assert payload["schema_version"] == 1
    assert payload["result"] == "fail"
    assert payload["exit_code"] == 1
    assert payload["reason_code"] == expected_reason_code
    assert payload["taxonomy_version"] == 1
    assert payload["reasons"][0]["code"] == expected_reason_code
    assert payload["reasons"][0]["path"] == "/chain_metadata/evidence_taxonomy_version"


def test_taxonomy_version_pinning_accepts_additive_field_bundle(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload = _run_verify(
        [
            "verify",
            "--json",
            "--require-taxonomy-version",
            "1",
            str(ADDITIVE_SCHEMA_BUNDLE),
        ],
        capsys,
    )

    assert rc == 0
    assert payload["schema_version"] == 1
    assert payload["result"] == "pass"
    assert payload["exit_code"] == 0
    assert payload["reason_code"] is None
    assert payload["taxonomy_version"] == 1
