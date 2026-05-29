# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Stable verifier rejection reason-code taxonomy.

This module is separate from ADR-0010 ``ReasonCodeV1`` and from the older
``VERIFY_*`` verifier outcome codes. These namespaced strings are the public
SDK surface for why ``verify`` rejected an otherwise parsed input.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Final, Literal

VERIFY_REASON_TAXONOMY_VERSION: Final[int] = 1
VERIFY_REASON_CODE_SCHEMA_VERSION: Final[int] = VERIFY_REASON_TAXONOMY_VERSION

VerifyReasonCodeV1 = Literal[
    "att.verify.anchor_invalid",
    "att.verify.canonical_mismatch",
    "att.verify.required_field_missing",
    "att.verify.schema_invalid",
    "att.verify.schema_unknown",
    "att.verify.schema_version_missing",
    "att.verify.schema_version_unsupported",
    "att.verify.signature_invalid",
    "att.verify.signature_missing",
    "att.verify.structure_invalid",
]

VERIFY_REASON_CANONICAL_MISMATCH: Final[VerifyReasonCodeV1] = "att.verify.canonical_mismatch"
VERIFY_REASON_SIGNATURE_INVALID: Final[VerifyReasonCodeV1] = "att.verify.signature_invalid"
VERIFY_REASON_SIGNATURE_MISSING: Final[VerifyReasonCodeV1] = "att.verify.signature_missing"
VERIFY_REASON_SCHEMA_UNKNOWN: Final[VerifyReasonCodeV1] = "att.verify.schema_unknown"
VERIFY_REASON_SCHEMA_INVALID: Final[VerifyReasonCodeV1] = "att.verify.schema_invalid"
VERIFY_REASON_SCHEMA_VERSION_MISSING: Final[VerifyReasonCodeV1] = "att.verify.schema_version_missing"
VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED: Final[VerifyReasonCodeV1] = "att.verify.schema_version_unsupported"
VERIFY_REASON_REQUIRED_FIELD_MISSING: Final[VerifyReasonCodeV1] = "att.verify.required_field_missing"
VERIFY_REASON_STRUCTURE_INVALID: Final[VerifyReasonCodeV1] = "att.verify.structure_invalid"
VERIFY_REASON_ANCHOR_INVALID: Final[VerifyReasonCodeV1] = "att.verify.anchor_invalid"

ALL_VERIFY_REASON_CODES_V1: Final[tuple[VerifyReasonCodeV1, ...]] = (
    VERIFY_REASON_ANCHOR_INVALID,
    VERIFY_REASON_CANONICAL_MISMATCH,
    VERIFY_REASON_REQUIRED_FIELD_MISSING,
    VERIFY_REASON_SCHEMA_INVALID,
    VERIFY_REASON_SCHEMA_UNKNOWN,
    VERIFY_REASON_SCHEMA_VERSION_MISSING,
    VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
    VERIFY_REASON_SIGNATURE_INVALID,
    VERIFY_REASON_SIGNATURE_MISSING,
    VERIFY_REASON_STRUCTURE_INVALID,
)

VERIFY_REASON_TAXONOMY: Final[Mapping[VerifyReasonCodeV1, str]] = {
    VERIFY_REASON_ANCHOR_INVALID: "Anchor material is missing, malformed, unsupported, or failed verification.",
    VERIFY_REASON_CANONICAL_MISMATCH: (
        "Recomputed canonical bytes, event hashes, chain links, or embedded verification reports disagree."
    ),
    VERIFY_REASON_REQUIRED_FIELD_MISSING: (
        "A required top-level, nested, signature, or verifier-envelope field is absent."
    ),
    VERIFY_REASON_SCHEMA_INVALID: "The input shape is malformed for a known verifier schema.",
    VERIFY_REASON_SCHEMA_UNKNOWN: (
        "The input declares an unknown schema family, verification method namespace, "
        "or fail-closed critical/required field."
    ),
    VERIFY_REASON_SCHEMA_VERSION_MISSING: (
        "A known bundle, payload, signature, or verifier schema version is missing."
    ),
    VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED: (
        "A known bundle, payload, signature, or verifier schema version is unsupported."
    ),
    VERIFY_REASON_SIGNATURE_INVALID: "Signature material is present but malformed or fails verifier checks.",
    VERIFY_REASON_SIGNATURE_MISSING: "Strict verification requires signature material but none is present.",
    VERIFY_REASON_STRUCTURE_INVALID: "Known bundle relationships are malformed, duplicated, dangling, or out of order.",
}
VERIFY_REASON_CODE_DESCRIPTIONS: Final[Mapping[VerifyReasonCodeV1, str]] = VERIFY_REASON_TAXONOMY

_VERIFY_REASON_CODE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^att\.verify\.[a-z][a-z0-9_]*$")


def is_known_verify_reason_code(value: str) -> bool:
    """Return True when ``value`` is a v1 verifier rejection reason code."""
    return value in ALL_VERIFY_REASON_CODES_V1


def verify_reason_code_matches_format(value: str) -> bool:
    """Return True when ``value`` matches the public ``att.verify.*`` format."""
    return bool(_VERIFY_REASON_CODE_PATTERN.match(value))


def verify_reason_code_explanation(value: VerifyReasonCodeV1) -> str:
    """Return the stable human-readable explanation for a verify reason code."""
    return VERIFY_REASON_TAXONOMY[value]


def resolve_verify_reason_taxonomy_version(result: Any | None = None) -> int:
    """Return the stable public taxonomy version used by verify surfaces.

    Missing, absent, or otherwise non-numeric values are normalized to the
    documented v1 representation so callers do not need to special-case older
    result objects or partial data structures.
    """
    if isinstance(result, int) and not isinstance(result, bool):
        return result
    taxonomy_version = getattr(result, "taxonomy_version", None)
    if isinstance(taxonomy_version, int) and not isinstance(taxonomy_version, bool):
        return taxonomy_version
    return VERIFY_REASON_TAXONOMY_VERSION


__all__ = [
    "ALL_VERIFY_REASON_CODES_V1",
    "VERIFY_REASON_ANCHOR_INVALID",
    "VERIFY_REASON_CANONICAL_MISMATCH",
    "VERIFY_REASON_CODE_DESCRIPTIONS",
    "VERIFY_REASON_CODE_SCHEMA_VERSION",
    "VERIFY_REASON_TAXONOMY",
    "VERIFY_REASON_TAXONOMY_VERSION",
    "VERIFY_REASON_REQUIRED_FIELD_MISSING",
    "VERIFY_REASON_SCHEMA_INVALID",
    "VERIFY_REASON_SCHEMA_UNKNOWN",
    "VERIFY_REASON_SCHEMA_VERSION_MISSING",
    "VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED",
    "VERIFY_REASON_SIGNATURE_INVALID",
    "VERIFY_REASON_SIGNATURE_MISSING",
    "VERIFY_REASON_STRUCTURE_INVALID",
    "resolve_verify_reason_taxonomy_version",
    "VerifyReasonCodeV1",
    "is_known_verify_reason_code",
    "verify_reason_code_explanation",
    "verify_reason_code_matches_format",
]
