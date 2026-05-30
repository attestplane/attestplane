# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for claim-safe quarantine persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pytest

from attestplane import AttestSubstrate, EventDraft
from attestplane.cli.main import main
from attestplane.proof_bundle import ProofBundleBuilder
from attestplane.verifier import verify_proof_bundle
from attestplane.verify_reason_codes import VERIFY_REASON_ANCHOR_INVALID

ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = ROOT / "schemas" / "v1" / "proof_bundle.schema.json"
NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _bundle(*, status: str) -> dict[str, object]:
    substrate = AttestSubstrate()
    event = substrate.append(
        EventDraft(event_type="eval_event", actor="agent://test", payload={"score": 1}),
        now=NOW,
    )
    builder = ProofBundleBuilder(chain_id="freetsa-quarantine", producer_runtime="test")
    builder.extend([event])
    bundle = builder.build(now=NOW, anchoring={"status": status, "quarantined": status == "quarantined"})
    if status == "anchored":
        bundle["chain_metadata"]["anchor_ref"] = "anchor://freetsa/live/ok"
    return bundle


@pytest.mark.parametrize(
    ("status", "expected_ok", "expected_quarantined"),
    [
        ("anchored", True, False),
        ("quarantined", False, True),
    ],
)
def test_bundle_anchoring_field_is_schema_compatible(
    status: str,
    expected_ok: bool,
    expected_quarantined: bool,
) -> None:
    bundle = _bundle(status=status)
    jsonschema.validate(bundle, _schema())

    result = verify_proof_bundle(bundle)

    assert result.ok is expected_ok
    assert result.anchoring_status == status
    assert result.anchoring_quarantined is expected_quarantined
    if status == "quarantined":
        assert result.primary_reason == VERIFY_REASON_ANCHOR_INVALID


def test_quarantined_bundle_surfaces_in_verify_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bundle = _bundle(status="quarantined")
    bundle_path = tmp_path / "quarantined.json"
    bundle_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")

    rc = main(["verify", "--json", str(bundle_path)])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 4
    assert payload["result"] == "fail"
    assert payload["exit_code"] == 4
    assert payload["reason_code"] == VERIFY_REASON_ANCHOR_INVALID
    assert payload["anchoring"] == {"status": "quarantined", "quarantined": True}
