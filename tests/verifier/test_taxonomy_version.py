# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for resolved verifier taxonomy surfacing."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verifier import verify_proof_bundle

ROOT = Path(__file__).resolve().parents[2]
SIGNED_FIXTURE = ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"


def _write_bundle(tmp_path: Path, bundle: dict[str, object], *, name: str) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_verify_result_surfaces_bundle_taxonomy_version_and_legacy_null(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = json.loads(SIGNED_FIXTURE.read_text(encoding="utf-8"))
    legacy_bundle = copy.deepcopy(bundle)
    del legacy_bundle["chain_metadata"]["evidence_taxonomy_version"]

    declared_result = verify_proof_bundle(bundle)
    legacy_result = verify_proof_bundle(legacy_bundle)

    assert declared_result.taxonomy_version == 1
    assert legacy_result.taxonomy_version is None

    declared_path = _write_bundle(tmp_path, bundle, name="declared.json")
    legacy_path = _write_bundle(tmp_path, legacy_bundle, name="legacy.json")

    rc = main(["verify", "--json", str(declared_path)])
    declared_payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert declared_payload["taxonomy_version"] == 1

    rc = main(["verify", "--json", str(legacy_path)])
    legacy_payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert legacy_payload["taxonomy_version"] is None


def test_verify_explain_human_summary_uses_same_taxonomy_resolution(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = json.loads(SIGNED_FIXTURE.read_text(encoding="utf-8"))
    legacy_bundle = copy.deepcopy(bundle)
    del legacy_bundle["chain_metadata"]["evidence_taxonomy_version"]

    declared_path = _write_bundle(tmp_path, bundle, name="declared-explain.json")
    legacy_path = _write_bundle(tmp_path, legacy_bundle, name="legacy-explain.json")

    rc = main(["verify", "--explain", str(declared_path)])
    declared_stdout = capsys.readouterr().out
    assert rc == 0
    assert "taxonomy_version=1" in declared_stdout

    rc = main(["verify", "--explain", str(legacy_path)])
    legacy_stdout = capsys.readouterr().out
    assert rc == 0
    assert "taxonomy_version=null" in legacy_stdout
