# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Issue #123 SDK minimum proof-bundle builder tests."""

from __future__ import annotations

import pytest

from attestplane.sdk import IncompleteProofBundleError, ProofBundleBuilder
from attestplane.signing import InMemoryKeyProvider, Signer
from attestplane.verifier import verify_proof_bundle


SUBJECT_DIGEST = "3f551d9" + "0" * 57


def _signer() -> Signer:
    return Signer(
        chain_id="issue-123-minimal",
        key_provider=InMemoryKeyProvider(seed=b"\x12" * 32),
    )


def test_minimal_bundle_passes_non_empty_and_signed_schema() -> None:
    bundle = ProofBundleBuilder.minimal(SUBJECT_DIGEST, _signer())

    result = verify_proof_bundle(
        bundle,
        require_non_empty=True,
        require_signed_attestation=True,
    )

    assert result.ok is True
    assert result.event_count == 1
    assert result.error_code == "VERIFY_OK"
    assert set(bundle) >= {
        "bundle_version",
        "chain_metadata",
        "events",
        "verification_report",
        "forbidden_fields",
        "signatures",
    }
    assert bundle["events"][0]["event"]["matched_input_ref"] == SUBJECT_DIGEST
    assert bundle["events"][0]["event"]["payload"]["subject_digest"] == SUBJECT_DIGEST
    assert bundle["signatures"][0]["signed_event_hash_hex"] == bundle["events"][0]["event_hash_hex"]


def test_minimal_docstring_documents_v17_stability() -> None:
    assert ProofBundleBuilder.minimal.__doc__ is not None
    assert "Stability guarantee for v1.7.x" in ProofBundleBuilder.minimal.__doc__
    assert "minimum-valid" in ProofBundleBuilder.minimal.__doc__


@pytest.mark.parametrize(
    "subject_digest",
    [
        "",
        "3f551d9",
        "A" * 64,
        "g" * 64,
    ],
)
def test_minimal_rejects_invalid_subject_digest_with_typed_error(subject_digest: str) -> None:
    with pytest.raises(IncompleteProofBundleError) as exc_info:
        ProofBundleBuilder.minimal(subject_digest, _signer())

    assert exc_info.value.error_code == "bundle.schema.incomplete"
