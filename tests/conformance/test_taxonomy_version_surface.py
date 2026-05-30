# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Cross-surface regression coverage for stable verifier taxonomy surfacing."""

from __future__ import annotations

import json
from pathlib import Path

from attestplane.cli.main import main
from attestplane.verify_reason_codes import VERIFY_REASON_TAXONOMY_VERSION
from attestplane.verifier import verify_proof_bundle

ROOT = Path(__file__).resolve().parents[2]
BUNDLE_PATH = ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"
SCHEMA_PATH = ROOT / "schemas" / "cli" / "verify-result-v1.json"


def test_taxonomy_version_surfaces_identically_across_verify_json_explain_and_sdk_result_object(
    capsys,
) -> None:
    bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    sdk_result = verify_proof_bundle(bundle)

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    json_rc = main(["verify", "--json", str(BUNDLE_PATH)])
    json_out = capsys.readouterr()
    explain_rc = main(["verify", "--explain", str(BUNDLE_PATH)])
    explain_out = capsys.readouterr()

    json_payload = json.loads(json_out.out)

    assert json_rc == 0
    assert explain_rc == 0
    assert json_out.err == ""
    assert explain_out.err == ""
    assert json_payload["taxonomy_version"] == VERIFY_REASON_TAXONOMY_VERSION
    assert (
        schema["properties"]["taxonomy_version"]["const"]
        == VERIFY_REASON_TAXONOMY_VERSION
    )
    assert schema["properties"]["taxonomy_version"]["description"] == (
        "Stable public verifier taxonomy version shared with verify --json, "
        "verify --explain, and SDK result objects."
    )
    assert sdk_result.taxonomy_version == VERIFY_REASON_TAXONOMY_VERSION
    assert f"taxonomy_version={VERIFY_REASON_TAXONOMY_VERSION}" in explain_out.out
