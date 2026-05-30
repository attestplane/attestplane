# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Cross-surface regression coverage for verifier taxonomy surfacing."""

from __future__ import annotations

import json
from pathlib import Path

from attestplane.cli.main import main
from attestplane.verify_reason_codes import (
    format_verify_taxonomy_version,
    resolve_verify_taxonomy_version,
)
from attestplane.verifier import verify_proof_bundle

ROOT = Path(__file__).resolve().parents[2]
BUNDLE_PATH = ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"


def test_resolve_verify_taxonomy_version_reads_bundle_metadata() -> None:
    assert resolve_verify_taxonomy_version(
        {"chain_metadata": {"evidence_taxonomy_version": 7}}
    ) == 7
    assert resolve_verify_taxonomy_version(None) == 1


def test_taxonomy_version_matches_across_sdk_json_and_explain(capsys) -> None:
    bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    sdk_result = verify_proof_bundle(bundle)

    json_rc = main(["verify", "--json", str(BUNDLE_PATH)])
    json_captured = capsys.readouterr()
    explain_rc = main(["verify", "--explain", str(BUNDLE_PATH)])
    explain_captured = capsys.readouterr()

    json_payload = json.loads(json_captured.out)

    assert json_rc == 0
    assert explain_rc == 0
    assert json_captured.err == ""
    assert explain_captured.err == ""
    assert sdk_result.taxonomy_version == bundle["chain_metadata"]["evidence_taxonomy_version"]
    assert json_payload["taxonomy_version"] == sdk_result.taxonomy_version
    assert str(json_payload["taxonomy_version"]) == str(sdk_result.taxonomy_version)
    assert f"taxonomy_version={sdk_result.taxonomy_version}" in explain_captured.out
    assert explain_captured.out.count("taxonomy_version=") == 1
    assert format_verify_taxonomy_version(sdk_result.taxonomy_version) == "1"
    assert list(json_payload) == [
        "anchoring",
        "bundle",
        "exit_code",
        "reason_code",
        "reasons",
        "result",
        "schema_version",
        "taxonomy_version",
    ]
    assert list(json_payload["bundle"]) == ["digest", "schema_version"]
    assert list(json_payload["anchoring"]) == ["quarantined", "status"]
