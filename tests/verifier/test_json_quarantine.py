# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Direct regression coverage for ``verify --json`` anchoring state."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verifier import verify_proof_bundle

ROOT = Path(__file__).resolve().parents[2]
PASS_FIXTURE = ROOT / "fixtures" / "conformance" / "baseline.att"
QUARANTINE_FIXTURE = ROOT / "fixtures" / "quarantined.bundle"


def _load_bundle(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_bundle(tmp_path: Path, name: str, bundle: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(bundle), encoding="utf-8")
    return path


def test_verify_json_unanchored_bundle_reports_unanchored(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bundle_path = PASS_FIXTURE
    rc = main(["verify", "--json", str(bundle_path)])
    payload = json.loads(capsys.readouterr().out)
    result = verify_proof_bundle(_load_bundle(bundle_path))

    assert rc == 0
    assert payload["anchoring"] == {"status": "unanchored", "quarantined": False}
    assert result.anchoring_status == "unanchored"
    assert result.anchoring_quarantined is False


def test_verify_json_anchored_bundle_reports_anchored(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bundle = _load_bundle(PASS_FIXTURE)
    bundle["chain_metadata"]["anchor_ref"] = "anchor://test/quarantine"
    bundle_path = _write_bundle(tmp_path, "anchored.json", bundle)

    rc = main(["verify", "--json", str(bundle_path)])
    payload = json.loads(capsys.readouterr().out)
    result = verify_proof_bundle(_load_bundle(bundle_path))

    assert rc == 0
    assert payload["anchoring"] == {"status": "anchored", "quarantined": False}
    assert result.anchoring_status == "anchored"
    assert result.anchoring_quarantined is False


def test_verify_json_quarantined_bundle_reports_quarantined(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["verify", "--json", str(QUARANTINE_FIXTURE)])
    payload = json.loads(capsys.readouterr().out)
    result = verify_proof_bundle(_load_bundle(QUARANTINE_FIXTURE))

    assert rc == 2
    assert payload["anchoring"] == {"status": "quarantined", "quarantined": True}
    assert result.anchoring_status == "quarantined"
    assert result.anchoring_quarantined is True

