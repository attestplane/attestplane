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
from attestplane.anchoring import (
    ANCHOR_SCHEMA_VERSION,
    AnchorError,
    AnchorPolicy,
    AnchorRecord,
    AnchorVerificationError,
    AnchorVerificationResult,
    MockTSAProvider,
    MultiTSAProvider,
    SingleAnchorResult,
    TimestampRequest,
    TSAProvider,
    TSAUnavailableError,
    verify_chain_with_anchors,
)
from attestplane.canonical import CanonicalizationError, canonicalize
from attestplane.canonical_text import (
    CanonicalTextError,
    canonicalize_text,
    text_hash,
    text_hash_hex,
)
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
from attestplane.proof_bundle import (
    DEFAULT_FORBIDDEN_FIELDS,
    FrameworkMapping,
    ProofBundleBuilder,
    build_auditor_export,
)
from attestplane.storage import (
    AbstractStorageBackend,
    JsonlStorageBackend,
    StorageError,
    StorageReadError,
    StorageWriteError,
)
from attestplane.verifier import (
    BundleSchemaError,
    BundleVerificationError,
    BundleVerificationResult,
    verify_proof_bundle,
    verify_proof_bundle_file,
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

__version__ = "0.0.2a0"

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
    "CanonicalTextError",
    "CanonicalizationError",
    "ChainHead",
    "ChainedEvent",
    "EventDraft",
    "ANCHOR_SCHEMA_VERSION",
    "AbstractStorageBackend",
    "AnchorError",
    "AnchorPolicy",
    "AnchorRecord",
    "AnchorVerificationError",
    "AnchorVerificationResult",
    "BundleSchemaError",
    "BundleVerificationError",
    "BundleVerificationResult",
    "DEFAULT_FORBIDDEN_FIELDS",
    "FrameworkMapping",
    "GenericRuntimeAdapter",
    "MockTSAProvider",
    "MultiTSAProvider",
    "JsonlStorageBackend",
    "ObligationEntry",
    "ObligationRegistryError",
    "ProofBundleBuilder",
    "Registry",
    "SingleAnchorResult",
    "StorageError",
    "StorageReadError",
    "StorageWriteError",
    "SubjectRef",
    "TSAProvider",
    "TSAUnavailableError",
    "TimestampRequest",
    "VerificationResult",
    "__version__",
    "canonicalize",
    "chain_extend",
    "genesis_head",
    "hash_event",
    "build_auditor_export",
    "canonicalize_text",
    "is_known_v1_event_type",
    "load_all_registries",
    "load_dora_article_8",
    "load_eu_ai_act_article_12",
    "text_hash",
    "text_hash_hex",
    "verify_chain",
    "verify_chain_with_anchors",
    "verify_proof_bundle",
    "verify_proof_bundle_file",
]
