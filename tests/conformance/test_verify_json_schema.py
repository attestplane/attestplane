# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import re
from pathlib import Path

from attestplane.cli.main import main

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "cli" / "verify-result-v1.json"
PASS_FIXTURE = ROOT / "fixtures" / "positive" / "minimal.json"
FAIL_FIXTURE = ROOT / "fixtures" / "negative" / "non_nfc_bundle.json"


def _schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _payload(argv: list[str], capsys) -> dict[str, object]:
    rc = main(argv)
    assert rc in {0, 1, 2}
    return json.loads(capsys.readouterr().out)


def _assert_matches_verify_result_v1(payload: dict[str, object]) -> None:
    schema = _schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["schema_version", "result", "exit_code", "reasons", "bundle"]

    assert set(payload) == {"schema_version", "result", "exit_code", "reasons", "bundle"}
    assert payload["schema_version"] == 1
    assert payload["result"] in {"pass", "fail"}
    assert isinstance(payload["exit_code"], int)
    assert payload["exit_code"] >= 0
    assert isinstance(payload["reasons"], list)

    bundle = payload["bundle"]
    assert isinstance(bundle, dict)
    assert set(bundle) == {"schema_version", "digest"}
    assert bundle["schema_version"] == 1
    assert re.fullmatch(r"[0-9a-f]{64}", str(bundle["digest"]))

    for reason in payload["reasons"]:
        assert isinstance(reason, dict)
        expected_keys = {"code", "reason_code", "reason_code_version", "path", "message"}
        if "explanation" in reason:
            expected_keys.add("explanation")
        assert set(reason) == expected_keys
        assert re.fullmatch(r"att\.verify\.[a-z][a-z0-9_]*", str(reason["code"]))
        assert reason["reason_code"] == reason["code"]
        assert reason["reason_code_version"] == "rc.v1"
        assert reason["path"]
        assert reason["message"]
        if "explanation" in reason:
            assert reason["explanation"]


def test_verify_result_schema_is_valid_draft_2020_12() -> None:
    schema = _schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema_version"]["const"] == 1
    assert schema["properties"]["result"]["enum"] == ["pass", "fail"]
    assert schema["properties"]["reasons"]["items"]["additionalProperties"] is False
    assert schema["properties"]["bundle"]["additionalProperties"] is False
    assert schema["properties"]["reasons"]["items"]["required"] == [
        "code",
        "reason_code",
        "reason_code_version",
        "path",
        "message",
    ]
    assert schema["properties"]["reasons"]["items"]["properties"]["reason_code_version"]["const"] == "rc.v1"


def test_verify_json_pass_payload_matches_schema(capsys) -> None:
    payload = _payload(["verify", "--json", str(PASS_FIXTURE)], capsys)
    _assert_matches_verify_result_v1(payload)


def test_verify_json_fail_payload_matches_schema(capsys) -> None:
    payload = _payload(["verify", "--json", "--explain", str(FAIL_FIXTURE)], capsys)
    _assert_matches_verify_result_v1(payload)
