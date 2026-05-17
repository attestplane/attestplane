# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Compliance obligation registry loader.

Loads JSON obligation files shipped under :mod:`attestplane.obligations` and
exposes them as typed :class:`ObligationEntry` records. The registry is
read-only at runtime; mutation is not supported because the registry is part
of the public claim-safety surface ([forbidden_claims.md], [allowed_claims.md])
and silent runtime modification would undermine the audit trail discipline
locked by [claims_policy.md].

The loader validates each entry against four invariants enforced beyond the
JSON Schema:

1. ``implementation_status`` is one of the four locked values
   (``mapping_target`` / ``designed_toward`` / ``field_supported`` /
   ``verified_in_test``). Any other value raises
   :class:`InvalidImplementationStatusError`.
2. Every ``event_type_mapping`` string is a v1 taxonomy member
   (:data:`attestplane.event_types.ALL_EVENT_TYPES_V1`). Unknown strings raise
   :class:`UnknownEventTypeError` — preventing a registry entry that
   references a hypothetical event type that no adapter would emit.
3. Every ``required_evidence_fields`` / ``optional_evidence_fields`` entry
   is a known :class:`~attestplane.types.EventDraft` field (or one of
   ``event_id``, ``timestamp``, ``event_type`` added by the substrate).
4. ``obligation_id`` is unique across a registry file.

Loaders for specific frameworks (e.g., :func:`load_eu_ai_act_article_12`)
return the parsed registry. Callers should treat the returned
:class:`Registry` as immutable; the dataclasses are frozen.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Final, Literal

from attestplane.event_types import ALL_EVENT_TYPES_V1

ImplementationStatus = Literal[
    "mapping_target",
    "designed_toward",
    "field_supported",
    "verified_in_test",
]

_ALLOWED_IMPLEMENTATION_STATUSES: Final[frozenset[str]] = frozenset({
    "mapping_target",
    "designed_toward",
    "field_supported",
    "verified_in_test",
})

# Top-level EventDraft fields plus the three substrate-assigned identity fields
# that may legitimately appear in required/optional evidence-field lists.
_KNOWN_EVIDENCE_FIELDS: Final[frozenset[str]] = frozenset({
    "event_id",
    "timestamp",
    "event_type",
    "actor",
    "payload",
    "subject_ref",
    "session_id",
    "reference_db_ref",
    "matched_input_ref",
    "human_verifier",
})


class ObligationRegistryError(Exception):
    """Base class for registry-loading errors."""


class InvalidImplementationStatusError(ObligationRegistryError):
    """``implementation_status`` is not one of the four locked values."""


class UnknownEventTypeError(ObligationRegistryError):
    """An entry's ``event_type_mapping`` references an unknown v1 type."""


class UnknownEvidenceFieldError(ObligationRegistryError):
    """An entry references an evidence field that is not part of EventDraft."""


class DuplicateObligationIdError(ObligationRegistryError):
    """Two entries in the same file share an ``obligation_id``."""


@dataclass(frozen=True, slots=True)
class ObligationEntry:
    """A single regulatory obligation mapped to v1 evidence types and fields."""

    framework: str
    article: str
    paragraph: str
    obligation_id: str
    regulatory_text: str
    required_evidence_fields: tuple[str, ...]
    optional_evidence_fields: tuple[str, ...]
    event_type_mapping: tuple[str, ...]
    verifier_expectation: str
    implementation_status: ImplementationStatus
    legal_disclaimer: str
    source_citation: str
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class Registry:
    """A loaded registry file (e.g., one regulatory article)."""

    framework: str
    framework_source: str
    registry_version: int
    last_reviewed: str
    entries: tuple[ObligationEntry, ...]

    def by_id(self, obligation_id: str) -> ObligationEntry:
        """Return the entry matching ``obligation_id`` or raise ``KeyError``."""
        for entry in self.entries:
            if entry.obligation_id == obligation_id:
                return entry
        raise KeyError(f"no obligation entry with id {obligation_id!r}")

    def by_event_type(self, event_type: str) -> tuple[ObligationEntry, ...]:
        """Return all entries that map to a given v1 event type, in file order."""
        return tuple(
            entry for entry in self.entries
            if event_type in entry.event_type_mapping
        )

    def by_implementation_status(
        self, status: ImplementationStatus
    ) -> tuple[ObligationEntry, ...]:
        return tuple(
            entry for entry in self.entries if entry.implementation_status == status
        )


