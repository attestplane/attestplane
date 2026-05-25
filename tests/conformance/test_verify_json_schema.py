# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

from attestplane.cli.main import main
from attestplane.cli.verify_json import (
    VERIFY_JSON_ERROR_CANON_MISMATCH,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "cli" / "verify-result-v1.json"
PASS_FIXTURE = ROOT / "fixtures" / "positive" / "minimal.json"
FAIL_FIXTURE = ROOT / "fixtures" / "reject" / "canonicalization-edge.json"


def _schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _payload(argv: list[str], capsys) -> dict[str, object]:
    rc = main(argv)
    assert rc in {0, 1, 2}
    out = capsys.readouterr().out
    assert out.count("\n") == 1
    return json.loads(out)


def _assert_matches_verify_result_v1(payload: dict[str, object]) -> None:
    schema = _schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["additionalProperties"] is False
    assert schema["required"] == [
        "schema_version",
        "result",
        "failed_gates",
    ]

    expected_keys = {
        "schema_version",
        "result",
        "failed_gates",
    }
    if "explanation" in payload:
        expected_keys.add("explanation")
    if "bundle_id" in payload:
        expected_keys.add("bundle_id")
    if "vector_id" in payload:
        expected_keys.add("vector_id")

    assert set(payload) == expected_keys
    assert payload["schema_version"] == 1
    assert payload["result"] in {"pass", "fail"}
    assert isinstance(payload["failed_gates"], list)
    if "explanation" in payload:
        explanation = payload["explanation"]
        assert isinstance(explanation, list)
        for entry in explanation:
            assert isinstance(entry, dict)
            assert set(entry) == {"primary_reason", "pointer", "message"}
            assert entry["pointer"]
            assert entry["message"]
    for gate in payload["failed_gates"]:
        assert isinstance(gate, dict)
        assert set(gate) == {"gate", "error_code"}
        assert gate["gate"] in {"non_empty", "strict_schema", "canonicalization", "signature"}
        assert gate["error_code"] in {
            "E_EMPTY_BUNDLE",
            "E_SCHEMA_INVALID",
            "E_CANON_MISMATCH",
            "E_SIGNATURE_INVALID",
        }


def test_verify_result_schema_is_valid_draft_2020_12() -> None:
    schema = _schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema_version"]["const"] == 1
    assert schema["properties"]["result"]["enum"] == ["pass", "fail"]
    assert schema["properties"]["failed_gates"]["items"]["additionalProperties"] is False


def test_verify_json_pass_payload_matches_schema(capsys) -> None:
    payload = _payload(["verify", "--json", str(PASS_FIXTURE)], capsys)
    _assert_matches_verify_result_v1(payload)
    assert payload["failed_gates"] == []
    assert payload["bundle_id"] == "p3-cli-proofbundle"


def test_verify_json_fail_payload_matches_schema(capsys) -> None:
    payload = _payload(["verify", "--json", "--explain", str(FAIL_FIXTURE)], capsys)
    _assert_matches_verify_result_v1(payload)
    assert payload["failed_gates"] == [
        {"gate": "canonicalization", "error_code": VERIFY_JSON_ERROR_CANON_MISMATCH}
    ]


def test_verify_failed_gate_parity_vector_for_canonicalization_edge_bundle(
    capsys,
) -> None:
    payload = _payload(["verify", "--json", str(FAIL_FIXTURE)], capsys)
    _assert_matches_verify_result_v1(payload)
    failed_gates = payload["failed_gates"]
    assert failed_gates == [
        {"gate": "canonicalization", "error_code": VERIFY_JSON_ERROR_CANON_MISMATCH}
    ]

    rc = main(["verify", "--explain", str(FAIL_FIXTURE)])
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out.startswith("FAIL")
    assert captured.err.splitlines()[0].startswith(
        "att.verify.canonical_mismatch /events/0/event/payload/artifact_ref: "
    )
