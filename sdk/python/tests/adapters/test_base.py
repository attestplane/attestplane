# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for :mod:`attestplane.adapters.base`.

Validates:

1. ``GenericRuntimeAdapter`` is abstract — cannot be instantiated directly.
2. A well-formed concrete subclass works (pure translate, no side effects).
3. Forbidden authority/execution method names are rejected at class
   creation time (``__init_subclass__`` hook).
4. :class:`AdapterTranslationError` is raised by malformed input, not
   silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from attestplane.adapters import (
    AdapterError,
    AdapterTranslationError,
    GenericRuntimeAdapter,
)
from attestplane.types import EventDraft, SubjectRef


@dataclass(frozen=True)
class _MockRuntimeEvent:
    kind: str
    actor_id: str
    user_id_hashed: str


class _MockAdapter(GenericRuntimeAdapter[_MockRuntimeEvent]):
    runtime_name = "mock"
    schema_version = 1

    def translate(self, runtime_event: _MockRuntimeEvent) -> EventDraft:
        if not isinstance(runtime_event, _MockRuntimeEvent):
            raise AdapterTranslationError(
                f"expected _MockRuntimeEvent, got {type(runtime_event).__name__}"
            )
        return EventDraft(
            event_type=f"mock.{runtime_event.kind}",
            actor=runtime_event.actor_id,
            subject_ref=SubjectRef(scheme="sha256_salted", value=runtime_event.user_id_hashed),
            payload={"kind": runtime_event.kind},
        )


def test_abc_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        GenericRuntimeAdapter()  # type: ignore[abstract]


def test_concrete_adapter_translates() -> None:
    adapter = _MockAdapter()
    event = _MockRuntimeEvent(kind="foo", actor_id="agent_1", user_id_hashed="abc123")

    draft = adapter.translate(event)

    assert draft.event_type == "mock.foo"
    assert draft.actor == "agent_1"
    assert draft.subject_ref == SubjectRef(scheme="sha256_salted", value="abc123")
    assert draft.payload == {"kind": "foo"}


def test_concrete_adapter_is_pure() -> None:
    adapter = _MockAdapter()
    event = _MockRuntimeEvent(kind="foo", actor_id="agent_1", user_id_hashed="abc123")

    first = adapter.translate(event)
    second = adapter.translate(event)

    assert first == second


def test_translation_error_on_bad_input() -> None:
    adapter = _MockAdapter()

    with pytest.raises(AdapterTranslationError):
        adapter.translate("not a runtime event")  # type: ignore[arg-type]


def test_translation_error_is_adapter_error() -> None:
    assert issubclass(AdapterTranslationError, AdapterError)


@pytest.mark.parametrize(
    "forbidden_method",
    [
        "execute", "run", "dispatch",
        "grant", "revoke", "issue",
        "decide", "approve", "reject",
        "settle", "charge", "credit",
        "schedule", "allocate",
    ],
)
def test_forbidden_method_rejected_at_subclass_creation(forbidden_method: str) -> None:
    """ADR-0004 § 1: adapters MUST NOT expose authority/execution verbs."""

    def make_bad_subclass() -> None:
        namespace = {
            "runtime_name": "bad",
            "schema_version": 1,
            "translate": lambda self, x: EventDraft(event_type="x", actor="y"),
            forbidden_method: lambda self, *a, **kw: None,
        }
        type("BadAdapter", (GenericRuntimeAdapter,), namespace)

    with pytest.raises(TypeError, match=r"forbidden authority/execution method"):
        make_bad_subclass()


def test_private_methods_with_forbidden_names_are_allowed() -> None:
    """Leading underscore = internal; only the public surface is gated."""

    class AdapterWithPrivateHelper(GenericRuntimeAdapter[_MockRuntimeEvent]):
        runtime_name = "ok"
        schema_version = 1

        def translate(self, runtime_event: _MockRuntimeEvent) -> EventDraft:
            self._execute_internal_check()
            return EventDraft(event_type="x", actor="y")

        def _execute_internal_check(self) -> None:
            pass

    adapter = AdapterWithPrivateHelper()
    draft = adapter.translate(_MockRuntimeEvent(kind="x", actor_id="y", user_id_hashed="z"))
    assert draft.event_type == "x"


def test_aios_spec_module_is_docstring_only() -> None:
    """ADR-0004 § 4: the AIOS adapter spec stub ships no executable surface."""
    import attestplane.adapters.aios_spec as spec

    public_names = [name for name in dir(spec) if not name.startswith("_")]
    assert public_names == [], (
        f"aios_spec.py must remain docstring-only; found public names: {public_names}"
    )
    assert spec.__doc__ is not None and len(spec.__doc__) > 500
