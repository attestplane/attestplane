# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Conformance vectors for ``attestplane verify --require-taxonomy-version``."""

from __future__ import annotations

import json
import importlib.util
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verifier import verify_proof_bundle
from attestplane.verify_reason_codes import VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED

_VECTOR_HELPER_PATH = Path(__file__).with_name("require_taxonomy_version_vectors.py")


def _load_vectors() -> list[dict[str, object]]:
    module_name = "attestplane_require_taxonomy_version_vectors"
    spec = importlib.util.spec_from_file_location(module_name, _VECTOR_HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"could not load taxonomy version vectors from {_VECTOR_HELPER_PATH}"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.REQUIRE_TAXONOMY_VERSION_VECTORS)


REQUIRE_TAXONOMY_VERSION_VECTORS = _load_vectors()


def test_require_taxonomy_version_vector_set_is_complete() -> None:
    assert {vector["case_id"] for vector in REQUIRE_TAXONOMY_VERSION_VECTORS} == {
        "require_taxonomy_version_match",
        "require_taxonomy_version_mismatch",
    }


@pytest.mark.parametrize(
    "vector", REQUIRE_TAXONOMY_VERSION_VECTORS, ids=lambda vector: vector["case_id"]
)
def test_require_taxonomy_version_vectors(
    vector: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = json.loads(Path(vector["bundle_path"]).read_text(encoding="utf-8"))
    sdk_result = verify_proof_bundle(
        bundle, require_taxonomy_version=int(vector["require_taxonomy_version"])
    )

    rc = main(
        [
            "verify",
            "--json",
            str(vector["bundle_path"]),
            "--require-taxonomy-version",
            str(vector["require_taxonomy_version"]),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == vector["expected_exit_code"]
    assert captured.err == ""
    assert payload["schema_version"] == 1
    assert payload["exit_code"] == vector["expected_exit_code"]
    if vector["expected_exit_code"] == 0:
        assert sdk_result.ok is True
        assert sdk_result.primary_reason is None
        assert payload["result"] == "pass"
        assert payload["reason_code"] is None
        assert payload["reasons"] == []
    else:
        assert sdk_result.ok is False
        assert sdk_result.primary_reason == VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED
        assert payload["result"] == "fail"
        assert payload["reason_code"] == vector["expected_reason_code"]
        assert payload["reasons"][0]["code"] == vector["expected_reason_code"]
        assert (
            payload["reasons"][0]["path"] == "/chain_metadata/evidence_taxonomy_version"
        )
