# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from attestplane import AttestSubstrate, EventDraft
from attestplane.proof_bundle import ProofBundleBuilder
from attestplane.retention import build_deletion_proof
from attestplane.verifier import verify_proof_bundle
from attestplane.verify_errors import VERIFY_OK, VERIFY_RETENTION_PROOF_FAILED


def _chain() -> list:
    sub = AttestSubstrate()
    base = datetime(2026, 5, 19, 0, 0, 0, tzinfo=UTC)
    return [
        sub.append(EventDraft(event_type="retention_commit_event", actor="controller", payload={"i": 0}), now=base),
        sub.append(
            EventDraft(event_type="redaction_event", actor="controller", payload={"i": 1}),
            now=base + timedelta(microseconds=1),
        ),
        sub.append(
            EventDraft(event_type="deletion_marker_event", actor="controller", payload={"i": 2}),
            now=base + timedelta(microseconds=2),
        ),
    ]


def test_retention_deletion_proof_references_existing_events() -> None:
    chain = _chain()
    proof = build_deletion_proof(
        proof_id="proof-1",
        target_event_hash_hex=chain[0].event_hash.hex(),
        commit_event_hash_hex=chain[1].event_hash.hex(),
        redacted_event_hash_hex=chain[2].event_hash.hex(),
        reason="controller_policy_redaction",
    )
    builder = ProofBundleBuilder(chain_id="retention", producer_runtime="test")
    builder.extend(chain)
    builder.extend_retention_proofs([proof])

    result = verify_proof_bundle(builder.build(now=datetime(2026, 5, 19, tzinfo=UTC)))

    assert result.ok is True
    assert result.retention_proofs_ok is True
    assert result.retention_proofs_reason is None
    assert result.error_code == VERIFY_OK


def test_retention_deletion_proof_dangling_ref_fails_closed() -> None:
    chain = _chain()
    proof = build_deletion_proof(
        proof_id="proof-1",
        target_event_hash_hex=chain[0].event_hash.hex(),
        commit_event_hash_hex=chain[1].event_hash.hex(),
        redacted_event_hash_hex="f" * 64,
        reason="controller_policy_redaction",
    )
    builder = ProofBundleBuilder(chain_id="retention", producer_runtime="test")
    builder.extend(chain)
    builder.extend_retention_proofs([proof])

    result = verify_proof_bundle(builder.build(now=datetime(2026, 5, 19, tzinfo=UTC)))

    assert result.ok is False
    assert result.retention_proofs_ok is False
    assert result.error_code == VERIFY_RETENTION_PROOF_FAILED
    assert "dangling event refs" in (result.retention_proofs_reason or "")
