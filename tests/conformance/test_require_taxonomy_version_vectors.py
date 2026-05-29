# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verify_errors import VERIFY_TAXONOMY_VERSION_UNSUPPORTED
from attestplane.verify_reason_codes import VERIFY_REASON_TAXONOMY_VERSION_UNSUPPORTED

ROOT = Path(__file__).resolve().parents[2]
VECTOR_PATH = (
    ROOT
    / "tests"
    / "conformance"
    / "vectors"
    / "verify_taxonomy_version"
    / "negative"
    / "require-taxonomy-version-mismatch.json"
)


def _vectors() -> list[dict[str, object]]:
    return json.loads(VECTOR_PATH.read_text(encoding="utf-8"))["cases"]


def test_require_taxonomy_version_vector_set_is_complete() -> None:
    assert {vector["case_id"] for vector in _vectors()} == {"require-taxonomy-version-mismatch"}


@pytest.mark.parametrize("vector", _vectors(), ids=lambda vector: vector["case_id"])
def test_require_taxonomy_version_negative_vector_pins_rejection(
    vector: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle_path = ROOT / str(vector["bundle"])
    required_version = int(vector["verify_options"]["required_taxonomy_version"])

    rc = main(
        [
            "verify",
            "--json",
            "--require-taxonomy-version",
            str(required_version),
            str(bundle_path),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == vector["expected_exit_code"]
    assert payload["schema_version"] == 1
    assert payload["result"] == "fail"
    assert payload["exit_code"] == vector["expected_exit_code"]
    assert payload["reason_code"] == VERIFY_REASON_TAXONOMY_VERSION_UNSUPPORTED
    assert payload["taxonomy_version"] == 1
    assert payload["reasons"][0]["code"] == VERIFY_REASON_TAXONOMY_VERSION_UNSUPPORTED
    assert captured.err == f"{VERIFY_TAXONOMY_VERSION_UNSUPPORTED}\n"
