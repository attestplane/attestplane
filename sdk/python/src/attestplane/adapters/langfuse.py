# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""LangFuse → Attestplane evidence-event adapter.

Implements ticket #32 of the competitive_positioning_upgrade_plan_20260517.

A LangFuse ``Observation`` describes one node of an agent / chain /
LLM / tool execution (LangFuse's data model is Trace → Observations).
This adapter translates one ``Observation`` into one
:class:`~attestplane.types.EventDraft` per the v1 evidence taxonomy.

The adapter is **pure** per the
:class:`~attestplane.adapters.GenericRuntimeAdapter` contract: no
I/O, no clock reads, no LangFuse API calls.

Trust boundary (ADR-0004 § 4):

- This adapter lives in the Attestplane OSS substrate tree because
  LangFuse's observation shape is public documentation (LangFuse
  itself is MIT-licensed OSS).
- LangFuse / ClickHouse (its acquirer per the 2026-05-17
  competitive research) do not endorse this adapter; it is built
  from publicly documented trace structures per
  ``docs/policy/forbidden_claims.md § G``.

Redaction (mandatory per ADR-0008 § Boundary anti-requirements):

- ``Observation.input`` and ``Observation.output`` are NEVER copied
  into the evidence event payload as raw values. They are hashed
  (SHA-256 hex) and the hash is placed in ``arguments_hash`` /
  ``result_hash``.
- Generation / span / event name goes into ``payload.tool_name``.
- ``status_message`` is truncated to 200 chars before being placed
  in ``error_code``.
- LangFuse ``Trace.user_id`` is wrapped in :class:`~attestplane.types.SubjectRef`.

Observation type → event_type mapping:

| LangFuse ``type``      | Attestplane ``event_type`` | Notes |
|------------------------|----------------------------|-------|
| ``GENERATION``         | ``tool_call_event``        | LLM call |
| ``SPAN``               | ``tool_call_event``        | wrapper span; broad |
| ``EVENT``              | ``tool_call_event``        | logical event marker |

Level → result_status mapping:

| LangFuse ``level``     | Attestplane ``result_status`` |
|------------------------|-------------------------------|
| ``DEFAULT`` / ``DEBUG``| ``OK``                        |
| ``WARNING``            | ``OK`` (warnings are not errors) |
| ``ERROR``              | ``ERROR``                     |
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from attestplane.adapters.base import AdapterTranslationError, GenericRuntimeAdapter
from attestplane.event_types import TOOL_CALL_EVENT
from attestplane.types import EventDraft, SubjectRef

_KNOWN_OBSERVATION_TYPES: frozenset[str] = frozenset(
    {
        "GENERATION",
        "SPAN",
        "EVENT",
    }
)

_KNOWN_LEVELS: frozenset[str] = frozenset(
    {
        "DEFAULT",
        "DEBUG",
        "WARNING",
        "ERROR",
    }
)


@dataclass(frozen=True, slots=True)
class LangFuseObservation:
    """Subset of LangFuse's ``Observation`` schema that this adapter consumes.

    Fields follow the public LangFuse Python/JS SDK observation
    schema (https://langfuse.com/docs).
    """

    id: str
    trace_id: str
    type: str  # "GENERATION" | "SPAN" | "EVENT"
    name: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    input: Any = None
    output: Any = None
    level: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    status_message: str | None = None
    model: str | None = None
    """For GENERATION type: the LLM model name (e.g., 'gpt-4o-mini')."""

    user_id: str | None = None
    """LangFuse Trace.user_id propagated to the observation level for
    SubjectRef wrapping."""


def _hash_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _truncate(text: str, n: int = 200) -> str:
    if len(text) <= n:
        return text
    return text[: n - 3] + "..."


def _level_to_status(level: str | None) -> Literal["OK", "ERROR"]:
    if level == "ERROR":
        return "ERROR"
    return "OK"


