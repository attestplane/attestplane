# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main

ROOT = Path(__file__).resolve().parents[2]
VECTOR_PATH = ROOT / "tests" / "conformance" / "verify_taxonomy_version_vectors.json"


@pytest.mark.parametrize(
    "vector",
    json.loads(VECTOR_PATH.read_text(encoding="utf-8"))["cases"],
    ids=lambda vector: vector["case_id"],
)
def test_verify_require_taxonomy_version_vectors(
    vector: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = ROOT / str(vector["bundle_path"])
    rc = main(
        [
            "verify",
            "--require-taxonomy-version",
            str(vector["require_taxonomy_version"]),
            str(bundle),
        ]
    )
    captured = capsys.readouterr()

    assert rc == vector["expected_rc"]
    assert captured.err == str(vector["expected_stderr"])
    expected_prefix = "OK" if vector["expected_result"] == "pass" else "FAIL"
    assert captured.out.startswith(f"{expected_prefix} ")
    if vector["expected_result"] == "pass":
        assert captured.err == ""
    if vector["expected_result"] == "fail":
        assert "primary_reason=att.verify.taxonomy_version_mismatch" in captured.out
        assert "taxonomy_version_reason='taxonomy_version=1 does not match required taxonomy_version=2'" in captured.out
        assert "required taxonomy_version=2" in captured.out
