# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""CLI strict proof-bundle error surfacing tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.proof_bundle import ProofBundleBuilder
from attestplane.types import EventDraft
from attestplane.verify_errors import VERIFY_BUNDLE_SCHEMA_INCOMPLETE, VERIFY_REQUIRED_FIELDS_MISSING

GOLDEN = Path(__file__).resolve().parents[4] / "tests" / "golden" / "verify-json"


def test_verify_bundle_option_prints_incomplete_code_to_stderr(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    event = chain_extend(
        genesis_head(),
        EventDraft(event_type="evidence_event", actor="agent"),
        now=datetime(2026, 5, 22, tzinfo=UTC),
        event_id="00000000-0000-7000-8000-000000000124",
    )
    builder = ProofBundleBuilder(chain_id="unsigned", producer_runtime="test")
    builder.extend([event])
    path = tmp_path / "unsigned.json"
    path.write_text(json.dumps(builder.build()), encoding="utf-8")

    rc = main(["verify", "--bundle", str(path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    expected = json.loads((GOLDEN / "unsigned_bundle.json").read_text(encoding="utf-8"))

    assert rc == 2
    assert payload == expected
    assert captured.err == f"{VERIFY_BUNDLE_SCHEMA_INCOMPLETE}\n"


def test_verify_require_events_prints_empty_code_to_stderr(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "empty.json"
    path.write_text(
        json.dumps(ProofBundleBuilder(chain_id="empty", producer_runtime="test").build()),
        encoding="utf-8",
    )

    rc = main(["verify", str(path), "--require-events", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    expected = json.loads((GOLDEN / "empty_required_events.json").read_text(encoding="utf-8"))

    assert rc == 2
    assert payload == expected
    assert captured.err == f"{VERIFY_REQUIRED_FIELDS_MISSING}\n"


def test_verify_schema_version_unsupported_preserves_bundle_version_in_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    event = chain_extend(
        genesis_head(),
        EventDraft(event_type="evidence_event", actor="agent"),
        now=datetime(2026, 5, 22, tzinfo=UTC),
        event_id="00000000-0000-7000-8000-000000000125",
    )
    builder = ProofBundleBuilder(chain_id="unsupported-version", producer_runtime="test")
    builder.extend([event])
    path = tmp_path / "unsupported.json"
    bundle = builder.build()
    bundle["bundle_version"] = 999
    path.write_text(json.dumps(bundle), encoding="utf-8")

    rc = main(["verify", "--json", str(path)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 2
    assert payload["bundle_schema_version"] == 999
    assert payload["ok"] is False
    assert payload["reasons"] == [
        {
            "code": "REASON_SCHEMA_VERSION_UNSUPPORTED",
            "field": "/",
            "message": "unsupported bundle_version=999; this verifier handles version 1 only",
        }
    ]
    assert captured.err == ""