class LangFuseAdapter(GenericRuntimeAdapter[LangFuseObservation]):
    """Translates one :class:`LangFuseObservation` into one ``EventDraft``."""

    runtime_name = "langfuse"
    schema_version = 1

    def translate(self, runtime_event: LangFuseObservation) -> EventDraft:
        if not isinstance(runtime_event, LangFuseObservation):
            raise AdapterTranslationError(f"expected LangFuseObservation, got {type(runtime_event).__name__}")
        obs = runtime_event

        if obs.type not in _KNOWN_OBSERVATION_TYPES:
            kind = "unknown"
        else:
            kind = obs.type.lower()

        result_status = _level_to_status(obs.level)

        payload: dict[str, Any] = {
            "kind": kind,
            "tool_name": f"langfuse.{kind}.{obs.name or 'unnamed'}",
            "tool_call_id": obs.id,
            "result_status": result_status,
        }
        if obs.input is not None:
            payload["arguments_hash"] = _hash_json(obs.input)
        else:
            # Schema-level requirement: tool_call_event always has
            # arguments_hash. Use the empty-dict hash for null input.
            payload["arguments_hash"] = _hash_json({})

        if obs.output is not None:
            payload["result_hash"] = _hash_json(obs.output)

        if obs.start_time is not None and obs.end_time is not None:
            duration_ms = int((obs.end_time - obs.start_time).total_seconds() * 1000)
            payload["latency_ms"] = duration_ms

        if obs.status_message and result_status == "ERROR":
            payload["error_code"] = _truncate(obs.status_message)

        if obs.model:
            # Generation-type observations carry the LLM model name as
            # a tool version; producers may further use it for cost
            # tracking but Attestplane only records the identifier.
            payload["tool_version"] = obs.model

        if obs.level and obs.level in _KNOWN_LEVELS and obs.level != "DEFAULT":
            payload["level"] = obs.level

        subject_ref: SubjectRef | None = None
        if obs.user_id:
            subject_ref = SubjectRef(scheme="opaque", value=obs.user_id)

        return EventDraft(
            event_type=TOOL_CALL_EVENT,
            actor=f"langfuse://{kind}/{obs.name or 'unnamed'}",
            payload=payload,
            subject_ref=subject_ref,
            session_id=obs.trace_id,
        )

    @staticmethod
    def from_dict(
        raw: dict[str, Any],
        *,
        user_id: str | None = None,
    ) -> LangFuseObservation:
        """Build a :class:`LangFuseObservation` from a LangFuse API dict.

        ``user_id`` is passed separately because LangFuse stores it
        on the parent ``Trace`` rather than the ``Observation``; the
        caller typically fetches both and threads ``Trace.user_id``
        through this kwarg.
        """
        required = ("id", "trace_id", "type")
        missing = [k for k in required if k not in raw]
        if missing:
            raise AdapterTranslationError(f"LangFuse observation dict missing required fields: {sorted(missing)}")

        def parse_dt(value: Any) -> datetime:
            if value is None:
                return None  # type: ignore[return-value]
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
                try:
                    return datetime.fromisoformat(normalized)
                except ValueError as exc:
                    raise AdapterTranslationError(f"unparsable datetime {value!r}: {exc}") from exc
            raise AdapterTranslationError(f"datetime field has type {type(value).__name__}")

        metadata = raw.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise AdapterTranslationError("metadata must be a dict")

        return LangFuseObservation(
            id=str(raw["id"]),
            trace_id=str(raw["trace_id"]),
            type=str(raw["type"]),
            name=raw.get("name"),
            start_time=parse_dt(raw.get("start_time")) if raw.get("start_time") else None,
            end_time=parse_dt(raw.get("end_time")) if raw.get("end_time") else None,
            input=raw.get("input"),
            output=raw.get("output"),
            level=raw.get("level"),
            metadata=metadata,
            status_message=raw.get("status_message"),
            model=raw.get("model"),
            user_id=user_id,
        )


__all__ = [
    "LangFuseAdapter",
    "LangFuseObservation",
]
