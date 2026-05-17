# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Attestplane — verifiable audit substrate for AI agents.

Designed toward EU AI Act Article 12 auditability. Apache-2.0 licensed. See:
- https://github.com/attestplane/attestplane
- docs/adr/0002-substrate-data-model-and-hash-chain-v0.md
"""

from attestplane.adapters import (
    AdapterError,
    AdapterTranslationError,
    GenericRuntimeAdapter,
)
from attestplane.canonical import CanonicalizationError, canonicalize
from attestplane.event_types import (
    ALL_EVENT_TYPES_V1,
    BUDGET_EVENT,
    EVAL_EVENT,
    EVIDENCE_TAXONOMY_VERSION,
    GATEWAY_DECISION_EVENT,
    HUMAN_APPROVAL_EVENT,
    LEASE_LIFECYCLE_EVENT,
    POLICY_CHECK_EVENT,
    ROUTING_EVENT,
    RUNTIME_LIFECYCLE_EVENT,
    SETTLEMENT_EVENT,
    STATE_TRANSITION_EVENT,
    TOOL_CALL_EVENT,
    WORKER_ASSIGNMENT_EVENT,
    is_known_v1_event_type,
)
from attestplane.obligations import (
    ObligationEntry,
    ObligationRegistryError,
    Registry,
    load_all_registries,
    load_dora_article_8,
    load_eu_ai_act_article_12,
)
from attestplane.storage import (
    AbstractStorageBackend,
    JsonlStorageBackend,
    StorageError,
    StorageReadError,
    StorageWriteError,
)
from attestplane.hashchain import (
    GENESIS_HASH,
    SCHEMA_VERSION,
    VerificationResult,
    chain_extend,
    genesis_head,
    hash_event,
    verify_chain,
)
from attestplane.substrate import AttestSubstrate
from attestplane.types import (
    AuditEvent,
    ChainedEvent,
    ChainHead,
    EventDraft,
    SubjectRef,
)

__version__ = "0.0.1"

__all__ = [
    "ALL_EVENT_TYPES_V1",
    "BUDGET_EVENT",
    "EVAL_EVENT",
    "EVIDENCE_TAXONOMY_VERSION",
    "GATEWAY_DECISION_EVENT",
    "GENESIS_HASH",
    "HUMAN_APPROVAL_EVENT",
    "LEASE_LIFECYCLE_EVENT",
    "POLICY_CHECK_EVENT",
    "ROUTING_EVENT",
    "RUNTIME_LIFECYCLE_EVENT",
    "SCHEMA_VERSION",
    "SETTLEMENT_EVENT",
    "STATE_TRANSITION_EVENT",
    "TOOL_CALL_EVENT",
    "WORKER_ASSIGNMENT_EVENT",
    "AdapterError",
    "AdapterTranslationError",
    "AttestSubstrate",
    "AuditEvent",
    "CanonicalizationError",
    "ChainHead",
    "ChainedEvent",
    "EventDraft",
    "AbstractStorageBackend",
    "GenericRuntimeAdapter",
    "JsonlStorageBackend",
    "ObligationEntry",
    "ObligationRegistryError",
    "Registry",
    "StorageError",
    "StorageReadError",
    "StorageWriteError",
    "SubjectRef",
    "VerificationResult",
    "__version__",
    "canonicalize",
    "chain_extend",
    "genesis_head",
    "hash_event",
    "is_known_v1_event_type",
    "load_all_registries",
    "load_dora_article_8",
    "load_eu_ai_act_article_12",
    "verify_chain",
]
