# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verify_reason_codes import VERIFY_REASON_TAXONOMY_VERSION_MISMATCH

ROOT = Path(__file__).resolve().parents[2]
VALID_BUNDLE = ROOT / "tests" / "fixtures" / "valid_bundle.json"


def test_verify_require_taxonomy_version_passes_when_pinned_version_matches(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main([
        "verify",
        "--json",
        "--require-taxonomy-version",
        "1",
        str(VALID_BUNDLE),
    ])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert captured.err == ""
    assert payload["schema_version"] == 1
    assert payload["result"] == "pass"
    assert payload["exit_code"] == 0
    assert payload["reason_code"] is None
    assert payload["taxonomy_version"] == 1
    assert payload["required_taxonomy_version"] == 1
    assert payload["reasons"] == []
    assert payload["bundle"]["schema_version"] == 1


def test_verify_require_taxonomy_version_fails_with_stable_reason_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main([
        "verify",
        "--json",
        "--require-taxonomy-version",
        "999",
        str(VALID_BUNDLE),
    ])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 1
    assert captured.err == ""
    assert payload["schema_version"] == 1
    assert payload["result"] == "fail"
    assert payload["exit_code"] == 1
    assert payload["reason_code"] == VERIFY_REASON_TAXONOMY_VERSION_MISMATCH
    assert payload["taxonomy_version"] == 1
    assert payload["required_taxonomy_version"] == 999
    assert payload["reasons"][0]["code"] == VERIFY_REASON_TAXONOMY_VERSION_MISMATCH
    assert payload["reasons"][0]["path"] == "/taxonomy_version"


def test_verify_help_lists_require_taxonomy_version_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["verify", "--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "--require-taxonomy-version" in help_text
    assert "taxonomy_version matches this value" in help_text
