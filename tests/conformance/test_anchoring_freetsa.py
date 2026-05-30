# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""FreeTSA live-anchoring quarantine regression coverage.

The quarantined fixture below captures the 2026-05-27 live FreeTSA
failure mode. A TSA failure must fail closed into quarantine and never
surface as a claim-safe verified result.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verifier import verify_proof_bundle
from attestplane.verify_reason_codes import VERIFY_REASON_ANCHOR_INVALID

ROOT = Path(__file__).resolve().parents[2]
FREE_TSA_QUARANTINED_FIXTURE = (
    ROOT / "sdk" / "python" / "tests" / "conformance" / "free_tsa_quarantined_bundle.json"
)


def _load_fixture(path: Path) -> dict[str, object]:
    raw = path.read_text(encoding="utf-8")
    bundle = json.loads(raw)
    assert raw == json.dumps(bundle, indent=2) + "\n"
    return bundle


def test_freetsa_quarantine_fixture_is_byte_stable() -> None:
    assert FREE_TSA_QUARANTINED_FIXTURE.exists()
    bundle = _load_fixture(FREE_TSA_QUARANTINED_FIXTURE)
    assert bundle["anchoring"] == {"status": "quarantined", "quarantined": True}


def test_freetsa_quarantine_fixture_verifies_as_quarantined(
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = _load_fixture(FREE_TSA_QUARANTINED_FIXTURE)
    result = verify_proof_bundle(bundle)

    rc = main(["verify", "--json", str(FREE_TSA_QUARANTINED_FIXTURE)])
    payload = json.loads(capsys.readouterr().out)

    assert result.ok is False
    assert result.anchoring_status == "quarantined"
    assert result.anchoring_quarantined is True
    assert result.primary_reason == VERIFY_REASON_ANCHOR_INVALID
    assert rc == 2
    assert payload["result"] == "fail"
    assert payload["exit_code"] == 2
    assert payload["reason_code"] == VERIFY_REASON_ANCHOR_INVALID
    assert payload["anchoring"] == {"status": "quarantined", "quarantined": True}

