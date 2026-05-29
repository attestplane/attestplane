# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Issue #123 typed SDK error tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from attestplane.hashchain import chain_extend, genesis_head
from attestplane.proof_bundle import ProofBundleBuilder
from attestplane.sdk import (
    EmptyProofBundleError,
    IncompleteProofBundleError,
    verify_minimum_bundle,
)
from attestplane.verifier import verify_proof_bundle
from attestplane.verify_reason_codes import VERIFY_REASON_TAXONOMY_VERSION
from attestplane.types import EventDraft

ROOT = Path(__file__).resolve().parents[2]
SIGNED_SCHEMA_FIXTURE = (
    ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"
)


def test_verify_minimum_bundle_raises_empty_error_for_zero_event_bundle() -> None:
    bundle = ProofBundleBuilder(chain_id="empty", producer_runtime="test").build()

    with pytest.raises(EmptyProofBundleError) as exc_info:
        verify_minimum_bundle(bundle)

    assert exc_info.value.error_code == "VERIFY_REQUIRED_FIELDS_MISSING"


def test_verify_minimum_bundle_raises_incomplete_error_for_unsigned_bundle() -> None:
    event = chain_extend(
        genesis_head(),
        EventDraft(event_type="evidence_event", actor="agent"),
        now=datetime(2026, 5, 22, tzinfo=UTC),
        event_id="00000000-0000-7000-8000-000000000123",
    )
    builder = ProofBundleBuilder(chain_id="unsigned", producer_runtime="test")
    builder.extend([event])

    with pytest.raises(IncompleteProofBundleError) as exc_info:
        verify_minimum_bundle(builder.build())

    assert exc_info.value.error_code == "bundle.schema.incomplete"


def test_verify_result_taxonomy_version_matches_sdk_result_object() -> None:
    bundle = json.loads(SIGNED_SCHEMA_FIXTURE.read_text(encoding="utf-8"))

    result = verify_proof_bundle(bundle)

    assert result.ok is True
    assert result.taxonomy_version == VERIFY_REASON_TAXONOMY_VERSION
