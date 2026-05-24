# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verifier import verify_proof_bundle_file

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "bundles"


def test_future_minor_bundle_sets_forward_compat_flag() -> None:
    result = verify_proof_bundle_file(FIXTURES / "future_minor.json")

    assert result.ok is True
    assert result.schema_version == "1.8"
    assert result.schema_version_forward_compat is True


def test_verify_json_reports_accept_and_forward_compat(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(["verify", "--json", str(FIXTURES / "future_minor.json")])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["result"] == "accept"
    assert payload["ok"] is True
    assert payload["schema_version"] == "1.8"
    assert payload["schema_version_forward_compat"] is True


def test_verify_explain_shows_forward_compat_info(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(["verify", "--explain", str(FIXTURES / "future_minor.json")])
    out = capsys.readouterr().out

    assert rc == 0
    assert "schema_version_forward_compat: true" in out
    assert "1.8 exceeds supported 1.7" in out
