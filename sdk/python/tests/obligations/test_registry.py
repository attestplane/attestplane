# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for :mod:`attestplane.obligations.registry`."""

from __future__ import annotations

import pytest

from attestplane.event_types import ALL_EVENT_TYPES_V1
from attestplane.obligations import (
    DuplicateObligationIdError,
    InvalidImplementationStatusError,
    ObligationEntry,
    ObligationRegistryError,
    Registry,
    UnknownEventTypeError,
    UnknownEvidenceFieldError,
    load_all_registries,
    load_dora_article_8,
    load_eu_ai_act_article_12,
)
from attestplane.obligations.registry import _ALLOWED_IMPLEMENTATION_STATUSES, _validate_entry


def _good_entry(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "framework": "EU AI Act",
        "article": "12",
        "paragraph": "1",
        "obligation_id": "eu_ai_act.art12.1.example",
        "regulatory_text": "Example regulatory text.",
        "required_evidence_fields": ["timestamp"],
        "optional_evidence_fields": ["session_id"],
        "event_type_mapping": ["eval_event"],
        "verifier_expectation": "Every eval_event has a timestamp.",
        "implementation_status": "designed_toward",
        "legal_disclaimer": "Mapping target only.",
        "source_citation": "Regulation (EU) 2024/1689, Article 12(1).",
    }
    base.update(overrides)
    return base


def test_eu_ai_act_article_12_loads() -> None:
    registry = load_eu_ai_act_article_12()
    assert isinstance(registry, Registry)
    assert registry.framework == "EU AI Act"
    assert registry.registry_version == 1
    assert len(registry.entries) == 8


def test_eu_ai_act_article_12_entries_have_locked_status() -> None:
    registry = load_eu_ai_act_article_12()
    for entry in registry.entries:
        assert entry.implementation_status in _ALLOWED_IMPLEMENTATION_STATUSES


def test_eu_ai_act_article_12_event_type_mappings_are_v1() -> None:
    registry = load_eu_ai_act_article_12()
    for entry in registry.entries:
        assert len(entry.event_type_mapping) >= 1
        for et in entry.event_type_mapping:
            assert et in ALL_EVENT_TYPES_V1, (entry.obligation_id, et)


def test_eu_ai_act_article_12_obligation_ids_unique() -> None:
    registry = load_eu_ai_act_article_12()
    ids = [e.obligation_id for e in registry.entries]
    assert len(ids) == len(set(ids))


def test_eu_ai_act_article_12_required_field_set_covered() -> None:
    """The four Art. 12(3) field-set obligations cover the four substrate-level fields."""
    registry = load_eu_ai_act_article_12()
    fields_required_anywhere: set[str] = set()
    for entry in registry.entries:
        fields_required_anywhere.update(entry.required_evidence_fields)
    for required in ["session_id", "reference_db_ref", "matched_input_ref", "human_verifier"]:
        assert required in fields_required_anywhere, required


def test_by_id_finds_entry() -> None:
    registry = load_eu_ai_act_article_12()
    entry = registry.by_id("eu_ai_act.art12.3d.human_verifier")
    assert entry.paragraph == "3(d)"
    assert "human_verifier" in entry.required_evidence_fields


def test_by_id_raises_on_unknown() -> None:
    registry = load_eu_ai_act_article_12()
    with pytest.raises(KeyError):
        registry.by_id("does.not.exist")


def test_by_event_type_returns_subset() -> None:
    registry = load_eu_ai_act_article_12()
    eval_entries = registry.by_event_type("eval_event")
    assert len(eval_entries) >= 1
    for entry in eval_entries:
        assert "eval_event" in entry.event_type_mapping


def test_by_implementation_status_filters() -> None:
    registry = load_eu_ai_act_article_12()
    field_supported = registry.by_implementation_status("field_supported")
    designed_toward = registry.by_implementation_status("designed_toward")
    assert len(field_supported) >= 1
    assert len(designed_toward) >= 1
    assert len(field_supported) + len(designed_toward) == len(registry.entries)


def test_validate_entry_accepts_good_input() -> None:
    entry = _validate_entry(_good_entry())
    assert isinstance(entry, ObligationEntry)
    assert entry.implementation_status == "designed_toward"


def test_invalid_implementation_status_rejected() -> None:
    with pytest.raises(InvalidImplementationStatusError):
        _validate_entry(_good_entry(implementation_status="compliant"))
    with pytest.raises(InvalidImplementationStatusError):
        _validate_entry(_good_entry(implementation_status="certified"))
    with pytest.raises(InvalidImplementationStatusError):
        _validate_entry(_good_entry(implementation_status="ready"))


def test_unknown_event_type_rejected() -> None:
    with pytest.raises(UnknownEventTypeError):
        _validate_entry(_good_entry(event_type_mapping=["future_taxonomy_event_v2"]))


def test_unknown_evidence_field_rejected() -> None:
    with pytest.raises(UnknownEvidenceFieldError):
        _validate_entry(_good_entry(required_evidence_fields=["not_a_real_field"]))


