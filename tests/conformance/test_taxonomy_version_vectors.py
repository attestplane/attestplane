# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Taxonomy-version pinning coverage for ``attestplane verify``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures" / "conformance"
PASS_FIXTURE = FIXTURES / "with_taxonomy.attest"
FAIL_FIXTURE = FIXTURES / "taxonomy_mismatch.attest"


def _run_verify(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, object], str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, json.loads(captured.out), captured.err


def test_require_taxonomy_version_passes_on_exact_match(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, stderr = _run_verify(
        ["verify", "--json", "--require-taxonomy-version", "1", str(PASS_FIXTURE)],
        capsys,
    )

    assert rc == 0
    assert stderr == ""
    assert payload["result"] == "pass"
    assert payload["exit_code"] == 0
    assert payload["reason_code"] is None
    assert payload["reasons"] == []


def test_require_taxonomy_version_rejects_mismatch(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, stderr = _run_verify(
        ["verify", "--json", "--require-taxonomy-version", "1", str(FAIL_FIXTURE)],
        capsys,
    )

    assert rc == 3
    assert stderr == ""
    assert payload["result"] == "fail"
    assert payload["exit_code"] == 3
    assert payload["reason_code"] == "att.verify.taxonomy_version_mismatch"
    assert payload["reasons"]
    assert payload["reasons"][0]["code"] == "att.verify.taxonomy_version_mismatch"
    assert payload["reasons"][0]["path"] == "/taxonomy_version"
