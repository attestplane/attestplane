# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Conformance coverage for ``--require-taxonomy-version`` pinning."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verifier import verify_proof_bundle
from attestplane.verify_errors import VERIFY_METADATA_CLOSURE_FAILED, VERIFY_OK

ROOT = Path(__file__).resolve().parents[2]
VECTORS_PATH = ROOT / "tests" / "conformance" / "require_taxonomy_version_vectors.json"


def _vectors() -> list[dict[str, object]]:
    return list(json.loads(VECTORS_PATH.read_text(encoding="utf-8"))["cases"])


def _bundle_path(vector: dict[str, object]) -> Path:
    return ROOT / str(vector["bundle_path"])


@pytest.mark.parametrize("vector", _vectors(), ids=lambda vector: str(vector["case_id"]))
def test_require_taxonomy_version_vectors_pin_acceptance_and_rejection(
    vector: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle_path = _bundle_path(vector)
    require_taxonomy_version = int(vector["require_taxonomy_version"])

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    result = verify_proof_bundle(
        bundle,
        require_taxonomy_version=require_taxonomy_version,
    )

    assert result.ok is vector["expected_ok"]
    assert result.primary_reason == vector["expected_primary_reason"]
    assert result.error_code == vector["expected_error_code"]
    if result.ok:
        assert result.error_code == VERIFY_OK
    else:
        assert result.error_code == VERIFY_METADATA_CLOSURE_FAILED

    rc = main(
        [
            "verify",
            "--require-taxonomy-version",
            str(require_taxonomy_version),
            str(bundle_path),
        ]
    )
    capsys.readouterr()

    assert rc == vector["expected_exit_code"]
