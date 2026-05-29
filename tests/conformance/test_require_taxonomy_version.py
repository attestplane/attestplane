# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Coverage for ``attestplane verify --require-taxonomy-version``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verifier import verify_proof_bundle
from attestplane.verify_reason_codes import VERIFY_REASON_TAXONOMY_VERSION

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures" / "conformance"
PASS_FIXTURE = FIXTURES / "with_taxonomy.attest"
FAIL_FIXTURE = FIXTURES / "taxonomy_mismatch.attest"
SCHEMA_VERSION_DIR = ROOT / "tests" / "conformance" / "schema_version"
SCHEMA_VERSION_VECTORS = json.loads(
    (SCHEMA_VERSION_DIR / "vectors.json").read_text(encoding="utf-8")
)["cases"]


def _run_verify(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, object], str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, json.loads(captured.out), captured.err


def test_require_taxonomy_version_vector_set_is_complete() -> None:
    case_ids = {str(vector["case_id"]) for vector in SCHEMA_VERSION_VECTORS}
    assert "taxonomy_version_mismatch" in case_ids


def test_require_taxonomy_version_negative_vector_rejects_mismatch() -> None:
    bundle = json.loads(FAIL_FIXTURE.read_text(encoding="utf-8"))

    result = verify_proof_bundle(bundle, require_taxonomy_version=2)

    assert result.ok is False
    assert result.primary_reason == "att.verify.taxonomy_version_mismatch"
    assert result.metadata_reason == (
        "chain_metadata.evidence_taxonomy_version=1 does not match required taxonomy version 2"
    )


def test_require_taxonomy_version_cli_rejects_mismatch_and_accepts_exact_match(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fail_rc, fail_payload, fail_stderr = _run_verify(
        ["verify", "--json", "--require-taxonomy-version", "2", str(FAIL_FIXTURE)],
        capsys,
    )
    pass_rc, pass_payload, pass_stderr = _run_verify(
        ["verify", "--json", "--require-taxonomy-version", "1", str(PASS_FIXTURE)],
        capsys,
    )

    assert fail_rc == 1
    assert fail_payload["result"] == "fail"
    assert fail_payload["exit_code"] == 1
    assert fail_payload["reason_code"] == "att.verify.taxonomy_version_mismatch"
    assert fail_payload["reasons"][0]["code"] == "att.verify.taxonomy_version_mismatch"
    assert fail_payload["reasons"][0]["path"] == "/chain_metadata/evidence_taxonomy_version"
    assert fail_stderr == ""

    assert pass_rc == 0
    assert pass_payload["result"] == "pass"
    assert pass_payload["exit_code"] == 0
    assert pass_payload["reason_code"] is None
    assert pass_payload["taxonomy_version"] == VERIFY_REASON_TAXONOMY_VERSION
    assert pass_stderr == ""
