# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Issue #123 typed SDK error tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from attestplane.hashchain import chain_extend, genesis_head
from attestplane.proof_bundle import ProofBundleBuilder
from attestplane.sdk import (
    EmptyProofBundleError,
    IncompleteProofBundleError,
    verify_minimum_bundle,
)
from attestplane.types import EventDraft


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
