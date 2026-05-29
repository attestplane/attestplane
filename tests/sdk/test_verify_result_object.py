# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""SDK result-object contract tests for ``taxonomy_version`` parity."""

from __future__ import annotations

import json
from pathlib import Path

from attestplane.cli.main import main
from attestplane.verifier import verify_proof_bundle
from attestplane.verify_reason_codes import VERIFY_REASON_TAXONOMY_VERSION

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"


def _run_verify(argv: list[str], capsys) -> tuple[int, str, str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def test_result_object_taxonomy_version_is_stable_across_verify_surfaces(
    capsys,
) -> None:
    bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = verify_proof_bundle(
        bundle, require_non_empty=True, require_signed_attestation=True
    )

    json_rc, json_stdout, json_stderr = _run_verify(
        ["verify", "--json", str(FIXTURE)], capsys
    )
    explain_rc, explain_stdout, explain_stderr = _run_verify(
        ["verify", "--explain", str(FIXTURE)], capsys
    )

    json_payload = json.loads(json_stdout)

    assert json_rc == 0
    assert explain_rc == 0
    assert json_stderr == ""
    assert explain_stderr == ""
    assert result.taxonomy_version == VERIFY_REASON_TAXONOMY_VERSION
    assert json_payload["taxonomy_version"] == VERIFY_REASON_TAXONOMY_VERSION
    assert result.taxonomy_version == json_payload["taxonomy_version"]
    assert explain_stdout.startswith("OK signer_subject=")
    assert "schema_version=1 taxonomy_version=1 anchor=absent" in explain_stdout
