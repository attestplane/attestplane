# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Golden taxonomy-version parity coverage for verify surfaces."""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from attestplane.cli.main import main
from attestplane.verifier import verify_proof_bundle
from attestplane.verify_reason_codes import resolve_verify_reason_taxonomy_version

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"


def _run_verify(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def _extract_taxonomy_version(text: str) -> str:
    match = re.search(r"taxonomy_version=([^\s]+)", text)
    assert match is not None
    return match.group(1)


def test_taxonomy_version_surfaces_agree_byte_for_byte(
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))

    sdk_result = verify_proof_bundle(bundle)
    json_rc, json_stdout, json_stderr = _run_verify(
        ["verify", "--json", str(FIXTURE)], capsys
    )
    explain_rc, explain_stdout, explain_stderr = _run_verify(
        ["verify", "--explain", str(FIXTURE)], capsys
    )

    json_payload = json.loads(json_stdout)
    taxonomy_version = str(resolve_verify_reason_taxonomy_version(sdk_result))

    assert json_rc == 0
    assert explain_rc == 0
    assert json_stderr == ""
    assert explain_stderr == ""
    assert str(json_payload["taxonomy_version"]) == taxonomy_version
    assert _extract_taxonomy_version(explain_stdout) == taxonomy_version
    assert str(sdk_result.taxonomy_version) == taxonomy_version


def test_missing_taxonomy_version_resolves_to_stable_v1() -> None:
    assert resolve_verify_reason_taxonomy_version(None) == 1
    assert resolve_verify_reason_taxonomy_version(SimpleNamespace()) == 1