def _validate_entry(entry_dict: dict[str, object]) -> ObligationEntry:
    status = entry_dict.get("implementation_status")
    if status not in _ALLOWED_IMPLEMENTATION_STATUSES:
        raise InvalidImplementationStatusError(
            f"obligation {entry_dict.get('obligation_id')!r}: "
            f"implementation_status={status!r} is not one of "
            f"{sorted(_ALLOWED_IMPLEMENTATION_STATUSES)}"
        )

    event_types_raw = entry_dict.get("event_type_mapping", [])
    assert isinstance(event_types_raw, list)
    event_types = tuple(event_types_raw)
    for event_type in event_types:
        if event_type not in ALL_EVENT_TYPES_V1:
            raise UnknownEventTypeError(
                f"obligation {entry_dict.get('obligation_id')!r}: "
                f"event_type_mapping contains {event_type!r}, "
                f"which is not a v1 taxonomy member"
            )

    required_fields_raw = entry_dict.get("required_evidence_fields", [])
    optional_fields_raw = entry_dict.get("optional_evidence_fields", [])
    assert isinstance(required_fields_raw, list)
    assert isinstance(optional_fields_raw, list)
    for field in [*required_fields_raw, *optional_fields_raw]:
        assert isinstance(field, str)
        if field not in _KNOWN_EVIDENCE_FIELDS:
            raise UnknownEvidenceFieldError(
                f"obligation {entry_dict.get('obligation_id')!r}: "
                f"evidence field {field!r} is not a known EventDraft / AuditEvent field; "
                f"known fields are {sorted(_KNOWN_EVIDENCE_FIELDS)}"
            )

    return ObligationEntry(
        framework=str(entry_dict["framework"]),
        article=str(entry_dict["article"]),
        paragraph=str(entry_dict["paragraph"]),
        obligation_id=str(entry_dict["obligation_id"]),
        regulatory_text=str(entry_dict["regulatory_text"]),
        required_evidence_fields=tuple(str(f) for f in required_fields_raw),
        optional_evidence_fields=tuple(str(f) for f in optional_fields_raw),
        event_type_mapping=event_types,
        verifier_expectation=str(entry_dict["verifier_expectation"]),
        implementation_status=status,  # type: ignore[arg-type]
        legal_disclaimer=str(entry_dict["legal_disclaimer"]),
        source_citation=str(entry_dict["source_citation"]),
        notes=str(entry_dict["notes"]) if entry_dict.get("notes") is not None else None,
    )


def _load_from_resource(filename: str) -> Registry:
    """Load a registry file shipped inside this package."""
    raw_bytes = resources.files("attestplane.obligations").joinpath(filename).read_bytes()
    data = json.loads(raw_bytes)

    entries_raw = data.get("entries", [])
    assert isinstance(entries_raw, list)

    seen_ids: set[str] = set()
    entries: list[ObligationEntry] = []
    for entry_dict in entries_raw:
        assert isinstance(entry_dict, dict)
        entry = _validate_entry(entry_dict)
        if entry.obligation_id in seen_ids:
            raise DuplicateObligationIdError(
                f"duplicate obligation_id {entry.obligation_id!r} in {filename}"
            )
        seen_ids.add(entry.obligation_id)
        entries.append(entry)

    return Registry(
        framework=str(data["framework"]),
        framework_source=str(data["framework_source"]),
        registry_version=int(data["registry_version"]),
        last_reviewed=str(data["last_reviewed"]),
        entries=tuple(entries),
    )


def load_eu_ai_act_article_12() -> Registry:
    """Load the EU AI Act Article 12 obligation registry shipped with this package.

    Returns a :class:`Registry` with eight entries covering Art. 12(1),
    12(2)(a)-(c), and 12(3)(a)-(d). The Annex III biometric subset is the
    primary v0.1 mapping target; the broader Art. 12(2) entries are
    ``designed_toward`` until M6 retention discipline ships.
    """
    return _load_from_resource("eu_ai_act_article_12.json")


def load_dora_article_8() -> Registry:
    """Load the DORA Article 8 obligation registry shipped with this package.

    Returns a :class:`Registry` with five entries covering Art. 8(1)
    (identification + documentation), 8(3) (classification + yearly review),
    8(5) (privileged-access inventory), 8(7) (third-party dependency
    mapping), and 8(8) (records of third-party arrangements). All entries
    are ``designed_toward`` except 8(5) which is ``field_supported``
    (the substrate's ``actor`` field and ``SubjectRef`` type already
    enable the privileged-access recording mechanism).

    The ``regulatory_text`` fields in the underlying JSON are paraphrased
    summaries pending final verbatim verification against OJ L 333,
    27.12.2022. Public-facing material citing any entry must include the
    legal_disclaimer per ``docs/policy/claims_policy.md``.
    """
    return _load_from_resource("dora_article_8.json")


def load_all_registries() -> tuple[Registry, ...]:
    """Load every obligation registry shipped with this package.

    Returns a tuple of all registries in canonical order:

    1. EU AI Act Article 12
    2. DORA Article 8

    Additional frameworks (NIS2, GDPR Art. 30, ISO 42001, NIST AI RMF) will
    extend this tuple at M6+ in append-only order. Verifiers and exporters
    that want to evaluate evidence against every shipped registry use this
    helper rather than enumerating ``load_*`` functions manually.
    """
    return (
        load_eu_ai_act_article_12(),
        load_dora_article_8(),
    )
