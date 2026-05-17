# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Compliance obligation registry — maps regulatory articles to v1 evidence.

Public surface:

- :class:`ObligationEntry` — frozen dataclass for a single entry.
- :class:`Registry` — frozen container with lookup helpers.
- :func:`load_eu_ai_act_article_12` — load the EU AI Act Article 12 registry
  shipped inside this package.
- Error hierarchy: :class:`ObligationRegistryError` and its subclasses.

Future entries (M6+) will add DORA Article 8, NIS2 Article 21, GDPR
Article 30, ISO 42001 clauses, and NIST AI RMF subcategories. The loader
contract is stable; only new ``load_*`` functions appear.

See ADR-0008 and docs/policy/{forbidden_claims,allowed_claims,claims_policy}.md
for the discipline that governs entries.
"""

from attestplane.obligations.registry import (
    DuplicateObligationIdError,
    ImplementationStatus,
    InvalidImplementationStatusError,
    ObligationEntry,
    ObligationRegistryError,
    Registry,
    UnknownEventTypeError,
    UnknownEvidenceFieldError,
    load_eu_ai_act_article_12,
)

__all__ = [
    "DuplicateObligationIdError",
    "ImplementationStatus",
    "InvalidImplementationStatusError",
    "ObligationEntry",
    "ObligationRegistryError",
    "Registry",
    "UnknownEventTypeError",
    "UnknownEvidenceFieldError",
    "load_eu_ai_act_article_12",
]
