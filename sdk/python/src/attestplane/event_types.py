# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Evidence event type constants — v1 taxonomy.

These twelve strings are the canonical ``event_type`` identifiers for the
v1 evidence taxonomy locked by ADR-0008 and specified in
``docs/spec/evidence-event-taxonomy-v1.md``.

Adapters MUST import these constants rather than embedding string literals.
The :data:`ALL_EVENT_TYPES_V1` set is exported for runtime "is this a
known v1 type?" checks performed by exporters, verifiers, and the
obligation registry — **not** by the substrate's canonicalization or
hash-chain layers, which deliberately stay taxonomy-agnostic per
ADR-0008 § Decision ("Substrate stays neutral").

The taxonomy version is tracked separately from the chain schema version
and the anchor schema version::

    EVIDENCE_TAXONOMY_VERSION  # this file, value 1 in v1
    SCHEMA_VERSION             # attestplane.hashchain, value 1 from ADR-0002
    anchor_schema_version      # ADR-0003, value 1 in v0.1
"""

from __future__ import annotations

from typing import Final

EVIDENCE_TAXONOMY_VERSION: Final[int] = 1
"""Frozen at 1 for the v1 taxonomy. Increment requires a new ADR superseding 0008."""

TOOL_CALL_EVENT: Final = "tool_call_event"
POLICY_CHECK_EVENT: Final = "policy_check_event"
HUMAN_APPROVAL_EVENT: Final = "human_approval_event"
LEASE_LIFECYCLE_EVENT: Final = "lease_lifecycle_event"
BUDGET_EVENT: Final = "budget_event"
SETTLEMENT_EVENT: Final = "settlement_event"
WORKER_ASSIGNMENT_EVENT: Final = "worker_assignment_event"
RUNTIME_LIFECYCLE_EVENT: Final = "runtime_lifecycle_event"
GATEWAY_DECISION_EVENT: Final = "gateway_decision_event"
STATE_TRANSITION_EVENT: Final = "state_transition_event"
EVAL_EVENT: Final = "eval_event"
ROUTING_EVENT: Final = "routing_event"

ALL_EVENT_TYPES_V1: Final[frozenset[str]] = frozenset({
    TOOL_CALL_EVENT,
    POLICY_CHECK_EVENT,
    HUMAN_APPROVAL_EVENT,
    LEASE_LIFECYCLE_EVENT,
    BUDGET_EVENT,
    SETTLEMENT_EVENT,
    WORKER_ASSIGNMENT_EVENT,
    RUNTIME_LIFECYCLE_EVENT,
    GATEWAY_DECISION_EVENT,
    STATE_TRANSITION_EVENT,
    EVAL_EVENT,
    ROUTING_EVENT,
})


def is_known_v1_event_type(event_type: str) -> bool:
    """Return ``True`` if ``event_type`` is one of the twelve v1 strings.

    Verifiers and exporters use this to distinguish "known v1 event" from
    "future-taxonomy / unknown event". The latter is not an error — v1
    verifiers are required to tolerate unknown event types per ADR-0008
    § Decision ("Substrate stays neutral") to remain forward-compatible
    with future taxonomy versions.
    """
    return event_type in ALL_EVENT_TYPES_V1


__all__ = [
    "ALL_EVENT_TYPES_V1",
    "BUDGET_EVENT",
    "EVAL_EVENT",
    "EVIDENCE_TAXONOMY_VERSION",
    "GATEWAY_DECISION_EVENT",
    "HUMAN_APPROVAL_EVENT",
    "LEASE_LIFECYCLE_EVENT",
    "POLICY_CHECK_EVENT",
    "ROUTING_EVENT",
    "RUNTIME_LIFECYCLE_EVENT",
    "SETTLEMENT_EVENT",
    "STATE_TRANSITION_EVENT",
    "TOOL_CALL_EVENT",
    "WORKER_ASSIGNMENT_EVENT",
    "is_known_v1_event_type",
]
