# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import re
from pathlib import Path

from attestplane.cli.main import main
from attestplane.verify_reason_codes import (
    ALL_VERIFY_REASON_CODES_V1,
    VERIFY_REASON_TAXONOMY_VERSION,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "cli" / "verify-result-v1.json"
PASS_FIXTURE = ROOT / "fixtures" / "positive" / "minimal.json"
FAIL_FIXTURE = ROOT / "fixtures" / "reject" / "canonicalization-edge.json"


def _schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _payload(argv: list[str], capsys) -> dict[str, object]:
    rc = main(argv)
    assert rc in {0, 1, 2, 3}
    return json.loads(capsys.readouterr().out)


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
    if "explanation" in payload:
        expected_keys.add("explanation")

    assert set(payload) == expected_keys
    assert payload["schema_version"] == 1
    assert payload["result"] in {"pass", "fail"}
    assert isinstance(payload["exit_code"], int)
    assert payload["exit_code"] >= 0
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
    assert schema["properties"]["exit_code"]["enum"] == [0, 1, 2, 3]
    assert schema["properties"]["reasons"]["items"]["additionalProperties"] is False
    assert schema["properties"]["bundle"]["additionalProperties"] is False


def test_verify_json_pass_payload_matches_schema(capsys) -> None:
    payload = _payload(["verify", "--json", str(PASS_FIXTURE)], capsys)
    _assert_matches_verify_result_v1(payload)


def test_verify_json_fail_payload_matches_schema(capsys) -> None:
    payload = _payload(["verify", "--json", "--explain", str(FAIL_FIXTURE)], capsys)
    _assert_matches_verify_result_v1(payload)


def test_verify_reason_code_parity_vector_for_canonicalization_edge_bundle(
    capsys,
) -> None:
    payload = _payload(["verify", "--json", str(FAIL_FIXTURE)], capsys)
    _assert_matches_verify_result_v1(payload)
    json_reason_codes = [reason["code"] for reason in payload["reasons"]]
    assert json_reason_codes
    assert all(code in ALL_VERIFY_REASON_CODES_V1 for code in json_reason_codes)
    reason_code = payload["reason_code"]
    assert isinstance(reason_code, str)
    assert reason_code == json_reason_codes[0]

    rc = main(["verify", "--explain", str(FAIL_FIXTURE)])
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out.startswith("FAIL")
    explain_reason_codes = [line.split(" ", 1)[0] for line in captured.err.splitlines()]
    assert explain_reason_codes == json_reason_codes
    first_reason = payload["reasons"][0]
    assert isinstance(first_reason, dict)
    assert captured.err.splitlines()[0].startswith(
        f"{reason_code} {first_reason['path']}: "
    )
