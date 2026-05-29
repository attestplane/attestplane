# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Cross-surface taxonomy-version parity checks for ``verify``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.cli.verify_json import format_verify_reason_taxonomy_version
from attestplane.verifier import verify_proof_bundle
from attestplane.verify_reason_codes import resolve_verify_reason_taxonomy_version

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_BUNDLE = ROOT / "fixtures" / "sample.bundle"

EXPECTED_TAXONOMY_VERSION_TEXT = "1"
EXPECTED_EXPLAIN_SUMMARY = (
    "OK signer_subject=key_id:4bf5122f344554c53bde2ebb8cd2b7e3 "
    "schema_version=1 taxonomy_version=1 anchor=absent"
)


def test_taxonomy_version_surface_is_shared_across_sdk_cli_json_and_explain(
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = json.loads(SAMPLE_BUNDLE.read_text(encoding="utf-8"))

    sdk_result = verify_proof_bundle(bundle)
    assert sdk_result.ok is True
    assert sdk_result.taxonomy_version == resolve_verify_reason_taxonomy_version()
    assert format_verify_reason_taxonomy_version(sdk_result.taxonomy_version) == EXPECTED_TAXONOMY_VERSION_TEXT

    rc_json = main(["verify", "--json", str(SAMPLE_BUNDLE)])
    json_stdout = capsys.readouterr().out
    assert rc_json == 0

    payload = json.loads(json_stdout)
    assert payload["taxonomy_version"] == sdk_result.taxonomy_version
    assert json_stdout.count(f'"taxonomy_version": {EXPECTED_TAXONOMY_VERSION_TEXT}') == 1

    rc_explain = main(["verify", "--explain", str(SAMPLE_BUNDLE)])
    explain_stdout = capsys.readouterr().out.strip()
    assert rc_explain == 0
    assert explain_stdout == EXPECTED_EXPLAIN_SUMMARY
    assert f"taxonomy_version={EXPECTED_TAXONOMY_VERSION_TEXT}" in explain_stdout


def test_absent_taxonomy_version_renders_as_unknown() -> None:
    assert format_verify_reason_taxonomy_version(None) == "unknown"
