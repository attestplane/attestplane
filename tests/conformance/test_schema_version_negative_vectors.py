# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main

ROOT = Path(__file__).resolve().parents[2]
VECTOR_DIR = ROOT / "tests" / "conformance" / "vectors" / "schema_version" / "negative"
FIXTURES = ROOT / "tests" / "fixtures" / "bundles"


def _vectors() -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(VECTOR_DIR.glob("*.json"))
    ]


def _apply_mutation(bundle: dict, mutation: dict) -> dict:
    mutated = json.loads(json.dumps(bundle))
    for field in mutation.get("remove_top_level_fields", []):
        mutated.pop(field, None)
    for key, value in mutation.get("set_top_level_fields", {}).items():
        mutated[key] = value
    for key, value in mutation.get("add_top_level_fields", {}).items():
        mutated[key] = value
    return mutated


@pytest.mark.parametrize("vector", _vectors(), ids=lambda vector: vector["case_id"])
def test_schema_version_negative_vectors(vector: dict, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base_bundle = json.loads((FIXTURES / vector["bundle_fixture"]).read_text(encoding="utf-8"))
    bundle = _apply_mutation(base_bundle, vector["mutation"])
    bundle_path = tmp_path / f"{vector['case_id']}.json"
    bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    rc = main(["verify", "--json", str(bundle_path)])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert payload["result"] == "reject"
    assert payload["schema_version_forward_compat"] is False
    assert payload["ok"] is vector["expected_ok"]
    assert payload["error_code"] == vector["expected_error_code"]
    assert payload["primary_reason"] == vector["expected_primary_reason"]
    assert list(payload["secondary_reasons"]) == vector["expected_secondary_reasons"]
    assert vector["expected_detail_label"] in payload["detail"]


@pytest.mark.parametrize("vector", _vectors(), ids=lambda vector: vector["case_id"])
def test_schema_version_negative_vectors_explain(vector: dict, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base_bundle = json.loads((FIXTURES / vector["bundle_fixture"]).read_text(encoding="utf-8"))
    bundle = _apply_mutation(base_bundle, vector["mutation"])
    bundle_path = tmp_path / f"{vector['case_id']}.json"
    bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    rc = main(["verify", "--explain", str(bundle_path)])
    out = capsys.readouterr().out

    assert rc == 2
    assert vector["expected_detail_label"] in out
