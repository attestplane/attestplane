# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Cross-surface regression coverage for verifier taxonomy surfacing."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from attestplane.cli.main import main
from attestplane.cli.verify_json import _verify_explanations
from attestplane.verify_reason_codes import format_verify_taxonomy_version
from attestplane.verifier import verify_proof_bundle

ROOT = Path(__file__).resolve().parents[2]
BUNDLE_PATH = ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"


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
    assert bundle["chain_metadata"]["evidence_taxonomy_version"] == sdk_result.taxonomy_version
    assert json_payload["taxonomy_version"] == sdk_result.taxonomy_version
    assert str(json_payload["taxonomy_version"]) == str(sdk_result.taxonomy_version)
    assert f"taxonomy_version={sdk_result.taxonomy_version}" in explain_captured.out
    assert format_verify_taxonomy_version(sdk_result.taxonomy_version) == "1"


def test_missing_taxonomy_version_renders_stable_placeholder() -> None:
    explanation = _verify_explanations(SimpleNamespace(ok=True), bundle=None, explain=True)

    assert explanation == [
        {
            "primary_reason": None,
            "pointer": "/",
            "message": "signer_subject=unknown schema_version=unknown taxonomy_version=unknown anchor=unknown",
        }
    ]
    assert format_verify_taxonomy_version(None) == "unknown"
