# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""CI-gated golden tests for ``attestplane verify --json``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main

ROOT = Path(__file__).resolve().parents[2]
PASS_FIXTURE = ROOT / "fixtures" / "positive" / "minimal.json"
FAIL_FIXTURE = ROOT / "fixtures" / "reject" / "canonicalization-edge.json"
SCHEMA_PATH = ROOT / "schemas" / "cli" / "verify-result-v1.json"

EXPECTED_TOP_LEVEL_KEYS = {
    "schema_version",
    "result",
    "exit_code",
    "reason_code",
    "taxonomy_version",
    "reasons",
    "bundle",
}
EXPECTED_REASON_KEYS = {"code", "path", "message"}
EXPECTED_BUNDLE_KEYS = {"schema_version", "digest"}

PASS_GOLDEN = {
    "schema_version": 1,
    "result": "pass",
    "exit_code": 0,
    "reason_code": None,
    "taxonomy_version": 1,
    "reasons": [],
    "bundle": {
        "schema_version": 1,
        "digest": "d4d37025f7452ad2525d6b37c898bf08cd335db3e7983ce04e242e898b77b2cb",
    },
}

FAIL_GOLDEN = {
    "schema_version": 1,
    "result": "fail",
    "exit_code": 1,
    "reason_code": "att.verify.canonical_mismatch",
    "taxonomy_version": 1,
    "reasons": [
        {
            "code": "att.verify.canonical_mismatch",
            "path": "/events/0/event/payload/artifact_ref",
            "message": "canonicalization failed",
        }
    ],
    "bundle": {
        "schema_version": 1,
        "digest": "914bdd3745f9566e4cf0c3c2dd2747b701f50ad4cb3dc0eeede5f16207748ffd",
    },
}


def _run_verify_json(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, object], str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, json.loads(captured.out), captured.err


def _assert_schema_shape(payload: dict[str, object]) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

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

    actual_top_level_keys = set(payload)
    assert actual_top_level_keys == EXPECTED_TOP_LEVEL_KEYS

    bundle = payload["bundle"]
    assert isinstance(bundle, dict)
    assert set(bundle) == EXPECTED_BUNDLE_KEYS

    for reason in payload["reasons"]:
        assert isinstance(reason, dict)
        assert set(reason) == EXPECTED_REASON_KEYS


@pytest.mark.parametrize(
    ("fixture", "expected_exit_code", "expected_golden"),
    [
        (PASS_FIXTURE, 0, PASS_GOLDEN),
        (FAIL_FIXTURE, 1, FAIL_GOLDEN),
    ],
)
def test_verify_json_contract_matches_golden_fixture(
    fixture: Path,
    expected_exit_code: int,
    expected_golden: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, stderr = _run_verify_json(["verify", "--json", str(fixture)], capsys)

    assert rc == expected_exit_code
    assert stderr == ""
    assert payload == expected_golden


@pytest.mark.parametrize(
    ("fixture", "expected_exit_code"),
    [
        (PASS_FIXTURE, 0),
        (FAIL_FIXTURE, 1),
    ],
)
def test_verify_json_contract_shape_is_frozen(
    fixture: Path,
    expected_exit_code: int,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, stderr = _run_verify_json(["verify", "--json", str(fixture)], capsys)

    assert rc == expected_exit_code
    assert stderr == ""
    _assert_schema_shape(payload)

