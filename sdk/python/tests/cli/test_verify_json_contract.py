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
    VERIFY_REASON_SCHEMA_INVALID,
    VERIFY_REASON_SCHEMA_UNKNOWN,
    VERIFY_REASON_STRUCTURE_INVALID,
)

ROOT = Path(__file__).resolve().parents[4]
CONTRACT_FIXTURE = ROOT / "sdk" / "python" / "tests" / "conformance" / "verify_json_contract_v1.json"
PASS_FIXTURE = (CONTRACT_FIXTURE.parent / "../../../../fixtures/positive/minimal.json").resolve()
FAIL_FIXTURE = (CONTRACT_FIXTURE.parent / "../../../../fixtures/reject/canonicalization-edge.json").resolve()


def _run_verify(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, dict[str, object], str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, json.loads(captured.out), captured.err


def _load_contract_fixture() -> dict[str, object]:
    return json.loads(CONTRACT_FIXTURE.read_text(encoding="utf-8"))


def _contract_cases() -> list[dict[str, object]]:
    fixture = _load_contract_fixture()
    assert fixture["fixture_version"] == 1
    cases = fixture["cases"]
    assert isinstance(cases, list)
    return cases


def _bundle_fixture_path(case: dict[str, object]) -> Path:
    return (CONTRACT_FIXTURE.parent / str(case["bundle_fixture"])).resolve()


def _assert_matches_verify_result_v1(
    payload: dict[str, object],
    *,
    expect_explanation: bool = False,
) -> None:
    schema = json.loads((ROOT / "schemas" / "cli" / "verify-result-v1.json").read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["additionalProperties"] is False
    assert schema["required"] == [
        "schema_version",
        "result",
        "exit_code",
        "reason_code",
        "taxonomy_version",
        "reasons",
        "bundle",
    ]

    expected_keys = {
        "schema_version",
        "result",
        "exit_code",
        "reason_code",
        "taxonomy_version",
        "reasons",
        "bundle",
    }
    if expect_explanation:
        expected_keys.add("explanation")
    assert set(payload) == expected_keys
    assert payload["schema_version"] == 1
    assert payload["result"] in {"pass", "fail"}
    assert isinstance(payload["exit_code"], int)
    assert payload["exit_code"] >= 0
    assert payload["taxonomy_version"] == 1
    assert payload["reason_code"] is None or re.fullmatch(
        r"att\.verify\.[a-z][a-z0-9_]*",
        str(payload["reason_code"]),
    )
    assert isinstance(payload["reasons"], list)

    bundle = payload["bundle"]
    assert isinstance(bundle, dict)
    assert set(bundle) == {"schema_version", "digest"}
    assert bundle["schema_version"] == 1
    assert re.fullmatch(r"[0-9a-f]{64}", str(bundle["digest"]))

    if expect_explanation:
        explanation = payload["explanation"]
        assert isinstance(explanation, list)
        assert explanation
        for item in explanation:
            assert isinstance(item, dict)
            assert set(item) == {"primary_reason", "pointer", "message"}
            assert item["pointer"]
            assert item["message"]

    for reason in payload["reasons"]:
        assert isinstance(reason, dict)
        expected_keys = {"code", "path", "message"}
        if "explanation" in reason:
            expected_keys.add("explanation")
        assert set(reason) == expected_keys
        assert re.fullmatch(r"att\.verify\.[a-z][a-z0-9_]*", str(reason["code"]))
        assert reason["path"]
        assert reason["message"]
        if "explanation" in reason:
            assert reason["explanation"]


def test_verify_json_contract_fixture_is_stable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _load_contract_fixture()
    for case in fixture["cases"]:
        assert isinstance(case, dict)
        bundle_fixture = _bundle_fixture_path(case)
        rc, payload, stderr = _run_verify(["verify", "--json", str(bundle_fixture)], capsys)

        assert rc == case["expected_exit_code"]
        assert stderr == case["expected_stderr"]
        assert payload == case["expected_stdout"]
        _assert_matches_verify_result_v1(payload)


def test_verify_json_pass_fixture_emits_fixed_schema(
    capsys: pytest.CaptureFixture[str],
) -> None:
    case = next(case for case in _contract_cases() if case["case_id"] == "verify_json_pass_minimal")
    bundle_fixture = _bundle_fixture_path(case)
    rc, payload, stderr = _run_verify(["verify", "--json", str(bundle_fixture)], capsys)

    assert rc == 0
    assert stderr == ""
    _assert_matches_verify_result_v1(payload)
    assert payload == case["expected_stdout"]


def test_verify_json_fail_fixture_reports_canonicalization_reason(
    capsys: pytest.CaptureFixture[str],
) -> None:
    case = next(
        case for case in _contract_cases() if case["case_id"] == "verify_json_fail_canonicalization_edge"
    )
    bundle_fixture = _bundle_fixture_path(case)
    rc, payload, stderr = _run_verify(["verify", "--json", str(bundle_fixture)], capsys)

    assert rc == 1
    assert stderr == ""
    _assert_matches_verify_result_v1(payload)
    assert payload == case["expected_stdout"]
    assert payload["reason_code"] == VERIFY_REASON_CANONICAL_MISMATCH
    reason = payload["reasons"][0]  # type: ignore[index]
    assert reason["code"] == VERIFY_REASON_CANONICAL_MISMATCH
    assert reason["path"].startswith("/events/")
    assert "canonicalization" in reason["message"]


def test_verify_json_and_explain_keep_json_parseable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, stderr = _run_verify(["verify", "--json", "--explain", str(FAIL_FIXTURE)], capsys)

    assert rc == 1
    assert stderr == ""
    _assert_matches_verify_result_v1(payload, expect_explanation=True)
    assert payload["reason_code"] == VERIFY_REASON_CANONICAL_MISMATCH
    explanation = payload["explanation"][0]  # type: ignore[index]
    assert explanation["primary_reason"] == VERIFY_REASON_CANONICAL_MISMATCH
    assert explanation["pointer"].startswith("/events/")
    assert "Unicode-NFC" in explanation["message"]
    reason = payload["reasons"][0]  # type: ignore[index]
    assert reason["code"] == VERIFY_REASON_CANONICAL_MISMATCH
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
    _assert_matches_verify_result_v1(payload, expect_explanation=True)
    assert payload["reason_code"] == VERIFY_REASON_SCHEMA_INVALID
    explanation = payload["explanation"][0]  # type: ignore[index]
    assert explanation["primary_reason"] == VERIFY_REASON_SCHEMA_INVALID
    assert explanation["pointer"] == "/"
    assert str(bundle) in explanation["message"]
    reason = payload["reasons"][0]  # type: ignore[index]
    assert reason["code"] == VERIFY_REASON_SCHEMA_INVALID
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
    assert payload["reason_code"] == VERIFY_REASON_SCHEMA_INVALID
    assert payload["taxonomy_version"] == 1
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
    assert payload["reason_code"] == VERIFY_REASON_STRUCTURE_INVALID
    assert payload["taxonomy_version"] == 1
    reason = payload["reasons"][0]  # type: ignore[index]
    assert reason["code"] == VERIFY_REASON_STRUCTURE_INVALID
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
    assert payload["reason_code"] == VERIFY_REASON_SCHEMA_INVALID
    assert payload["taxonomy_version"] == 1
    reason = payload["reasons"][0]  # type: ignore[index]
    assert reason["code"] == VERIFY_REASON_SCHEMA_INVALID
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
    assert payload["reason_code"] == VERIFY_REASON_SCHEMA_INVALID
    assert payload["taxonomy_version"] == 1
    reason = payload["reasons"][0]  # type: ignore[index]
    assert reason["code"] == VERIFY_REASON_SCHEMA_INVALID
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
    assert reason["code"] == VERIFY_REASON_SCHEMA_UNKNOWN
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
            "code": VERIFY_REASON_SCHEMA_UNKNOWN,
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
