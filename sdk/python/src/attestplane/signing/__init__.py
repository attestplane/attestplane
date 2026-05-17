# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Event signing primitives per ADR-0005 (implementation in progress).

v0.0.2-alpha ships **T1 (abstract base) + T2 (concrete providers)** of
the architect plan; the Signer worker (T3) and verifier extension (T4)
land in subsequent commits.

Public surface (T1 + T2):

- :data:`SIGNATURE_SCHEMA_VERSION` — frozen at 1.
- :class:`SigningMaterial` — value type carrying the Ed25519 key.
- :class:`SignatureRecord` — sidecar dataclass mirroring
  :class:`~attestplane.anchoring.AnchorRecord`.
- :class:`SignaturePolicy` — when the Signer fires
  (mirrors :class:`~attestplane.anchoring.AnchorPolicy`).
- :class:`KeyProvider` — abstract base with forbidden-verb gate.
- :class:`InMemoryKeyProvider` / :class:`FileKeyProvider` /
  :class:`EnvKeyProvider` — concrete providers.
- :class:`MultiSignerProvider` — plurality composite (any-of-n).
- Error hierarchy: :class:`SigningError`, :class:`KeyProviderError`,
  :class:`SignatureVerificationError`, :class:`KeyBoundaryError`.
- :func:`derive_key_id` — stable 16-byte hex fingerprint helper.

Importing this module requires the ``[signing]`` extras
(``cryptography>=43``). Substrate-only installs without the extras
do not import this module.
"""

from attestplane.signing.base import (
    SIGNATURE_SCHEMA_VERSION,
    KeyBoundaryError,
    KeyProvider,
    KeyProviderError,
    SignatureMode,
    SignaturePolicy,
    SignatureRecord,
    SignatureVerificationError,
    SigningError,
    SigningMaterial,
    derive_key_id,
)
from attestplane.signing.providers import (
    EnvKeyProvider,
    FileKeyProvider,
    InMemoryKeyProvider,
    MultiSignerProvider,
)
from attestplane.signing.signer import (
    Signer,
    SignerResult,
    SignerStats,
)
from attestplane.signing.trust_roots import (
    TrustRootEntry,
    TrustRoots,
    TrustRootsError,
    load_trust_roots,
)
from attestplane.signing.verifier_ext import (
    BundleVerificationResult,
    SignatureStatus,
    SingleSignatureResult,
    verify_chain_full,
    verify_chain_with_signatures,
)

__all__ = [
    "SIGNATURE_SCHEMA_VERSION",
    "BundleVerificationResult",
    "EnvKeyProvider",
    "FileKeyProvider",
    "InMemoryKeyProvider",
    "KeyBoundaryError",
    "KeyProvider",
    "KeyProviderError",
    "MultiSignerProvider",
    "SignatureMode",
    "SignaturePolicy",
    "SignatureRecord",
    "SignatureStatus",
    "SignatureVerificationError",
    "Signer",
    "SignerResult",
    "SignerStats",
    "SigningError",
    "SigningMaterial",
    "SingleSignatureResult",
    "TrustRootEntry",
    "TrustRoots",
    "TrustRootsError",
    "derive_key_id",
    "load_trust_roots",
    "verify_chain_full",
    "verify_chain_with_signatures",
]
