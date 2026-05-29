# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for stable `taxonomy_version` surfacing.

This test locks the additive verifier contract across the SDK result object,
`attestplane verify --json`, and `attestplane verify --explain`.
"""

from __future__ import annotations

import json
from pathlib import Path

from attestplane.cli.main import main
from attestplane.verifier import verify_proof_bundle
from attestplane.verify_reason_codes import VERIFY_REASON_TAXONOMY_VERSION

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"


def _signer_subject(bundle: dict[str, object]) -> str:
    signatures = bundle.get("signatures")
    assert isinstance(signatures, list) and signatures
    first = signatures[0]
    assert isinstance(first, dict)

    key_id = first.get("key_id")
    if isinstance(key_id, str) and key_id:
        return f"key_id:{key_id}"

    signed_event_hash_hex = first.get("signed_event_hash_hex")
    assert isinstance(signed_event_hash_hex, str) and signed_event_hash_hex
    return f"subject_hash:{signed_event_hash_hex}"


def test_taxonomy_version_is_surfaced_identically_across_sdk_json_and_explain(
    capsys,
) -> None:
    bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = verify_proof_bundle(bundle)

    assert result.ok is True
    assert result.taxonomy_version == VERIFY_REASON_TAXONOMY_VERSION == 1

    rc = main(["verify", "--json", str(FIXTURE)])
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.err == ""
    json_payload = json.loads(captured.out)
    assert json_payload["taxonomy_version"] == result.taxonomy_version
    assert captured.out == json.dumps(json_payload, indent=2, sort_keys=True) + "\n"
    assert '"taxonomy_version": 1' in captured.out

    rc = main(["verify", "--explain", str(FIXTURE)])
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.err == ""
    expected_summary = (
        f"OK signer_subject={_signer_subject(bundle)} "
        f"schema_version=1 taxonomy_version={result.taxonomy_version} anchor=absent"
    )
    assert captured.out == expected_summary + "\n"
    assert f"taxonomy_version={result.taxonomy_version}" in captured.out