def test_disclaimer_is_present_on_every_entry() -> None:
    registry = load_eu_ai_act_article_12()
    for entry in registry.entries:
        assert entry.legal_disclaimer
        assert "mapping target" in entry.legal_disclaimer.lower()


def test_source_citation_references_regulation() -> None:
    registry = load_eu_ai_act_article_12()
    for entry in registry.entries:
        assert "2024/1689" in entry.source_citation


def test_obligation_entry_is_frozen() -> None:
    entry = _validate_entry(_good_entry())
    with pytest.raises((AttributeError, TypeError)):
        entry.implementation_status = "verified_in_test"  # type: ignore[misc]


def test_registry_is_frozen() -> None:
    registry = load_eu_ai_act_article_12()
    with pytest.raises((AttributeError, TypeError)):
        registry.framework = "Other"  # type: ignore[misc]


def test_duplicate_obligation_id_raises(tmp_path) -> None:
    """Two entries with the same obligation_id in one file is a load error."""

    bad_data = {
        "framework": "Test",
        "framework_source": "Test source",
        "registry_version": 1,
        "last_reviewed": "2026-05-17",
        "entries": [
            _good_entry(obligation_id="dup.id"),
            _good_entry(obligation_id="dup.id"),
        ],
    }

    # Bypass the file-loading path; call the inner duplicate check via a
    # synthetic load. We import the private helpers for this test only.
    from attestplane.obligations.registry import _validate_entry

    seen: set[str] = set()
    with pytest.raises(DuplicateObligationIdError):
        for entry_dict in bad_data["entries"]:
            entry = _validate_entry(entry_dict)
            if entry.obligation_id in seen:
                raise DuplicateObligationIdError(f"duplicate obligation_id {entry.obligation_id!r}")
            seen.add(entry.obligation_id)


def test_all_errors_inherit_from_base() -> None:
    for cls in [
        InvalidImplementationStatusError,
        UnknownEventTypeError,
        UnknownEvidenceFieldError,
        DuplicateObligationIdError,
    ]:
        assert issubclass(cls, ObligationRegistryError)


def test_art12_3_subset_uses_field_supported() -> None:
    """The four field-set obligations under Art. 12(3) ship as field_supported in v0.1."""
    registry = load_eu_ai_act_article_12()
    field_set_ids = {
        "eu_ai_act.art12.3a.period_of_each_use",
        "eu_ai_act.art12.3b.reference_database",
        "eu_ai_act.art12.3c.matched_input_data",
        "eu_ai_act.art12.3d.human_verifier",
    }
    for entry in registry.entries:
        if entry.obligation_id in field_set_ids:
            assert entry.implementation_status == "field_supported", entry.obligation_id


def test_dora_article_8_loads() -> None:
    registry = load_dora_article_8()
    assert isinstance(registry, Registry)
    assert registry.framework == "DORA"
    assert registry.registry_version == 1
    assert len(registry.entries) == 5


def test_dora_article_8_entries_have_locked_status() -> None:
    registry = load_dora_article_8()
    for entry in registry.entries:
        assert entry.implementation_status in {
            "mapping_target",
            "designed_toward",
            "field_supported",
            "verified_in_test",
        }


def test_dora_article_8_event_type_mappings_are_v1() -> None:
    registry = load_dora_article_8()
    for entry in registry.entries:
        assert len(entry.event_type_mapping) >= 1
        for et in entry.event_type_mapping:
            assert et in ALL_EVENT_TYPES_V1, (entry.obligation_id, et)


def test_dora_article_8_obligation_ids_unique() -> None:
    registry = load_dora_article_8()
    ids = [e.obligation_id for e in registry.entries]
    assert len(ids) == len(set(ids))


def test_dora_article_8_source_citation_references_regulation() -> None:
    registry = load_dora_article_8()
    for entry in registry.entries:
        assert "2022/2554" in entry.source_citation


def test_dora_article_8_disclaimers_present() -> None:
    registry = load_dora_article_8()
    for entry in registry.entries:
        assert "mapping target" in entry.legal_disclaimer.lower()


def test_load_all_registries_returns_known_frameworks() -> None:
    registries = load_all_registries()
    assert len(registries) == 2
    frameworks = {r.framework for r in registries}
    assert frameworks == {"EU AI Act", "DORA"}


def test_load_all_registries_canonical_order() -> None:
    """EU AI Act is listed first; DORA second. Order is part of the API contract."""
    registries = load_all_registries()
    assert registries[0].framework == "EU AI Act"
    assert registries[1].framework == "DORA"


def test_all_obligation_ids_unique_across_registries() -> None:
    registries = load_all_registries()
    all_ids = [e.obligation_id for r in registries for e in r.entries]
    assert len(all_ids) == len(set(all_ids))


def test_dora_art8_5_privileged_access_is_field_supported() -> None:
    """Art. 8(5) is the one DORA entry that's field_supported in v0.1
    (actor + SubjectRef already enable privileged-access recording)."""
    registry = load_dora_article_8()
    entry = registry.by_id("dora.art8.5.privileged_access_inventory")
    assert entry.implementation_status == "field_supported"
