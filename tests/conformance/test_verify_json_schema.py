# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import re
from pathlib import Path

from attestplane.cli.main import main
from attestplane.cli.verify_json import (
    VERIFY_JSON_EXIT_CODE_PINNING_GATE_FAILURE,
    VERIFY_JSON_EXIT_CODE_USAGE_ERROR,
    VERIFY_JSON_EXIT_CODE_VERIFIED,
    VERIFY_JSON_EXIT_CODE_VERIFICATION_FAILURE,
)
from attestplane.verify_reason_codes import (
    ALL_VERIFY_REASON_CODES_V1,
    VERIFY_REASON_TAXONOMY_VERSION,
    VERIFY_REASON_SCHEMA_UNKNOWN,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "cli" / "verify-result-v1.json"
CONFORMANCE_FIXTURES = ROOT / "fixtures" / "conformance"
OUTPUT_CONTRACT_FIXTURES = ROOT / "tests" / "conformance" / "fixtures"
VERIFY_JSON_OUTPUT_CONTRACT_VERSION = "1.8.19"
PASS_FIXTURE = CONFORMANCE_FIXTURES / "baseline.att"
PASS_GOLDEN_FIXTURE = OUTPUT_CONTRACT_FIXTURES / "verify_json_pass.golden"
FAIL_GOLDEN_FIXTURE = OUTPUT_CONTRACT_FIXTURES / "verify_json_fail.golden"
VERSIONED_GOLDEN_FIXTURE = (
    CONFORMANCE_FIXTURES
    / "golden"
    / f"verify_json_v{VERIFY_JSON_OUTPUT_CONTRACT_VERSION}.json"
)
FAIL_FIXTURE = ROOT / "fixtures" / "reject" / "canonicalization-edge.json"
UNKNOWN_REQUIRED_FIXTURE = CONFORMANCE_FIXTURES / "unknown_required_field.att"
ROOT_QUARANTINE_FIXTURE = ROOT / "fixtures" / "quarantined.bundle"


def _schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _payload(argv: list[str], capsys) -> tuple[int, str]:
    rc = main(argv)
    assert rc in {
        VERIFY_JSON_EXIT_CODE_VERIFIED,
        VERIFY_JSON_EXIT_CODE_VERIFICATION_FAILURE,
        VERIFY_JSON_EXIT_CODE_PINNING_GATE_FAILURE,
        VERIFY_JSON_EXIT_CODE_USAGE_ERROR,
    }
    return rc, capsys.readouterr().out


def _payload_json(argv: list[str], capsys) -> tuple[int, dict[str, object]]:
    rc, stdout = _payload(argv, capsys)
    return rc, json.loads(stdout)


def _assert_matches_verify_result_v1(payload: dict[str, object]) -> None:
    schema = _schema()
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
        "anchoring",
    ]

    expected_keys = {
        "schema_version",
        "result",
        "exit_code",
        "reason_code",
        "taxonomy_version",
        "reasons",
        "bundle",
        "anchoring",
    }
    if "explanation" in payload:
        expected_keys.add("explanation")

    assert set(payload) == expected_keys
    assert payload["schema_version"] == 1
    assert payload["result"] in {"pass", "fail"}
    assert isinstance(payload["exit_code"], int)
    assert payload["exit_code"] in {
        VERIFY_JSON_EXIT_CODE_VERIFIED,
        VERIFY_JSON_EXIT_CODE_VERIFICATION_FAILURE,
        VERIFY_JSON_EXIT_CODE_PINNING_GATE_FAILURE,
        VERIFY_JSON_EXIT_CODE_USAGE_ERROR,
    }
    assert payload["taxonomy_version"] == VERIFY_REASON_TAXONOMY_VERSION
    assert payload["reason_code"] is None or re.fullmatch(
        r"att\.verify\.[a-z][a-z0-9_]*",
        str(payload["reason_code"]),
    )
    assert isinstance(payload["reasons"], list)
    if "explanation" in payload:
        explanation = payload["explanation"]
        assert isinstance(explanation, list)
        for entry in explanation:
            assert isinstance(entry, dict)
            assert set(entry) == {"primary_reason", "pointer", "message"}
            assert entry["pointer"]
            assert entry["message"]

    bundle = payload["bundle"]
    assert isinstance(bundle, dict)
    assert set(bundle) == {"schema_version", "digest"}
    assert bundle["schema_version"] == 1
    assert re.fullmatch(r"[0-9a-f]{64}", str(bundle["digest"]))

    anchoring = payload["anchoring"]
    assert isinstance(anchoring, dict)
    assert set(anchoring) == {"status", "quarantined"}
    assert anchoring["status"] in {"anchored", "quarantined", "unanchored"}
    assert isinstance(anchoring["quarantined"], bool)

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


