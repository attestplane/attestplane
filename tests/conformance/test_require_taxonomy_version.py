# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Conformance coverage for `attestplane verify --require-taxonomy-version`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verify_reason_codes import VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures" / "conformance" / "taxonomy_v1_bundle.json"


def _run_verify(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, object]]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, json.loads(captured.out)


def test_taxonomy_pinning_is_opt_in_and_passes_when_matching(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload = _run_verify(["verify", "--json", str(FIXTURE)], capsys)

    assert rc == 0
    assert payload["result"] == "pass"
    assert payload["exit_code"] == 0
    assert payload["reason_code"] is None
    assert payload["reasons"] == []

    rc, payload = _run_verify(["verify", "--json", "--require-taxonomy-version", "v1", str(FIXTURE)], capsys)

    assert rc == 0
    assert payload["result"] == "pass"
    assert payload["exit_code"] == 0
    assert payload["reason_code"] is None
    assert payload["reasons"] == []


def test_taxonomy_pinning_mismatch_rejects_with_documented_exit_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload = _run_verify(["verify", "--json", "--require-taxonomy-version", "v2", str(FIXTURE)], capsys)

    assert rc == 2
    assert payload["result"] == "fail"
    assert payload["exit_code"] == 2
    assert payload["reason_code"] == VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED
    assert payload["reasons"][0]["code"] == VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED
    assert payload["reasons"][0]["path"] == "/chain_metadata/evidence_taxonomy_version"
    assert payload["reasons"][0]["message"] == "bundle taxonomy version mismatch"
