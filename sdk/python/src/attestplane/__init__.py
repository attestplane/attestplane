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
    "GENESIS_HASH",
    "SCHEMA_VERSION",
    "AdapterError",
    "AdapterTranslationError",
    "AttestSubstrate",
    "AuditEvent",
    "CanonicalizationError",
    "ChainHead",
    "ChainedEvent",
    "EventDraft",
    "GenericRuntimeAdapter",
    "SubjectRef",
    "VerificationResult",
    "__version__",
    "canonicalize",
    "chain_extend",
    "genesis_head",
    "hash_event",
    "verify_chain",
]
