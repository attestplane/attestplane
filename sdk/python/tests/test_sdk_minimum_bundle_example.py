# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the SDK minimum proof-bundle example."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from attestplane.sdk import verify_minimum_bundle, verify_minimum_bundle_file
from attestplane.sdk.examples.minimum_bundle import build_example_bundle, main
from attestplane.verifier import verify_proof_bundle


def _assert_strict_valid_minimum_bundle(bundle: dict[str, Any]) -> None:
    result = verify_proof_bundle(
        bundle,
        require_non_empty=True,
        require_signed_attestation=True,
    )

    assert result.ok is True
    assert result.chain_id == "attestplane-sdk-minimum-example"
    assert result.event_count == 1
    assert result.error_code == "VERIFY_OK"
    assert bundle["signatures"][0]["signed_event_hash_hex"] == bundle["events"][0]["event_hash_hex"]


def test_build_example_bundle_emits_strict_valid_minimum_bundle() -> None:
    bundle = build_example_bundle()

    _assert_strict_valid_minimum_bundle(bundle)
    assert verify_minimum_bundle(bundle).ok is True


def test_main_prints_strict_valid_minimum_bundle(capsys: Any) -> None:
    assert main() == 0

    out = capsys.readouterr().out
    assert out.endswith("\n")
    bundle = json.loads(out)

    _assert_strict_valid_minimum_bundle(bundle)


def test_example_bundle_can_be_verified_from_file(tmp_path: Path) -> None:
    bundle_path = tmp_path / "minimum-bundle.json"
    bundle_path.write_text(json.dumps(build_example_bundle()), encoding="utf-8")

    result = verify_minimum_bundle_file(bundle_path)

    assert result.ok is True
    assert result.chain_id == "attestplane-sdk-minimum-example"
