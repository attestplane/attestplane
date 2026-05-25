# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Issue #123 CLI strict proof-bundle error surfacing tests."""

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
from attestplane.verify_reason_codes import (
    VERIFY_REASON_REQUIRED_FIELD_MISSING,
    VERIFY_REASON_SCHEMA_UNKNOWN,
    VERIFY_REASON_SCHEMA_VERSION_MISSING,
    VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
    VERIFY_REASON_SIGNATURE_MISSING,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "bundles"
UNKNOWN_SCHEMA_VERSION = ROOT / "tests" / "fixtures" / "unknown_schema_version.json"


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

    assert rc == 2
    payload = json.loads(captured.out)
    assert payload["schema_version"] == 1
    assert payload["result"] == "fail"
    assert payload["exit_code"] == 2
    assert payload["reason_code"] == VERIFY_REASON_SIGNATURE_MISSING
    assert payload["taxonomy_version"] == 1
    assert payload["reasons"][0]["code"] == VERIFY_REASON_SIGNATURE_MISSING
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

    assert rc == 2
    payload = json.loads(captured.out)
    assert payload["schema_version"] == 1
    assert payload["result"] == "fail"
    assert payload["exit_code"] == 2
    assert payload["reason_code"] == VERIFY_REASON_REQUIRED_FIELD_MISSING
    assert payload["taxonomy_version"] == 1
    assert payload["reasons"][0]["code"] == VERIFY_REASON_REQUIRED_FIELD_MISSING
    assert captured.err == f"{VERIFY_REQUIRED_FIELDS_MISSING}\n"


def test_verify_json_includes_reasons_list_for_schema_version_failures(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "missing-schema-version.json"
    payload = json.loads((FIXTURES / "valid_signed_attestation.json").read_text(encoding="utf-8"))
    del payload["chain_metadata"]["schema_version"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    rc = main(["verify", "--json", str(path)])
    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert rc == 1
    assert result["schema_version"] == 1
    assert result["result"] == "fail"
    assert result["reason_code"] == VERIFY_REASON_SCHEMA_VERSION_MISSING
    assert result["taxonomy_version"] == 1
    assert result["reasons"][0]["code"] == VERIFY_REASON_SCHEMA_VERSION_MISSING
    assert captured.err == ""


def test_verify_json_reports_unknown_required_metadata_field(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "unknown-required-field.json"
    payload = json.loads((FIXTURES / "valid_signed_attestation.json").read_text(encoding="utf-8"))
    payload["chain_metadata"]["critical_future_field"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")

    rc = main(["verify", "--json", str(path)])
    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert rc == 1
    assert result["schema_version"] == 1
    assert result["result"] == "fail"
    assert result["reasons"][0]["code"] == VERIFY_REASON_SCHEMA_UNKNOWN
    assert result["reasons"][0]["path"] == "/chain_metadata/critical_future_field"
    assert captured.err == ""


def test_verify_json_reports_unknown_schema_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(["verify", "--strict-schema", "--json", str(UNKNOWN_SCHEMA_VERSION)])
    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert rc == 1
    assert result["schema_version"] == 1
    assert result["result"] == "fail"
    assert result["exit_code"] == 1
    assert result["reason_code"] == VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED
    assert result["reasons"][0]["code"] == VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED
    assert result["reasons"][0]["path"] == "/chain_metadata/schema_version"
    assert captured.err == ""
