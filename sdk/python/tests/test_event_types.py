# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for :mod:`attestplane.event_types`.

Locks the v1 taxonomy at the constant-string level. These tests fail if
anyone renames an event-type constant, changes the cardinality of the set,
bumps the taxonomy version without updating the test, or breaks the
``is_known_v1_event_type`` predicate semantics required by ADR-0008.
"""

from __future__ import annotations

import pytest

from attestplane import event_types


def test_taxonomy_version_is_one() -> None:
    assert event_types.EVIDENCE_TAXONOMY_VERSION == 1


# The exact twelve strings, alphabetized by constant name. Any rename here is
# a wire-format change; bumping requires a taxonomy v2 ADR per ADR-0008.
_EXPECTED_V1_PAIRS = {
    "BUDGET_EVENT": "budget_event",
    "EVAL_EVENT": "eval_event",
    "GATEWAY_DECISION_EVENT": "gateway_decision_event",
    "HUMAN_APPROVAL_EVENT": "human_approval_event",
    "LEASE_LIFECYCLE_EVENT": "lease_lifecycle_event",
    "POLICY_CHECK_EVENT": "policy_check_event",
    "ROUTING_EVENT": "routing_event",
    "RUNTIME_LIFECYCLE_EVENT": "runtime_lifecycle_event",
    "SETTLEMENT_EVENT": "settlement_event",
    "STATE_TRANSITION_EVENT": "state_transition_event",
    "TOOL_CALL_EVENT": "tool_call_event",
    "WORKER_ASSIGNMENT_EVENT": "worker_assignment_event",
}


@pytest.mark.parametrize(
    ("constant_name", "expected_value"),
    sorted(_EXPECTED_V1_PAIRS.items()),
)
def test_constant_value(constant_name: str, expected_value: str) -> None:
    assert getattr(event_types, constant_name) == expected_value


def test_set_cardinality_is_twelve() -> None:
    """v1 has exactly twelve event types. A thirteenth requires an ADR amendment."""
    assert len(event_types.ALL_EVENT_TYPES_V1) == 12


def test_set_contents_match_expected() -> None:
    assert event_types.ALL_EVENT_TYPES_V1 == frozenset(_EXPECTED_V1_PAIRS.values())


def test_set_is_immutable() -> None:
    assert isinstance(event_types.ALL_EVENT_TYPES_V1, frozenset)


def test_known_type_returns_true() -> None:
    for known in _EXPECTED_V1_PAIRS.values():
        assert event_types.is_known_v1_event_type(known), known


def test_unknown_type_returns_false() -> None:
    for unknown in ["", "unknown_event", "TOOL_CALL_EVENT", "tool_call",
                    "future_taxonomy_event_v2", "evid"]:
        assert not event_types.is_known_v1_event_type(unknown)


def test_constants_are_importable_from_package_root() -> None:
    """Re-export check — adapters should be able to ``from attestplane import TOOL_CALL_EVENT``."""
    import attestplane

    for name in _EXPECTED_V1_PAIRS:
        assert hasattr(attestplane, name), f"attestplane.{name} not exported"
        assert getattr(attestplane, name) == _EXPECTED_V1_PAIRS[name]

    assert attestplane.EVIDENCE_TAXONOMY_VERSION == 1
    assert attestplane.is_known_v1_event_type("tool_call_event")
