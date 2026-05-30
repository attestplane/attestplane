# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""SDK result-object taxonomy regression coverage."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk" / "python" / "src"))

from attestplane.cli.main import main  # noqa: E402
from attestplane.verify_reason_codes import (  # noqa: E402
    format_verify_taxonomy_version,
    resolve_verify_taxonomy_version,
)
from attestplane.verifier import verify_proof_bundle  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"


def test_sdk_result_taxonomy_and_cli_surfaces_share_one_version(capsys) -> None:
    bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))
    sdk_result = verify_proof_bundle(bundle)

    json_rc = main(["verify", "--json", str(FIXTURE)])
    json_captured = capsys.readouterr()
    explain_rc = main(["verify", "--explain", str(FIXTURE)])
    explain_captured = capsys.readouterr()

    json_payload = json.loads(json_captured.out)

    assert json_rc == 0
    assert explain_rc == 0
    assert json_captured.err == ""
    assert explain_captured.err == ""
    assert "taxonomy_version" in type(sdk_result).__dataclass_fields__
    assert sdk_result.taxonomy_version == resolve_verify_taxonomy_version()
    assert sdk_result.taxonomy_version == 1
    assert json_payload["taxonomy_version"] == sdk_result.taxonomy_version
    assert f"taxonomy_version={sdk_result.taxonomy_version}" in explain_captured.out
    assert format_verify_taxonomy_version(sdk_result.taxonomy_version) == "1"
