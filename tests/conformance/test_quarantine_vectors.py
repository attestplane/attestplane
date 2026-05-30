# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Anchoring status conformance vectors for ``attestplane verify --json``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verifier import verify_proof_bundle

ROOT = Path(__file__).resolve().parents[2]
PASS_FIXTURE = ROOT / "fixtures" / "conformance" / "baseline.att"
QUARANTINE_FIXTURE = ROOT / "fixtures" / "anchor" / "quarantine_case.json"

VECTOR_CASES = [
    {
        "case_id": "anchoring-unanchored-positive",
        "bundle_path": PASS_FIXTURE,
        "expected_status": "unanchored",
        "expected_quarantined": False,
        "expected_exit_code": 0,
    },
    {
        "case_id": "anchoring-unanchored-negative",
        "bundle_path": QUARANTINE_FIXTURE,
        "expected_status": "quarantined",
        "expected_quarantined": True,
        "expected_exit_code": 2,
    },
    {
        "case_id": "anchoring-anchored-positive",
        "bundle_path": PASS_FIXTURE,
        "mutate_anchor_ref": True,
        "expected_status": "anchored",
        "expected_quarantined": False,
        "expected_exit_code": 0,
    },
    {
        "case_id": "anchoring-anchored-negative",
        "bundle_path": PASS_FIXTURE,
        "expected_status": "unanchored",
        "expected_quarantined": False,
        "expected_exit_code": 0,
    },
    {
        "case_id": "anchoring-quarantined-positive",
        "bundle_path": QUARANTINE_FIXTURE,
        "expected_status": "quarantined",
        "expected_quarantined": True,
        "expected_exit_code": 2,
    },
    {
        "case_id": "anchoring-quarantined-negative",
        "bundle_path": PASS_FIXTURE,
        "expected_status": "unanchored",
        "expected_quarantined": False,
        "expected_exit_code": 0,
    },
]


def _load_bundle(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _materialize_bundle(case: dict[str, object], tmp_path: Path) -> Path:
    bundle = _load_bundle(Path(case["bundle_path"]))
    if case.get("mutate_anchor_ref"):
        bundle["chain_metadata"]["anchor_ref"] = "anchor://test/vector"
    out = tmp_path / f"{case['case_id']}.json"
    out.write_text(json.dumps(bundle), encoding="utf-8")
    return out


@pytest.mark.parametrize("case", VECTOR_CASES, ids=lambda case: str(case["case_id"]))
def test_verify_json_anchoring_vectors(
    case: dict[str, object], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle_path = _materialize_bundle(case, tmp_path)
    result = verify_proof_bundle(_load_bundle(bundle_path))

    rc = main(["verify", "--json", str(bundle_path)])
    payload = json.loads(capsys.readouterr().out)

    assert rc == case["expected_exit_code"]
    assert payload["anchor_status"] == case["expected_status"]
    assert payload["anchoring"] == {
        "status": case["expected_status"],
        "quarantined": case["expected_quarantined"],
    }
    assert result.anchoring_status == case["expected_status"]
    assert result.anchoring_quarantined is case["expected_quarantined"]
