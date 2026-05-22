# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Positive signed-schema conformance selector for Issue #139."""

from __future__ import annotations

from collections.abc import Callable
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from attestplane.verifier import verify_proof_bundle
from attestplane.verify_errors import VERIFY_OK

ROOT = Path(__file__).resolve().parents[2]
SIGNED_SCHEMA_FIXTURE = ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"
SIGNED_SCHEMA_HELPER = ROOT / "tests" / "verifier" / "test_signed_schema_roundtrip.py"


def _load_rebuild_signed_schema_fixture() -> Callable[[dict[str, Any]], dict[str, Any]]:
    module_name = "signed_schema_roundtrip_helper"
    spec = importlib.util.spec_from_file_location(module_name, SIGNED_SCHEMA_HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load signed-schema helper from {SIGNED_SCHEMA_HELPER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.rebuild_signed_schema_fixture


rebuild_signed_schema_fixture = _load_rebuild_signed_schema_fixture()


def test_signed_schema_positive_fixture_roundtrip_passes_strict_conformance() -> None:
    bundle = json.loads(SIGNED_SCHEMA_FIXTURE.read_text(encoding="utf-8"))
    rebuilt = rebuild_signed_schema_fixture(bundle)

    result = verify_proof_bundle(
        rebuilt,
        require_non_empty=True,
        require_signed_attestation=True,
    )

    assert result.ok is True
    assert result.error_code == VERIFY_OK
    assert result.signed_attestation_schema_ok is True
