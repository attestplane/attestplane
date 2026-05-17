# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""LangSmith → Attestplane evidence-event adapter.

Implements ticket #31 of the competitive_positioning_upgrade_plan_20260517.

A LangSmith ``Run`` describes one node of an agent / chain / LLM /
tool execution; this adapter translates one ``Run`` into one
:class:`~attestplane.types.EventDraft` per the v1 evidence taxonomy
(``tool_call_event`` family).

The adapter is **pure** per the
:class:`~attestplane.adapters.GenericRuntimeAdapter` contract: no
I/O, no clock reads, no LangSmith API calls. Callers feed in already-
fetched ``Run`` records (production callers typically pipe
LangSmith's ``Client.list_runs()`` output through this adapter; tests
use the :class:`LangSmithRun` dataclass directly).

Trust boundary (ADR-0004 § 4):

- This adapter lives in the Attestplane OSS substrate tree because
  LangSmith's Run shape is public documentation, not LangChain
  proprietary code. The adapter consumes a shape, not a runtime.
- LangSmith / LangChain do NOT endorse this adapter; it is built
  from publicly documented trace structures per
  ``docs/policy/forbidden_claims.md § G``.

Redaction (mandatory per ADR-0008 § Boundary anti-requirements):

- ``Run.inputs`` and ``Run.outputs`` are NEVER copied into the
  evidence event payload as raw values. They are hashed
  (SHA-256 hex) and the hash is placed in ``arguments_hash`` /
  ``result_hash``.
- Tool / chain names go into ``payload.tool_name``.
- Errors go into ``payload.error_code`` (the LangSmith error string,
  truncated to 200 chars to avoid accidental PII leak from
  exception traces).
- ``parent_run_id`` and ``trace_id`` map to ``session_id``.

Run type → event_type mapping:

| LangSmith ``run_type``       | Attestplane ``event_type`` |
|------------------------------|----------------------------|
| ``tool``                     | ``tool_call_event``        |
| ``llm``                      | ``tool_call_event``        |
| ``chain``                    | ``tool_call_event``        |
| ``retriever``                | ``tool_call_event``        |
| ``prompt``                   | ``tool_call_event``        |
| ``parser``                   | ``tool_call_event``        |
| ``embedding``                | ``tool_call_event``        |
| anything else                | ``tool_call_event`` (with ``payload.kind="unknown"``) |

All run types map to ``tool_call_event`` in v1; future taxonomy
revisions may split (e.g., separate ``llm_call_event`` predicate).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from attestplane.adapters.base import AdapterTranslationError, GenericRuntimeAdapter
from attestplane.event_types import TOOL_CALL_EVENT
from attestplane.types import EventDraft, SubjectRef

_KNOWN_RUN_TYPES: frozenset[str] = frozenset({
    "tool", "llm", "chain", "retriever",
    "prompt", "parser", "embedding",
})


@dataclass(frozen=True, slots=True)
class LangSmithRun:
    """Subset of LangSmith's ``Run`` schema that this adapter consumes.

    Fields follow the public LangSmith API documentation
    (https://docs.smith.langchain.com/). Fields not listed here are
    accepted in the input dict by :meth:`LangSmithAdapter.from_dict`
    but ignored — the adapter is conservative about what it reads.
    """

    id: str
    name: str
    run_type: str
    start_time: datetime
    end_time: datetime | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] | None = None
    error: str | None = None
    trace_id: str | None = None
    parent_run_id: str | None = None
    status: str | None = None
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    end_user_id: str | None = None
    """LangSmith metadata.user_id — wrapped in SubjectRef if present."""


def _hash_json(value: Any) -> str:
    """Deterministic SHA-256 hex of a JSON-serializable value.

    Uses sorted keys + compact separators so equivalent dicts hash
    identically regardless of key insertion order.
    """
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         default=str, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _truncate(text: str, n: int = 200) -> str:
    if len(text) <= n:
        return text
    return text[:n - 3] + "..."


