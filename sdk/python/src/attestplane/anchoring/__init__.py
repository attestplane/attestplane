# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""RFC-3161 TSA anchoring per ADR-0003.

v0.0.2-alpha ships the **design skeleton**:

- :class:`TSAProvider` ABC with forbidden-mutating-verb gate
- :class:`AnchorRecord`, :class:`AnchorPolicy`, :class:`TimestampRequest`
- :class:`MockTSAProvider` for tests
- :class:`MultiTSAProvider` composite (fan-out)
- :func:`verify_chain_with_anchors` cross-reference verifier

The real RFC-3161 / ASN.1 / OCSP-backed providers (``FreeTSAProvider``,
``DigiCertProvider``) ship in a follow-up PR alongside
``anchor_vectors.json``. Until then, the verifier reports
``cert_status="VALID_UNVERIFIED"`` for cross-reference-correct
anchors with non-empty cert chains.

This module does NOT modify the substrate's
:func:`~attestplane.hashchain.verify_chain` or any v0.0.1 surface. The
v0.0.1 hash-chain contract is preserved bit-for-bit. Anchors are
sidecar evidence per ADR-0003 § 1.
"""

from attestplane.anchoring.base import (
    ANCHOR_SCHEMA_VERSION,
    AnchorBoundaryError,
    AnchorError,
    AnchorPolicy,
    AnchorRecord,
    AnchorStatus,
    AnchorVerificationError,
    TimestampRequest,
    TSAProvider,
    TSAUnavailableError,
)
from attestplane.anchoring.composite import MultiTSAProvider
from attestplane.anchoring.mock import MockTSAProvider
from attestplane.anchoring.verifier import (
    AnchorVerificationResult,
    CertStatus,
    SingleAnchorResult,
    verify_chain_with_anchors,
)
from attestplane.anchoring.worker import (
    Anchorer,
    AnchorerResult,
    PendingAnchor,
    WorkerStats,
)

# HTTP transport classes; importing requires the 'anchor' extras.
# Guarded so substrate-only installs don't fail on missing crypto deps.
try:
    from attestplane.anchoring.http import (
        DigiCertProvider,
        FreeTSAProvider,
        HttpTransport,
        RecordedHttpTransport,
        Rfc3161HttpProvider,
        UrllibHttpTransport,
        make_replay_transport,
    )

    _HTTP_AVAILABLE = True
except ImportError:  # pragma: no cover
    _HTTP_AVAILABLE = False

# eIDAS Trusted List loader; pure-stdlib XML parsing, no extras required.
from attestplane.anchoring.eidas import (
    ETSI_QTST_URI,
    ETSI_TSA_URI,
    EidasError,
    QualifiedTsaEntry,
    TrustedListParseError,
    load_qualified_tsa_trust_roots,
    parse_trusted_list,
)

__all__ = [
    "ANCHOR_SCHEMA_VERSION",
    "AnchorBoundaryError",
    "AnchorError",
    "AnchorPolicy",
    "AnchorRecord",
    "Anchorer",
    "AnchorerResult",
    "AnchorStatus",
    "AnchorVerificationError",
    "AnchorVerificationResult",
    "CertStatus",
    "DigiCertProvider",
    "ETSI_QTST_URI",
    "ETSI_TSA_URI",
    "EidasError",
    "FreeTSAProvider",
    "HttpTransport",
    "MockTSAProvider",
    "MultiTSAProvider",
    "PendingAnchor",
    "QualifiedTsaEntry",
    "RecordedHttpTransport",
    "Rfc3161HttpProvider",
    "SingleAnchorResult",
    "TimestampRequest",
    "TrustedListParseError",
    "TSAProvider",
    "TSAUnavailableError",
    "UrllibHttpTransport",
    "WorkerStats",
    "load_qualified_tsa_trust_roots",
    "make_replay_transport",
    "parse_trusted_list",
    "verify_chain_with_anchors",
]
