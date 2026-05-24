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
from dataclasses import dataclass
from typing import Final, Literal

VERIFY_REASON_CODE_SCHEMA_VERSION: Final[int] = 1
VERIFY_REASON_CODE_VERSION: Final[str] = "rc.v1"


@dataclass(frozen=True, slots=True)
class VerifyReasonCodeRecord:
    reason_code: VerifyReasonCodeV1
    reason_code_version: str
    rationale: str

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

VERIFY_REASON_REGISTRY_V1: Final[tuple[VerifyReasonCodeRecord, ...]] = (
    VerifyReasonCodeRecord(
        reason_code="att.verify.anchor_invalid",
        reason_code_version=VERIFY_REASON_CODE_VERSION,
        rationale="Anchor material is missing, malformed, unsupported, or failed verification.",
    ),
    VerifyReasonCodeRecord(
        reason_code="att.verify.canonical_mismatch",
        reason_code_version=VERIFY_REASON_CODE_VERSION,
        rationale=(
            "Recomputed canonical bytes, event hashes, chain links, or embedded verification reports disagree."
        ),
    ),
    VerifyReasonCodeRecord(
        reason_code="att.verify.required_field_missing",
        reason_code_version=VERIFY_REASON_CODE_VERSION,
        rationale="A required top-level, nested, signature, or verifier-envelope field is absent.",
    ),
    VerifyReasonCodeRecord(
        reason_code="att.verify.schema_invalid",
        reason_code_version=VERIFY_REASON_CODE_VERSION,
        rationale="The input shape is malformed for a known verifier schema.",
    ),
    VerifyReasonCodeRecord(
        reason_code="att.verify.schema_unknown",
        reason_code_version=VERIFY_REASON_CODE_VERSION,
        rationale=(
            "The input declares an unknown schema family, verification method namespace, "
            "or fail-closed critical/required field."
        ),
    ),
    VerifyReasonCodeRecord(
        reason_code="att.verify.schema_version_missing",
        reason_code_version=VERIFY_REASON_CODE_VERSION,
        rationale="A known bundle, payload, signature, or verifier schema version is missing.",
    ),
    VerifyReasonCodeRecord(
        reason_code="att.verify.schema_version_unsupported",
        reason_code_version=VERIFY_REASON_CODE_VERSION,
        rationale="A known bundle, payload, signature, or verifier schema version is unsupported.",
    ),
    VerifyReasonCodeRecord(
        reason_code="att.verify.signature_invalid",
        reason_code_version=VERIFY_REASON_CODE_VERSION,
        rationale="Signature material is present but malformed or fails verifier checks.",
    ),
    VerifyReasonCodeRecord(
        reason_code="att.verify.signature_missing",
        reason_code_version=VERIFY_REASON_CODE_VERSION,
        rationale="Strict verification requires signature material but none is present.",
    ),
    VerifyReasonCodeRecord(
        reason_code="att.verify.structure_invalid",
        reason_code_version=VERIFY_REASON_CODE_VERSION,
        rationale="Known bundle relationships are malformed, duplicated, dangling, or out of order.",
    ),
)

VERIFY_REASON_ANCHOR_INVALID: Final[VerifyReasonCodeV1] = VERIFY_REASON_REGISTRY_V1[0].reason_code
VERIFY_REASON_CANONICAL_MISMATCH: Final[VerifyReasonCodeV1] = VERIFY_REASON_REGISTRY_V1[1].reason_code
VERIFY_REASON_REQUIRED_FIELD_MISSING: Final[VerifyReasonCodeV1] = VERIFY_REASON_REGISTRY_V1[2].reason_code
VERIFY_REASON_SCHEMA_INVALID: Final[VerifyReasonCodeV1] = VERIFY_REASON_REGISTRY_V1[3].reason_code
VERIFY_REASON_SCHEMA_UNKNOWN: Final[VerifyReasonCodeV1] = VERIFY_REASON_REGISTRY_V1[4].reason_code
VERIFY_REASON_SCHEMA_VERSION_MISSING: Final[VerifyReasonCodeV1] = VERIFY_REASON_REGISTRY_V1[5].reason_code
VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED: Final[VerifyReasonCodeV1] = VERIFY_REASON_REGISTRY_V1[6].reason_code
VERIFY_REASON_SIGNATURE_INVALID: Final[VerifyReasonCodeV1] = VERIFY_REASON_REGISTRY_V1[7].reason_code
VERIFY_REASON_SIGNATURE_MISSING: Final[VerifyReasonCodeV1] = VERIFY_REASON_REGISTRY_V1[8].reason_code
VERIFY_REASON_STRUCTURE_INVALID: Final[VerifyReasonCodeV1] = VERIFY_REASON_REGISTRY_V1[9].reason_code

ALL_VERIFY_REASON_CODES_V1: Final[tuple[VerifyReasonCodeV1, ...]] = tuple(
    record.reason_code for record in VERIFY_REASON_REGISTRY_V1
)

VERIFY_REASON_CODE_DESCRIPTIONS: Final[Mapping[VerifyReasonCodeV1, str]] = {
    record.reason_code: record.rationale for record in VERIFY_REASON_REGISTRY_V1
}

VERIFY_REASON_CODE_VERSIONS: Final[Mapping[VerifyReasonCodeV1, str]] = {
    record.reason_code: record.reason_code_version for record in VERIFY_REASON_REGISTRY_V1
}

_VERIFY_REASON_RECORD_BY_CODE: Final[Mapping[VerifyReasonCodeV1, VerifyReasonCodeRecord]] = {
    record.reason_code: record for record in VERIFY_REASON_REGISTRY_V1
}

_VERIFY_REASON_CODE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^att\.verify\.[a-z][a-z0-9_]*$"
)


def is_known_verify_reason_code(value: str) -> bool:
    """Return True when ``value`` is a v1 verifier rejection reason code."""
    return value in ALL_VERIFY_REASON_CODES_V1


def get_verify_reason_record(code: VerifyReasonCodeV1) -> VerifyReasonCodeRecord:
    """Return the canonical registry row for ``code``."""
    return _VERIFY_REASON_RECORD_BY_CODE[code]


def verify_reason_code_matches_format(value: str) -> bool:
    """Return True when ``value`` matches the public ``att.verify.*`` format."""
    return bool(_VERIFY_REASON_CODE_PATTERN.match(value))


__all__ = [
    "ALL_VERIFY_REASON_CODES_V1",
    "VERIFY_REASON_ANCHOR_INVALID",
    "VERIFY_REASON_CANONICAL_MISMATCH",
    "VERIFY_REASON_CODE_DESCRIPTIONS",
    "VERIFY_REASON_CODE_SCHEMA_VERSION",
    "VERIFY_REASON_CODE_VERSION",
    "VERIFY_REASON_CODE_VERSIONS",
    "VERIFY_REASON_REQUIRED_FIELD_MISSING",
    "VERIFY_REASON_SCHEMA_INVALID",
    "VERIFY_REASON_SCHEMA_UNKNOWN",
    "VERIFY_REASON_SCHEMA_VERSION_MISSING",
    "VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED",
    "VERIFY_REASON_SIGNATURE_INVALID",
    "VERIFY_REASON_SIGNATURE_MISSING",
    "VERIFY_REASON_STRUCTURE_INVALID",
    "VERIFY_REASON_REGISTRY_V1",
    "VerifyReasonCodeRecord",
    "VerifyReasonCodeV1",
    "get_verify_reason_record",
    "is_known_verify_reason_code",
    "verify_reason_code_matches_format",
]
