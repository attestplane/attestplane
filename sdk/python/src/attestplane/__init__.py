"""Attestplane — verifiable audit substrate for AI agents.

EU AI Act Article 12 ready. Apache-2.0 licensed. See:
- https://github.com/attestplane/attestplane
- docs/adr/0002-substrate-data-model-and-hash-chain-v0.md
"""

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
    "AttestSubstrate",
    "AuditEvent",
    "CanonicalizationError",
    "ChainHead",
    "ChainedEvent",
    "EventDraft",
    "SubjectRef",
    "VerificationResult",
    "__version__",
    "canonicalize",
    "chain_extend",
    "genesis_head",
    "hash_event",
    "verify_chain",
]
