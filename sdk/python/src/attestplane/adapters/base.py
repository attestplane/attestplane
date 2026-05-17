# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Abstract runtime-adapter base class.

Per ADR-0004 § 1 ("Universal rule"):

    Any AIOS surface whose primary semantic is authority or execution stays
    in AIOS. Attestplane only ever records the event of a decision having
    been made, never owns the decision.

A :class:`GenericRuntimeAdapter` translates one runtime-specific event into
one :class:`~attestplane.types.EventDraft`. That is the only verb it owns.
The ABC deliberately exposes no ``execute()``, ``grant()``, or ``decide()``
method — those would be authority/execution semantics and have no place on
the substrate.

Concrete adapters (AIOS, LangGraph, Claude Code SDK, …) live in their
respective execution-plane repositories or in ``attestplane-contrib``, not
in the substrate OSS tree.

This module is part of the Spec-Only Phase 0 deliverable (migration plan
ticket #3). v0.1 (M5) ships the ABC; concrete adapters arrive later under
the dependency direction locked in ADR-0004 § 4.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from attestplane.types import EventDraft


class AdapterError(Exception):
    """Base class for any adapter-raised error."""


class AdapterTranslationError(AdapterError):
    """A runtime event could not be translated into an ``EventDraft``.

    Raised by :meth:`GenericRuntimeAdapter.translate` when the input does not
    satisfy the adapter's contract — e.g., a malformed runtime event, an
    event whose type the adapter does not know how to map, or an event whose
    declared subject reference cannot be pseudonymized into a
    :class:`~attestplane.types.SubjectRef` without violating GDPR
    Art. 4(5).

    Adapters MUST raise this (or a subclass) rather than returning a
    partially-populated ``EventDraft`` or silently dropping the event.
    Silent drops would defeat the point of a substrate.
    """


RuntimeEvent = TypeVar("RuntimeEvent")
"""The runtime-specific event type that a concrete adapter consumes.

There is no shared base class for runtime events because the substrate has
no business knowing what an AIOS lease event, a LangGraph node-finish event,
or an MCP tool-call event looks like at the type level. Each concrete
adapter parameterizes this TypeVar with its own runtime's event type.
"""


class GenericRuntimeAdapter(ABC, Generic[RuntimeEvent]):
    """Abstract base for any execution-plane → Attestplane adapter.

    The contract is intentionally narrow:

    1. :meth:`translate` is the only required method.
    2. :meth:`translate` is a **pure function**: given the same input it
       returns the same output. No I/O, no side effects, no clock reads, no
       random number generation, no calls into the runtime.
    3. The returned :class:`~attestplane.types.EventDraft` is the
       caller-provided portion of the audit event. The substrate
       (via :class:`~attestplane.substrate.AttestSubstrate.append`) assigns
       ``event_id``, ``timestamp``, ``seq``, ``prev_hash`` and
       ``event_hash``. Adapters do not produce those fields.
    4. Adapters do not execute, grant, decide, or otherwise affect runtime
       state. The ABC enforces this by exposing no method that could.

    Implementations declare two metadata properties for substrate-side
    diagnostics:

    - :attr:`runtime_name` — short stable identifier for the runtime, e.g.
      ``"aios"``, ``"langgraph"``, ``"claude_code"``. Recommended to match
      the corresponding evidence event's ``actor`` field prefix.
    - :attr:`schema_version` — the version of the runtime's event schema
      that this adapter targets. Bump when the upstream runtime changes its
      event shape; the substrate uses this to detect drift.

    Example skeleton::

        class MyRuntimeAdapter(GenericRuntimeAdapter[MyRuntimeEvent]):
            runtime_name = "my_runtime"
            schema_version = 1

            def translate(self, runtime_event: MyRuntimeEvent) -> EventDraft:
                if not isinstance(runtime_event, MyRuntimeEvent):
                    raise AdapterTranslationError(
                        f"expected MyRuntimeEvent, got {type(runtime_event).__name__}"
                    )
                return EventDraft(
                    event_type=f"my_runtime.{runtime_event.kind}",
                    actor=runtime_event.actor_id,
                    payload={"kind": runtime_event.kind, ...},
                )

    Concrete adapters MUST NOT add public methods that imply authority or
    execution. The following names are reserved and any subclass defining
    them at the public level (no leading underscore) is an ADR-0004
    boundary violation and the PR introducing it must be rejected:

    - ``execute``, ``run``, ``dispatch``
    - ``grant``, ``revoke``, ``issue``
    - ``decide``, ``approve``, ``reject``
    - ``settle``, ``charge``, ``credit``
    - ``schedule``, ``allocate``
    """

    runtime_name: str
    schema_version: int

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        forbidden = {
            "execute", "run", "dispatch",
            "grant", "revoke", "issue",
            "decide", "approve", "reject",
            "settle", "charge", "credit",
            "schedule", "allocate",
        }
        offenders = sorted(
            name for name in vars(cls)
            if not name.startswith("_") and name in forbidden
        )
        if offenders:
            raise TypeError(
                f"{cls.__name__} defines forbidden authority/execution method(s) "
                f"{offenders}; adapters may only translate events. See ADR-0004 § 1."
            )

    @abstractmethod
    def translate(self, runtime_event: RuntimeEvent) -> EventDraft:
        """Translate one runtime-specific event into one ``EventDraft``.

        Implementations MUST:

        - Raise :class:`AdapterTranslationError` on any input the adapter
          cannot map. Never return ``None`` or a partially-populated draft.
        - Be pure: same input → same output, no I/O, no clock reads.
        - Apply pseudonymization at the boundary: any direct identifier in
          ``runtime_event`` that maps to a data subject MUST be wrapped in
          :class:`~attestplane.types.SubjectRef` with an appropriate
          ``scheme`` before being placed in the returned draft. The
          substrate's type system enforces this for the dedicated subject
          fields; the adapter is responsible for not smuggling raw PII into
          ``payload``.
        - Not call into the runtime to fetch additional context. If the
          runtime event lacks information the adapter needs, the runtime
          must emit a richer event — not the adapter.
        """
        raise NotImplementedError
