# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

from attestplane.cli.main import main
from attestplane.verifier import verify_proof_bundle
from attestplane.verify_reason_codes import VERIFY_REASON_TAXONOMY_VERSION

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"


def test_result_object_taxonomy_version_matches_cli_surfaces(
    capsys,
) -> None:
    bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))
    sdk_result = verify_proof_bundle(bundle)

    json_rc = main(["verify", "--json", str(FIXTURE)])
    json_payload = json.loads(capsys.readouterr().out)
    explain_rc = main(["verify", "--json", "--explain", str(FIXTURE)])
    explain_payload = json.loads(capsys.readouterr().out)

    assert sdk_result.taxonomy_version == VERIFY_REASON_TAXONOMY_VERSION
    assert json_rc == 0
    assert explain_rc == 0
    assert json_payload["taxonomy_version"] == sdk_result.taxonomy_version
    assert explain_payload["taxonomy_version"] == sdk_result.taxonomy_version
    assert (
        f"taxonomy_version={sdk_result.taxonomy_version}"
        in explain_payload["explanation"][0]["message"]
    )
