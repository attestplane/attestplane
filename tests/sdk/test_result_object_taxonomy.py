# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""SDK result-object regression coverage for verifier taxonomy surfacing."""

from __future__ import annotations

import json
from pathlib import Path

from attestplane.sdk import verify_minimum_bundle
from attestplane.verify_reason_codes import VERIFY_REASON_TAXONOMY_VERSION

ROOT = Path(__file__).resolve().parents[2]
BUNDLE_PATH = ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"


def test_result_object_surfaces_taxonomy_version_from_sdk_verifier() -> None:
    bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    result = verify_minimum_bundle(bundle)

    assert result.ok is True
    assert result.taxonomy_version == VERIFY_REASON_TAXONOMY_VERSION
    assert str(result.taxonomy_version) == "1"