def test_verify_result_schema_is_valid_draft_2020_12() -> None:
    schema = _schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema_version"]["const"] == 1
    assert schema["properties"]["result"]["enum"] == ["pass", "fail"]
    assert schema["properties"]["exit_code"]["minimum"] == 0
    assert (
        schema["properties"]["exit_code"]["maximum"]
        == VERIFY_JSON_EXIT_CODE_USAGE_ERROR
    )
    assert "verify --json" in schema["properties"]["taxonomy_version"]["description"]
    assert schema["properties"]["reasons"]["items"]["additionalProperties"] is False
    assert schema["properties"]["bundle"]["additionalProperties"] is False
    assert schema["properties"]["anchoring"]["additionalProperties"] is False
    assert schema["properties"]["anchoring"]["properties"]["status"]["enum"] == [
        "anchored",
        "quarantined",
        "unanchored",
    ]


def test_verify_json_output_contract_version_is_explicit() -> None:
    assert VERSIONED_GOLDEN_FIXTURE.exists()
    assert (
        VERSIONED_GOLDEN_FIXTURE.name
        == f"verify_json_v{VERIFY_JSON_OUTPUT_CONTRACT_VERSION}.json"
    )
    assert VERSIONED_GOLDEN_FIXTURE.read_text(
        encoding="utf-8"
    ) == PASS_GOLDEN_FIXTURE.read_text(encoding="utf-8")


def test_verify_json_output_contract_matches_versioned_golden_fixture(capsys) -> None:
    rc, stdout = _payload(["verify", "--json", str(PASS_FIXTURE)], capsys)
    assert rc == VERIFY_JSON_EXIT_CODE_VERIFIED
    assert stdout == PASS_GOLDEN_FIXTURE.read_text(encoding="utf-8")
    payload = json.loads(stdout)
    _assert_matches_verify_result_v1(payload)
    assert payload["anchoring"] == {"status": "unanchored", "quarantined": False}


def test_verify_json_fail_payload_matches_schema(capsys) -> None:
    rc, stdout = _payload(["verify", "--json", str(FAIL_FIXTURE)], capsys)
    assert rc == VERIFY_JSON_EXIT_CODE_VERIFICATION_FAILURE
    assert stdout == FAIL_GOLDEN_FIXTURE.read_text(encoding="utf-8")
    payload = json.loads(stdout)
    _assert_matches_verify_result_v1(payload)
    assert payload["reasons"] == [
        {
            "code": "att.verify.canonical_mismatch",
            "message": "canonicalization failed",
            "path": "/events/0/event/payload/artifact_ref",
        },
    ]


def test_verify_json_unknown_required_field_is_quarantined(capsys) -> None:
    rc, payload = _payload_json(
        ["verify", "--json", str(ROOT_QUARANTINE_FIXTURE)], capsys
    )
    assert rc == VERIFY_JSON_EXIT_CODE_PINNING_GATE_FAILURE
    _assert_matches_verify_result_v1(payload)
    assert payload["result"] == "fail"
    assert payload["exit_code"] == VERIFY_JSON_EXIT_CODE_PINNING_GATE_FAILURE
    assert payload["reason_code"] == VERIFY_REASON_SCHEMA_UNKNOWN
    assert payload["reasons"][0]["code"] == VERIFY_REASON_SCHEMA_UNKNOWN
    assert payload["reasons"][0]["path"] == "/chain_metadata/critical_future_field"
    assert payload["anchoring"] == {"status": "quarantined", "quarantined": True}


def test_verify_reason_code_parity_vector_for_canonicalization_edge_bundle(
    capsys,
) -> None:
    rc, payload = _payload_json(["verify", "--json", str(FAIL_FIXTURE)], capsys)
    assert rc == VERIFY_JSON_EXIT_CODE_VERIFICATION_FAILURE
    _assert_matches_verify_result_v1(payload)
    json_reason_codes = [reason["code"] for reason in payload["reasons"]]
    assert json_reason_codes
    assert all(code in ALL_VERIFY_REASON_CODES_V1 for code in json_reason_codes)
    reason_code = payload["reason_code"]
    assert isinstance(reason_code, str)
    assert reason_code == json_reason_codes[0]

    rc = main(["verify", "--explain", str(FAIL_FIXTURE)])
    captured = capsys.readouterr()

    assert rc == VERIFY_JSON_EXIT_CODE_VERIFICATION_FAILURE
    assert captured.out.startswith("FAIL")
    explain_reason_codes = [line.split(" ", 1)[0] for line in captured.err.splitlines()]
    assert explain_reason_codes == json_reason_codes
    first_reason = payload["reasons"][0]
    assert isinstance(first_reason, dict)
    assert captured.err.splitlines()[0].startswith(
        f"{reason_code} {first_reason['path']}: "
    )
