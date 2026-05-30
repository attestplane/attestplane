# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Conformance coverage for `verify --require-taxonomy-version` pinning."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main

ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = ROOT.parents[1]
VECTORS = json.loads(
    (ROOT / "tests" / "conformance" / "taxonomy_version_pin_vectors.json").read_text(encoding="utf-8")
)["cases"]


@pytest.mark.parametrize("case", VECTORS, ids=lambda case: str(case["case_id"]))
def test_taxonomy_version_pin_vectors(case: dict[str, object], capsys: pytest.CaptureFixture[str]) -> None:
    bundle_path = REPO_ROOT / str(case["path"])
    argv = [
        "verify",
        "--json",
        "--require-taxonomy-version",
        str(case["require_taxonomy_version"]),
        str(bundle_path),
    ]

    rc = main(argv)
    payload = json.loads(capsys.readouterr().out)

    assert rc == case["expected_exit_code"]
    assert payload["schema_version"] == 1
    assert payload["taxonomy_version"] == 1
    assert payload["result"] == ("pass" if case["expected_ok"] else "fail")
    assert payload["exit_code"] == case["expected_exit_code"]
    assert payload["reason_code"] == case["expected_reason_code"]
    if case["expected_ok"]:
        assert payload["reasons"] == []
    else:
        assert payload["reasons"] == [
            {
                "code": "att.verify.taxonomy_version_unsupported",
                "path": "/",
                "message": payload["reasons"][0]["message"],
            }
        ]
