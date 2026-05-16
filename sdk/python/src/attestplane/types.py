# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Core data types for the Attestplane substrate.

Three-layer envelope model from ADR-0002:

- ``EventDraft`` — caller-provided business fields only. No chain fields.
- ``AuditEvent`` — ``EventDraft`` plus substrate-assigned ``event_id`` and
  ``timestamp``. Still no chain fields. This is the value that is canonicalized
  and hashed.
- ``ChainedEvent`` — ``AuditEvent`` plus ``seq``, ``prev_hash``, ``event_hash``.
  Chain fields live here, not in ``AuditEvent``, to remove the self-reference
  ambiguity of storing a hash inside the value it hashes.

``SubjectRef`` is the only acceptable type for fields that may reference a
GDPR-protected data subject; it forces the caller to declare a pseudonymization
scheme at the type level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

SubjectScheme = Literal["sha256_salted", "opaque", "none"]


@dataclass(frozen=True, slots=True)
class SubjectRef:
    """Reference to a GDPR-protected data subject.

    The ``scheme`` field is a closed enumeration so the canonicalization layer
    can refuse free-form subject identifiers. ``"sha256_salted"`` indicates the
    caller has applied a salted SHA-256 to a direct identifier; ``"opaque"``
    indicates an externally-issued pseudonymous token (e.g., a session UUID);
    ``"none"`` is reserved for events that have no subject linkage at all and
    requires ``value == ""``.
    """

    scheme: SubjectScheme
    value: str

    def __post_init__(self) -> None:
        if self.scheme == "none" and self.value != "":
            raise ValueError("SubjectRef scheme 'none' requires empty value")
        if self.scheme != "none" and not self.value:
            raise ValueError(f"SubjectRef scheme {self.scheme!r} requires non-empty value")


@dataclass(frozen=True, slots=True)
class EventDraft:
    """Caller-provided fields for a new audit event.

    The substrate completes a draft by assigning ``event_id`` and ``timestamp``
    (producing an ``AuditEvent``) and then computing ``seq``, ``prev_hash``,
    ``event_hash`` (producing a ``ChainedEvent``).

    Art. 12(2)(a) of the EU AI Act is addressed by the four optional fields
    ``session_id`` / ``reference_db_ref`` / ``matched_input_ref`` /
    ``human_verifier``. They are *references*, not the data itself; storing
    matched input contents inside the audit log would defeat data minimization.
    """

    event_type: str
    actor: str
    payload: dict[str, Any] = field(default_factory=dict)
    subject_ref: SubjectRef | None = None
    session_id: str | None = None
    reference_db_ref: str | None = None
    matched_input_ref: str | None = None
    human_verifier: SubjectRef | None = None

    def __post_init__(self) -> None:
        if not self.event_type:
            raise ValueError("EventDraft.event_type must be non-empty")
        if not self.actor:
            raise ValueError("EventDraft.actor must be non-empty")


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """A draft completed with substrate-assigned identifier and timestamp.

    This is the value that gets canonicalized and hashed. ``schema_version`` is
    part of the canonicalization input so future field additions are detectable
    via a version bump rather than a silent hash drift.
    """

    schema_version: int
    event_id: str
    timestamp: datetime
    event_type: str
    actor: str
    payload: dict[str, Any]
    subject_ref: SubjectRef | None
    session_id: str | None
    reference_db_ref: str | None
    matched_input_ref: str | None
    human_verifier: SubjectRef | None


@dataclass(frozen=True, slots=True)
class ChainedEvent:
    """An ``AuditEvent`` anchored to its position in the chain."""

    seq: int
    prev_hash: bytes
    event_hash: bytes
    event: AuditEvent


@dataclass(frozen=True, slots=True)
class ChainHead:
    """The public concurrency contract.

    Multi-writer backends (M6) must atomically compare-and-swap on this tuple
    when appending. The genesis head has ``seq == -1`` and ``event_hash`` equal
    to the all-zero digest defined in ``hashchain.GENESIS_HASH``.
    """

    seq: int
    event_hash: bytes