class LangSmithAdapter(GenericRuntimeAdapter[LangSmithRun]):
    """Translates one :class:`LangSmithRun` into one ``EventDraft``."""

    runtime_name = "langsmith"
    schema_version = 1

    def translate(self, runtime_event: LangSmithRun) -> EventDraft:
        if not isinstance(runtime_event, LangSmithRun):
            raise AdapterTranslationError(
                f"expected LangSmithRun, got {type(runtime_event).__name__}"
            )
        run = runtime_event

        # Determine result_status from status / error.
        if run.error:
            result_status = "ERROR"
        elif run.end_time is None and run.status in (None, "in_progress"):
            # Run still running at trace-export time — emit nothing
            # confusing; mark as OK (the runtime will emit the
            # terminal event when it completes).
            result_status = "OK"
        else:
            result_status = "OK"

        kind = run.run_type if run.run_type in _KNOWN_RUN_TYPES else "unknown"

        payload: dict[str, Any] = {
            "kind": kind,
            "tool_name": f"langsmith.{kind}.{run.name}",
            "tool_call_id": run.id,
            "arguments_hash": _hash_json(run.inputs),
            "result_status": result_status,
        }
        if run.outputs is not None:
            payload["result_hash"] = _hash_json(run.outputs)
        if run.end_time is not None:
            duration_ms = int(
                (run.end_time - run.start_time).total_seconds() * 1000
            )
            payload["latency_ms"] = duration_ms
        if run.error:
            payload["error_code"] = _truncate(run.error)
        if run.tags:
            payload["tags"] = list(run.tags)

        subject_ref: SubjectRef | None = None
        if run.end_user_id:
            # Pseudonymize the LangSmith user_id field; sha256_salted
            # is the substrate's strongest scheme. Adapters that have
            # a stable salt pre-hash before passing; we use the raw
            # value here and tag scheme=opaque (the upstream is
            # already an opaque ID, not raw PII).
            subject_ref = SubjectRef(scheme="opaque", value=run.end_user_id)

        # session_id: prefer trace_id (LangSmith trace), fall back to
        # the run's own id (single-event "session").
        session_id = run.trace_id or run.id

        return EventDraft(
            event_type=TOOL_CALL_EVENT,
            actor=f"langsmith://{run.run_type}/{run.name}",
            payload=payload,
            subject_ref=subject_ref,
            session_id=session_id,
            reference_db_ref=run.parent_run_id,
        )

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> LangSmithRun:
        """Build a :class:`LangSmithRun` from a LangSmith API dict.

        Defensive: accepts the public Run schema, ignores fields we
        don't model. Raises :class:`AdapterTranslationError` on
        missing required fields or malformed datetimes.
        """
        required = ("id", "name", "run_type", "start_time")
        missing = [k for k in required if k not in raw]
        if missing:
            raise AdapterTranslationError(
                f"LangSmith run dict missing required fields: {sorted(missing)}"
            )

        def parse_dt(value: Any) -> datetime:
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                # LangSmith uses ISO 8601; some payloads use 'Z' for UTC.
                normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
                try:
                    return datetime.fromisoformat(normalized)
                except ValueError as exc:
                    raise AdapterTranslationError(
                        f"unparsable datetime {value!r}: {exc}"
                    ) from exc
            raise AdapterTranslationError(
                f"datetime field has type {type(value).__name__}, "
                f"expected datetime or ISO string"
            )

        metadata = raw.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise AdapterTranslationError("metadata must be a dict")

        tags_raw = raw.get("tags") or ()
        if not isinstance(tags_raw, (list, tuple)):
            raise AdapterTranslationError("tags must be a list or tuple")

        return LangSmithRun(
            id=str(raw["id"]),
            name=str(raw["name"]),
            run_type=str(raw["run_type"]),
            start_time=parse_dt(raw["start_time"]),
            end_time=parse_dt(raw["end_time"]) if raw.get("end_time") else None,
            inputs=raw.get("inputs") or {},
            outputs=raw.get("outputs"),
            error=raw.get("error"),
            trace_id=raw.get("trace_id"),
            parent_run_id=raw.get("parent_run_id"),
            status=raw.get("status"),
            tags=tuple(str(t) for t in tags_raw),
            metadata=metadata,
            end_user_id=metadata.get("user_id") if isinstance(metadata, dict) else None,
        )


__all__ = [
    "LangSmithAdapter",
    "LangSmithRun",
]
