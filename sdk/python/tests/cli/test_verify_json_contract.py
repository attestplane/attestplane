# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Structured ``attestplane verify --json`` contract tests."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from attestplane.cli.main import _explain_reserved_reasons, main
from attestplane.cli.verify_json import (
    _canonical_path_to_pointer,
    _reject_duplicate_keys,
    _schema_path_from_bundle_error,
)
from attestplane.proof_bundle import ProofBundleBuilder
from attestplane.verify_errors import VERIFY_SCHEMA_ERROR
from attestplane.verify_reason_codes import (
    VERIFY_REASON_CANONICAL_MISMATCH,
    VERIFY_REASON_CODE_DESCRIPTIONS,
    VERIFY_REASON_CODE_VERSION,
    VERIFY_REASON_SCHEMA_INVALID,
    VERIFY_REASON_STRUCTURE_INVALID,
)

ROOT = Path(__file__).resolve().parents[4]
PASS_FIXTURE = ROOT / "fixtures" / "positive" / "minimal.json"
FAIL_FIXTURE = ROOT / "fixtures" / "negative" / "non_nfc_bundle.json"


def _run_verify(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, dict[str, object], str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, json.loads(captured.out), captured.err


def test_verify_json_pass_fixture_emits_fixed_schema(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, stderr = _run_verify(["verify", "--json", str(PASS_FIXTURE)], capsys)

    assert rc == 0
    assert stderr == ""
    assert payload["schema_version"] == 1
    assert payload["result"] == "pass"
    assert payload["exit_code"] == 0
    assert payload["reasons"] == []
    assert payload["bundle"] == {
        "schema_version": 1,
        "digest": payload["bundle"]["digest"],  # type: ignore[index]
    }
    assert re.fullmatch(r"[0-9a-f]{64}", str(payload["bundle"]["digest"]))  # type: ignore[index]


def test_verify_json_fail_fixture_reports_canonicalization_reason(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, stderr = _run_verify(["verify", "--json", str(FAIL_FIXTURE)], capsys)

    assert rc == 1
    assert stderr == ""
    assert payload["schema_version"] == 1
    assert payload["result"] == "fail"
    assert payload["exit_code"] == 1
    assert re.fullmatch(r"[0-9a-f]{64}", str(payload["bundle"]["digest"]))  # type: ignore[index]
    reason = payload["reasons"][0]  # type: ignore[index]
    assert reason["code"] == VERIFY_REASON_CANONICAL_MISMATCH
    assert reason["reason_code"] == reason["code"]
    assert reason["reason_code_version"] == VERIFY_REASON_CODE_VERSION
    assert reason["path"].startswith("/events/")
    assert "canonicalization" in reason["message"]


def test_verify_json_and_explain_keep_json_parseable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, stderr = _run_verify(["verify", "--json", "--explain", str(FAIL_FIXTURE)], capsys)

    assert rc == 1
    assert stderr == ""
    reason = payload["reasons"][0]  # type: ignore[index]
    assert reason["code"] == VERIFY_REASON_CANONICAL_MISMATCH
    assert reason["reason_code"] == reason["code"]
    assert reason["reason_code_version"] == VERIFY_REASON_CODE_VERSION
    assert "Unicode-NFC" in reason["message"]
    assert reason["explanation"] == VERIFY_REASON_CODE_DESCRIPTIONS[reason["code"]]


def test_verify_json_reports_invalid_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = tmp_path / "bad.json"
    bundle.write_text("{", encoding="utf-8")

    rc, payload, stderr = _run_verify(["verify", "--json", "--explain", str(bundle)], capsys)

    assert rc == 2
    assert stderr == f"{VERIFY_SCHEMA_ERROR}\n"
    reason = payload["reasons"][0]  # type: ignore[index]
    assert reason["code"] == VERIFY_REASON_SCHEMA_INVALID
    assert reason["reason_code"] == reason["code"]
    assert reason["reason_code_version"] == VERIFY_REASON_CODE_VERSION
    assert reason["path"] == "/"
    assert str(bundle) in reason["message"]
    assert reason["explanation"] == VERIFY_REASON_CODE_DESCRIPTIONS[reason["code"]]


def test_verify_json_reports_invalid_utf8(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = tmp_path / "bad-utf8.json"
    bundle.write_bytes(b"\xff")

    rc, payload, stderr = _run_verify(["verify", "--json", str(bundle)], capsys)

    assert rc == 2
    assert stderr == f"{VERIFY_SCHEMA_ERROR}\n"
    reason = payload["reasons"][0]  # type: ignore[index]
    assert reason["code"] == VERIFY_REASON_SCHEMA_INVALID
    assert reason["path"] == "/"
    assert reason["message"] == "bundle is not valid UTF-8"


def test_verify_json_rejects_duplicate_keys(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = tmp_path / "duplicate.json"
    bundle.write_text('{"chain_metadata": {}, "chain_metadata": {}}', encoding="utf-8")

    rc, payload, stderr = _run_verify(["verify", "--json", "--explain", str(bundle)], capsys)

    assert rc == 2
    assert stderr == f"{VERIFY_SCHEMA_ERROR}\n"
    reason = payload["reasons"][0]  # type: ignore[index]
    assert reason["code"] == VERIFY_REASON_STRUCTURE_INVALID
    assert reason["reason_code"] == reason["code"]
    assert reason["reason_code_version"] == VERIFY_REASON_CODE_VERSION
    assert reason["path"] == "/chain_metadata"
    assert "duplicate JSON key: chain_metadata" in reason["message"]


def test_verify_json_rejects_non_object_root(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = tmp_path / "array.json"
    bundle.write_text("[]", encoding="utf-8")

    rc, payload, stderr = _run_verify(["verify", "--json", str(bundle)], capsys)

    assert rc == 2
    assert stderr == f"{VERIFY_SCHEMA_ERROR}\n"
    reason = payload["reasons"][0]  # type: ignore[index]
    assert reason["code"] == VERIFY_REASON_SCHEMA_INVALID
    assert reason["reason_code"] == reason["code"]
    assert reason["reason_code_version"] == VERIFY_REASON_CODE_VERSION
    assert reason["path"] == "/"
    assert reason["message"] == "bundle must be a JSON object, got list"


def test_verify_json_reports_missing_bundle_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = tmp_path / "missing.json"

    rc, payload, stderr = _run_verify(["verify", "--json", str(bundle)], capsys)

    assert rc == 1
    assert stderr == ""
    reason = payload["reasons"][0]  # type: ignore[index]
    assert reason["code"] == VERIFY_REASON_SCHEMA_INVALID
    assert reason["reason_code"] == reason["code"]
    assert reason["reason_code_version"] == VERIFY_REASON_CODE_VERSION
    assert reason["path"] == "/"
    assert "cannot read" in reason["message"]


def test_verify_json_schema_error_maps_missing_version_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = tmp_path / "missing-version.json"
    payload = ProofBundleBuilder(chain_id="missing-version", producer_runtime="test").build()
    del payload["chain_metadata"]["schema_version"]
    bundle.write_text(json.dumps(payload), encoding="utf-8")

    rc, payload, stderr = _run_verify(["verify", "--json", str(bundle)], capsys)

    assert rc == 1
    assert stderr == ""
    reason = payload["reasons"][0]  # type: ignore[index]
    assert reason["path"] == "/chain_metadata/schema_version"
    assert reason["reason_code"] == reason["code"]
    assert reason["reason_code_version"] == VERIFY_REASON_CODE_VERSION


def test_verify_json_unknown_required_field_reports_chain_metadata_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = tmp_path / "unknown-required-field.json"
    payload = ProofBundleBuilder(chain_id="unknown-required", producer_runtime="test").build()
    payload["chain_metadata"]["critical_future_field"] = True
    bundle.write_text(json.dumps(payload), encoding="utf-8")

    rc, payload, stderr = _run_verify(["verify", "--json", str(bundle)], capsys)

    assert rc == 1
    assert stderr == ""
    reason = payload["reasons"][0]  # type: ignore[index]
    assert reason["code"] == "att.verify.schema_unknown"
    assert reason["reason_code"] == reason["code"]
    assert reason["reason_code_version"] == VERIFY_REASON_CODE_VERSION
    assert reason["path"] == "/chain_metadata/critical_future_field"


def test_verify_json_private_pointer_helpers_cover_known_paths() -> None:
    assert _canonical_path_to_pointer("payload.actor") == "/"
    assert _canonical_path_to_pointer("$.actor") == "/actor"
    assert _canonical_path_to_pointer("$.events[0].event.payload") == "/events/0/event/payload"
    assert _canonical_path_to_pointer("$.events[bad") == "/events"

    assert _schema_path_from_bundle_error("chain_metadata.schema_version is missing") == (
        "/chain_metadata/schema_version"
    )
    assert _schema_path_from_bundle_error("verification_report must be object") == "/verification_report"
    assert _schema_path_from_bundle_error("forbidden_fields contains reserved key") == "/forbidden_fields"
    assert _schema_path_from_bundle_error("events must be a list") == "/events"
    assert _schema_path_from_bundle_error("bundle_version must be 1") == "/bundle_version"
    assert _schema_path_from_bundle_error("signatures must be a list") == "/signatures"
    assert _schema_path_from_bundle_error("policy_trace_refs must be a list") == "/policy_trace_refs"
    assert _schema_path_from_bundle_error("retention_proofs must be a list") == "/retention_proofs"
    assert _schema_path_from_bundle_error("unknown") == "/"


def test_verify_json_duplicate_key_hook_returns_object() -> None:
    assert _reject_duplicate_keys([("a", 1), ("b", 2)]) == {"a": 1, "b": 2}
    with pytest.raises(ValueError, match="duplicate JSON key: a"):
        _reject_duplicate_keys([("a", 1), ("a", 2)])


def test_verify_explain_reserved_reasons_lists_nested_additive_fields() -> None:
    bundle = ProofBundleBuilder(chain_id="reserved", producer_runtime="test").build()
    bundle["top_extra"] = True
    bundle["chain_metadata"]["extra_chain"] = True
    bundle["verification_report"]["extra_report"] = True
    bundle["framework_mappings"] = [
        {
            "obligation_id": "obl",
            "evidence_event_indexes": [],
            "implementation_status_at_bundle_time": "implemented",
            "extra_mapping": True,
        }
    ]
    bundle["events"] = [
        {
            "seq": 0,
            "prev_hash_hex": "0" * 64,
            "event_hash_hex": "1" * 64,
            "event": {
                "schema_version": 1,
                "event_id": "00000000-0000-7000-8000-000000000220",
                "timestamp": "2026-05-24T00:00:00Z",
                "event_type": "eval_event",
                "actor": "agent",
                "payload": {},
                "subject_ref": {
                    "scheme": "sha256",
                    "value": "2" * 64,
                    "extra_subject": True,
                },
                "human_verifier": {
                    "scheme": "mailto",
                    "value": "ops@example.invalid",
                    "extra_human": True,
                },
                "extra_event": True,
            },
            "extra_event_item": True,
        }
    ]
    bundle["signatures"] = [{"signature_schema_version": 1, "extra_signature": True}]
    bundle["retention_proofs"] = [
        {
            "retention_proof_schema_version": 1,
            "proof_id": "proof",
            "action": "delete",
            "target_event_hash_hex": "3" * 64,
            "commit_event_hash_hex": "4" * 64,
            "reason": "test",
            "redacted_event_hash_hex": "5" * 64,
            "extra_retention": True,
        }
    ]

    reasons = _explain_reserved_reasons(bundle)

    assert reasons == [
        {
            "code": "att.verify.schema_unknown",
            "severity": "reserved",
            "detail": (
                "ignored additive fields: bundle.top_extra, chain_metadata.extra_chain, "
                "verification_report.extra_report, framework_mappings[0].extra_mapping, "
                "events[0].extra_event_item, events[0].event.extra_event, "
                "events[0].event.subject_ref.extra_subject, "
                "events[0].event.human_verifier.extra_human, "
                "signatures[0].extra_signature, retention_proofs[0].extra_retention"
            ),
        }
    ]


def test_verify_explain_reserved_reasons_empty_for_known_bundle() -> None:
    bundle = ProofBundleBuilder(chain_id="reserved", producer_runtime="test").build()

    assert _explain_reserved_reasons(bundle) == []
