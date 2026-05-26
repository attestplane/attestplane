# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Positive signed-schema conformance selector for Issue #139."""

from __future__ import annotations

from collections.abc import Callable
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from attestplane.cli.main import main
from attestplane.verifier import verify_proof_bundle
from attestplane.verify_errors import VERIFY_OK

ROOT = Path(__file__).resolve().parents[2]
SIGNED_SCHEMA_FIXTURE = ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"
SIGNED_SCHEMA_HELPER = ROOT / "tests" / "verifier" / "test_signed_schema_roundtrip.py"


def _load_rebuild_signed_schema_fixture() -> Callable[[dict[str, Any]], dict[str, Any]]:
    module_name = "signed_schema_roundtrip_helper"
    spec = importlib.util.spec_from_file_location(module_name, SIGNED_SCHEMA_HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load signed-schema helper from {SIGNED_SCHEMA_HELPER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.rebuild_signed_schema_fixture


rebuild_signed_schema_fixture = _load_rebuild_signed_schema_fixture()


def _run_verify(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def test_signed_schema_positive_fixture_roundtrip_passes_strict_conformance() -> None:
    bundle = json.loads(SIGNED_SCHEMA_FIXTURE.read_text(encoding="utf-8"))
    rebuilt = rebuild_signed_schema_fixture(bundle)

    result = verify_proof_bundle(
        rebuilt,
        require_non_empty=True,
        require_signed_attestation=True,
    )

    assert result.ok is True
    assert result.error_code == VERIFY_OK
    assert result.signed_attestation_schema_ok is True


def test_signed_schema_taxonomy_version_is_stable_across_verify_json_and_explain(
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle_path = str(SIGNED_SCHEMA_FIXTURE)

    json_rc, json_stdout, json_stderr = _run_verify(["verify", "--json", bundle_path], capsys)
    explain_rc, explain_stdout, explain_stderr = _run_verify(
        ["verify", "--json", "--explain", bundle_path],
        capsys,
    )

    json_payload = json.loads(json_stdout)
    explain_payload = json.loads(explain_stdout)

    assert json_rc == 0
    assert explain_rc == 0
    assert json_stderr == ""
    assert explain_stderr == ""
    assert json_payload["taxonomy_version"] == 1
    assert explain_payload["taxonomy_version"] == 1
    assert json_payload["taxonomy_version"] == explain_payload["taxonomy_version"]
    assert explain_payload["explanation"] == [
        {
            "primary_reason": None,
            "pointer": "/",
            "message": "signer_subject=key_id:4bf5122f344554c53bde2ebb8cd2b7e3 schema_version=1 anchor=absent",
        }
    ]
    json_payload.pop("explanation", None)
    explain_payload.pop("explanation", None)
    assert json_payload == explain_payload
