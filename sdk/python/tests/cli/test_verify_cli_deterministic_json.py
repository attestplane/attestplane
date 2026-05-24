# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Deterministic JSON smoke tests for ``attestplane verify --json``."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from attestplane import AttestSubstrate, EventDraft
from attestplane.cli.main import main
from attestplane.proof_bundle import ProofBundleBuilder

ROOT = Path(__file__).resolve().parents[4]
GOLDEN = ROOT / "tests" / "golden" / "verify-json" / "valid_minimal.json"


def _bundle_path(tmp_path: Path) -> Path:
    substrate = AttestSubstrate()
    event = substrate.append(
        EventDraft(event_type="eval_event", actor="agent", payload={"ok": True}),
        now=datetime(2026, 5, 19, tzinfo=UTC),
    )
    builder = ProofBundleBuilder(chain_id="cli-json", producer_runtime="test")
    builder.extend([event])
    path = tmp_path / "bundle.json"
    path.write_text(
        json.dumps(builder.build(now=datetime(2026, 5, 19, tzinfo=UTC)), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def test_verify_json_is_deterministic_and_machine_readable(
    tmp_path: Path,
    capsys,
) -> None:
    bundle = _bundle_path(tmp_path)
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))

    rc1 = main(["verify", "--json", str(bundle)])
    out1 = capsys.readouterr()
    rc2 = main(["verify", "--json", str(bundle)])
    out2 = capsys.readouterr()

    assert rc1 == 0
    assert rc2 == 0
    assert out1.out == out2.out
    assert out1.err == ""
    assert out2.err == ""

    payload = json.loads(out1.out)
    assert payload == expected
    assert payload["schema_version"] == "1"
    assert payload["bundle_schema_version"] == 1
    assert payload["ok"] is True
    assert payload["reasons"] == []
