# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk" / "python" / "src"))
sys.path.insert(0, str(ROOT / "tests" / "conformance"))

from attestplane.cli.main import main

from require_taxonomy_version_vectors import VECTORS


@pytest.mark.parametrize("vector", VECTORS, ids=lambda vector: vector["case_id"])
def test_require_taxonomy_version_vectors(
    vector: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(
        [
            "verify",
            "--json",
            "--require-taxonomy-version",
            str(vector["require_taxonomy_version"]),
            str(vector["bundle_path"]),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == vector["expected_exit_code"]
    assert payload["schema_version"] == 1
    assert payload["exit_code"] == vector["expected_exit_code"]
    assert payload["result"] == ("pass" if vector["expected_exit_code"] == 0 else "fail")
    assert payload["reason_code"] == vector["expected_reason_code"]
    assert captured.err == ""
