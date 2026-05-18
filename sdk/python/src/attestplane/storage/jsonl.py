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
from dataclasses import dataclass
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

SUPPORTED_STORAGE_RECORD_VERSION = 1
STORAGE_RECORD_VERSION_FIELD = "storage_record_version"


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


@dataclass(frozen=True)
class JsonlStorageIssue:
    """Read-only JSONL scan issue with exact file location."""

    kind: str
    line_no: int
    byte_offset: int
    detail: str


@dataclass(frozen=True)
class JsonlStorageScanResult:
    """Read-only JSONL scan result.

    ``events`` is always the valid prefix before the first corruption issue.
    Corrupt or partial data is never treated as valid chain continuation.
    """

    path: str
    events: tuple[ChainedEvent, ...]
    issues: tuple[JsonlStorageIssue, ...]
    complete: bool

    @property
    def ok(self) -> bool:
        return self.complete and not self.issues


class JsonlStorageBackend(AbstractStorageBackend):
    """File-backed JSON Lines storage; one ChainedEvent per line.

    The file is opened lazily on first ``append`` or ``read_all`` call. A
    fresh backend pointed at a non-existent path returns an empty chain
    from ``read_all`` and creates the file on first append.

    On append: the row is serialised with
    ``json.dumps(..., separators=(',', ':'), sort_keys=True)`` followed by ``\\n``,
    written with ``write()``, then flushed and ``os.fsync``ed. ``ChainedEvent``
    bytes themselves are not canonical-JSON encoded — they are a convenience
    storage form. Chain integrity is guaranteed by the substrate's
    ``event_hash`` computation, not by this file's exact byte layout.

    Strict-format on read: each line must parse as JSON, contain
    ``seq``, ``prev_hash_hex``, ``event_hash_hex``, and ``event``. Any
    other shape raises :class:`StorageReadError`; the backend never
    silently skips malformed lines.
    """

    __slots__ = ("_durable", "_handle", "_lock", "_path")

    def __init__(self, path: str | os.PathLike[str], *, durable: bool = True) -> None:
        self._path = Path(path)
        self._durable = durable
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
                json.loads(line)
                handle.write(line + "\n")
                handle.flush()
                if self._durable:
                    os.fsync(handle.fileno())
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise StorageWriteError(
                f"failed to persist event seq={event.seq} to {self._path}: {exc}"
            ) from exc

    def scan(self) -> JsonlStorageScanResult:
        """Return a read-only scan report.

        The scan never repairs, truncates, or deletes data. On corruption,
        ``events`` contains only the valid prefix before the first issue and
        ``complete`` is false.
        """

        if not self._path.exists():
            return JsonlStorageScanResult(
                path=str(self._path), events=(), issues=(), complete=True
            )
        try:
            data = self._path.read_bytes()
        except OSError as exc:
            raise StorageReadError(
                f"failed to read chain from {self._path}: {exc}"
            ) from exc

        chain: list[ChainedEvent] = []
        issues: list[JsonlStorageIssue] = []
        byte_offset = 0
        for line_no, raw_bytes in enumerate(data.splitlines(keepends=True), start=1):
            line_offset = byte_offset
            byte_offset += len(raw_bytes)
            has_newline = raw_bytes.endswith(b"\n") or raw_bytes.endswith(b"\r\n")
            if not has_newline:
                issues.append(JsonlStorageIssue(
                    kind="partial_trailing_line",
                    line_no=line_no,
                    byte_offset=line_offset,
                    detail="final JSONL record is not newline-terminated",
                ))
                break
            try:
                raw_line = raw_bytes.rstrip(b"\r\n").decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                issues.append(JsonlStorageIssue(
                    kind="invalid_utf8",
                    line_no=line_no,
                    byte_offset=line_offset,
                    detail=str(exc),
                ))
                break
            if not raw_line.strip():
                continue
            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                issues.append(JsonlStorageIssue(
                    kind="malformed_json",
                    line_no=line_no,
                    byte_offset=line_offset,
                    detail=exc.msg,
                ))
                break
            if not isinstance(obj, dict):
                issues.append(JsonlStorageIssue(
                    kind="malformed_record",
                    line_no=line_no,
                    byte_offset=line_offset,
                    detail="JSONL row must be an object",
                ))
                break
            version = obj.get(STORAGE_RECORD_VERSION_FIELD)
            if version is not None and version != SUPPORTED_STORAGE_RECORD_VERSION:
                issues.append(JsonlStorageIssue(
                    kind="unknown_record_version",
                    line_no=line_no,
                    byte_offset=line_offset,
                    detail=(
                        f"unsupported {STORAGE_RECORD_VERSION_FIELD}={version!r}; "
                        f"supported={SUPPORTED_STORAGE_RECORD_VERSION}"
                    ),
                ))
                break
            required = {"seq", "prev_hash_hex", "event_hash_hex", "event"}
            missing = required - set(obj)
            if missing:
                issues.append(JsonlStorageIssue(
                    kind="missing_fields",
                    line_no=line_no,
                    byte_offset=line_offset,
                    detail=f"missing required fields {sorted(missing)}",
                ))
                break
            try:
                chain.append(_deserialize_event(obj))
            except (KeyError, ValueError, TypeError) as exc:
                issues.append(JsonlStorageIssue(
                    kind="malformed_event",
                    line_no=line_no,
                    byte_offset=line_offset,
                    detail=str(exc),
                ))
                break
        return JsonlStorageScanResult(
            path=str(self._path),
            events=tuple(chain),
            issues=tuple(issues),
            complete=not issues,
        )

    def read_all(self) -> list[ChainedEvent]:
        scan = self.scan()
        if scan.issues:
            issue = scan.issues[0]
            raise StorageReadError(
                f"{self._path}:{issue.line_no}@{issue.byte_offset}: "
                f"{issue.kind}: {issue.detail}"
            )
        return list(scan.events)

    def head(self) -> ChainHead:
        return head_of(self.read_all())

    def health_report(self) -> dict[str, Any]:
        """Report JSONL backend capabilities without making production claims."""

        return {
            "backend": "jsonl",
            "path": str(self._path),
            "jsonl_backend_available": True,
            "durable_fsync_enabled": self._durable,
            "fsync_supported": hasattr(os, "fsync"),
            "file_lock_supported": False,
            "multi_writer_safe": False,
            "concurrent_append_behavior": "single_process_thread_lock_only",
            "repair_supported": False,
            "destructive_repair_supported": False,
        }

    def close(self) -> None:
        with self._lock:
            if self._handle is not None:
                try:
                    self._handle.close()
                finally:
                    self._handle = None
