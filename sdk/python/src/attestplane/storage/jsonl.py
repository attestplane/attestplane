# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""JSON Lines file-backed storage backend.

One ``ChainedEvent`` per line; ``fsync()`` on every append. The file
format is deliberately boring so an auditor can read the chain with
``jq`` and an external ``sha256sum`` walker without depending on this
SDK.

The on-disk representation matches the negative-vector fixtures under
``sdk/python/tests/conformance/negative/``: each line is a JSON object
with top-level ``seq``, ``prev_hash_hex``, ``event_hash_hex``, and
``event`` (containing the ``AuditEvent`` fields).

Concurrency: process-local. The backend serialises appends through a
:class:`threading.Lock`. Two processes pointed at the same file path is
undefined behaviour for v1; the JSONL backend is for single-process
deployments. Multi-process / multi-writer needs the storage-backend ADR
(anticipated post-M5) and a database-backed implementation.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from attestplane.hashchain import head_of
from attestplane.storage.base import (
    AbstractStorageBackend,
    StorageReadError,
    StorageWriteError,
)
from attestplane.types import AuditEvent, ChainedEvent, ChainHead, SubjectRef


def _serialize_subject(ref: SubjectRef | None) -> dict[str, str] | None:
    if ref is None:
        return None
    return {"scheme": ref.scheme, "value": ref.value}


def _deserialize_subject(raw: dict[str, Any] | None) -> SubjectRef | None:
    if raw is None:
        return None
    return SubjectRef(scheme=raw["scheme"], value=raw["value"])


def _serialize_event(event: ChainedEvent) -> dict[str, Any]:
    return {
        "seq": event.seq,
        "prev_hash_hex": event.prev_hash.hex(),
        "event_hash_hex": event.event_hash.hex(),
        "event": {
            "schema_version": event.event.schema_version,
            "event_id": event.event.event_id,
            "timestamp": event.event.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
            "event_type": event.event.event_type,
            "actor": event.event.actor,
            "payload": event.event.payload,
            "subject_ref": _serialize_subject(event.event.subject_ref),
            "session_id": event.event.session_id,
            "reference_db_ref": event.event.reference_db_ref,
            "matched_input_ref": event.event.matched_input_ref,
            "human_verifier": _serialize_subject(event.event.human_verifier),
        },
    }


def _deserialize_event(raw: dict[str, Any]) -> ChainedEvent:
    e = raw["event"]
    ts_text = e["timestamp"]
    # Tolerate either explicit Z or +00:00 trailing form on read.
    if ts_text.endswith("Z"):
        ts = datetime.strptime(ts_text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    else:
        ts = datetime.strptime(ts_text, "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(UTC)
    audit = AuditEvent(
        schema_version=e["schema_version"],
        event_id=e["event_id"],
        timestamp=ts,
        event_type=e["event_type"],
        actor=e["actor"],
        payload=e["payload"],
        subject_ref=_deserialize_subject(e.get("subject_ref")),
        session_id=e.get("session_id"),
        reference_db_ref=e.get("reference_db_ref"),
        matched_input_ref=e.get("matched_input_ref"),
        human_verifier=_deserialize_subject(e.get("human_verifier")),
    )
    return ChainedEvent(
        seq=raw["seq"],
        prev_hash=bytes.fromhex(raw["prev_hash_hex"]),
        event_hash=bytes.fromhex(raw["event_hash_hex"]),
        event=audit,
    )


class JsonlStorageBackend(AbstractStorageBackend):
    """File-backed JSON Lines storage; one ChainedEvent per line.

    The file is opened lazily on first ``append`` or ``read_all`` call. A
    fresh backend pointed at a non-existent path returns an empty chain
    from ``read_all`` and creates the file on first append.

    On append: the row is serialised with ``json.dumps(..., separators=(',', ':'), sort_keys=True)`` followed by ``\\n``,
    written with ``write()``, then flushed and ``os.fsync``ed. ``ChainedEvent``
    bytes themselves are not canonical-JSON encoded — they are a convenience
    storage form. Chain integrity is guaranteed by the substrate's
    ``event_hash`` computation, not by this file's exact byte layout.

    Strict-format on read: each line must parse as JSON, contain
    ``seq``, ``prev_hash_hex``, ``event_hash_hex``, and ``event``. Any
    other shape raises :class:`StorageReadError`; the backend never
    silently skips malformed lines.
    """

    __slots__ = ("_path", "_lock", "_handle")

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._handle: Any = None

    def _ensure_open_for_append(self) -> Any:
        if self._handle is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = open(self._path, "a", encoding="utf-8")
        return self._handle

    def append(self, event: ChainedEvent) -> None:
        try:
            with self._lock:
                handle = self._ensure_open_for_append()
                line = json.dumps(
                    _serialize_event(event), separators=(",", ":"), sort_keys=True
                )
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise StorageWriteError(
                f"failed to persist event seq={event.seq} to {self._path}: {exc}"
            ) from exc

    def read_all(self) -> list[ChainedEvent]:
        if not self._path.exists():
            return []
        try:
            text = self._path.read_text(encoding="utf-8")
        except OSError as exc:
            raise StorageReadError(
                f"failed to read chain from {self._path}: {exc}"
            ) from exc

        chain: list[ChainedEvent] = []
        for line_no, raw_line in enumerate(text.splitlines(), start=1):
            if not raw_line.strip():
                continue
            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise StorageReadError(
                    f"{self._path}:{line_no}: not valid JSON: {exc.msg}"
                ) from exc
            required = {"seq", "prev_hash_hex", "event_hash_hex", "event"}
            missing = required - set(obj)
            if missing:
                raise StorageReadError(
                    f"{self._path}:{line_no}: missing required fields {sorted(missing)}"
                )
            try:
                chain.append(_deserialize_event(obj))
            except (KeyError, ValueError, TypeError) as exc:
                raise StorageReadError(
                    f"{self._path}:{line_no}: malformed event row: {exc}"
                ) from exc
        return chain

    def head(self) -> ChainHead:
        return head_of(self.read_all())

    def close(self) -> None:
        with self._lock:
            if self._handle is not None:
                try:
                    self._handle.close()
                finally:
                    self._handle = None
