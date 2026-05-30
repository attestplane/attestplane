# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main

ROOT = Path(__file__).resolve().parents[2]
VECTORS_PATH = ROOT / "tests" / "conformance" / "taxonomy_version" / "vectors.json"


@pytest.mark.parametrize(
    "vector",
    json.loads(VECTORS_PATH.read_text(encoding="utf-8"))["cases"],
    ids=lambda vector: vector["case_id"],
)
def test_require_taxonomy_version_vectors(
    vector: dict[str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = ROOT / str(vector["bundle"])
    rc = main(
        [
            "verify",
            "--json",
            "--require-taxonomy-version",
            str(vector["require_taxonomy_version"]),
            str(bundle),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == vector["expected_exit_code"]
    assert payload["schema_version"] == 1
    assert payload["exit_code"] == vector["expected_exit_code"]
    assert payload["result"] == ("pass" if vector["expected_ok"] else "fail")
    assert payload["reason_code"] == vector["expected_reason_code"]
    assert payload["taxonomy_version"] == 1
    assert captured.err == ""
