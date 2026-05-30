# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Conformance vectors for ``attestplane verify --require-taxonomy-version``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verify_reason_codes import (
    VERIFY_REASON_SCHEMA_VERSION_MISSING,
    VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
)

ROOT = Path(__file__).resolve().parents[2]
MATCHING_BUNDLE = (
    ROOT
    / "tests"
    / "conformance"
    / "schema_version"
    / "additive_minor_ok"
    / "bundle.json"
)

REQUIRE_TAXONOMY_VERSION_VECTORS = [
    {
        "case_id": "require_taxonomy_version_missing",
        "bundle_path": MATCHING_BUNDLE,
        "mutate": "remove_taxonomy_version",
        "require_taxonomy_version": 1,
        "expected_exit_code": 2,
        "expected_reason_code": VERIFY_REASON_SCHEMA_VERSION_MISSING,
    },
    {
        "case_id": "require_taxonomy_version_mismatch",
        "bundle_path": MATCHING_BUNDLE,
        "require_taxonomy_version": 2,
        "expected_exit_code": 2,
        "expected_reason_code": VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
    },
]


def test_require_taxonomy_version_vector_set_is_complete() -> None:
    assert {vector["case_id"] for vector in REQUIRE_TAXONOMY_VERSION_VECTORS} == {
        "require_taxonomy_version_missing",
        "require_taxonomy_version_mismatch",
    }


def test_require_taxonomy_version_matching_bundle_passes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(
        ["verify", "--json", str(MATCHING_BUNDLE), "--require-taxonomy-version", "1"]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert captured.err == ""
    assert payload["schema_version"] == 1
    assert payload["result"] == "pass"
    assert payload["exit_code"] == 0
    assert payload["reason_code"] is None
    assert payload["reasons"] == []


def _materialize_bundle(vector: dict[str, object], tmp_path: Path) -> Path:
    payload = json.loads(Path(vector["bundle_path"]).read_text(encoding="utf-8"))
    if vector.get("mutate") == "remove_taxonomy_version":
        del payload["chain_metadata"]["evidence_taxonomy_version"]
    path = tmp_path / f"{vector['case_id']}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "vector", REQUIRE_TAXONOMY_VERSION_VECTORS, ids=lambda vector: vector["case_id"]
)
def test_require_taxonomy_version_negative_vector(
    vector: dict[str, object],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle_path = _materialize_bundle(vector, tmp_path)
    rc = main(
        [
            "verify",
            "--json",
            str(bundle_path),
            "--require-taxonomy-version",
            str(vector["require_taxonomy_version"]),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == vector["expected_exit_code"]
    assert captured.err == ""
    assert payload["schema_version"] == 1
    assert payload["result"] == "fail"
    assert payload["exit_code"] == vector["expected_exit_code"]
    assert payload["reason_code"] == vector["expected_reason_code"]
    assert payload["reasons"][0]["code"] == vector["expected_reason_code"]
    assert payload["reasons"][0]["path"] == "/chain_metadata/evidence_taxonomy_version"
