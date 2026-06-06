# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coverage-completion tests for attestplane.storage.jsonl + base (target ≥98%)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from attestplane.hashchain import chain_extend, genesis_head
from attestplane.storage import (
    AbstractStorageBackend,
    JsonlStorageBackend,
    StorageBoundaryError,
    StorageReadError,
    StorageWriteError,
)
from attestplane.storage.jsonl import (
    _deserialize_subject,
    _serialize_subject,
)
from attestplane.types import (
    ChainedEvent,
    ChainHead,
    EventDraft,
    SubjectRef,
)


def _build_event(idx: int = 0) -> ChainedEvent:
    ts = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    draft = EventDraft(
        event_type="ai_decision",
        actor=f"agent://test/{idx}",
        payload={"index": idx},
    )
    head = genesis_head()
    return chain_extend(head, draft, now=ts, event_id=f"00000000-0000-7000-8000-{idx:012d}")


def _build_chain(n: int) -> list[ChainedEvent]:
    ts = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    chain: list[ChainedEvent] = []
    head = genesis_head()
    for i in range(n):
        draft = EventDraft(
            event_type="ai_decision",
            actor=f"agent://test/{i}",
            payload={"index": i},
        )
        ev = chain_extend(head, draft, now=ts, event_id=f"00000000-0000-7000-8000-{i:012d}")
        chain.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    return chain


# ── _serialize_subject / _deserialize_subject (lines 47, 53) ─────────────────

def test_serialize_subject_none() -> None:
    # line 46: ref is None → return None
    assert _serialize_subject(None) is None


def test_serialize_subject_present() -> None:
    # line 47: non-None ref → dict
    ref = SubjectRef(scheme="opaque", value="abc-123")
    result = _serialize_subject(ref)
    assert result == {"scheme": "opaque", "value": "abc-123"}


def test_deserialize_subject_none() -> None:
    # line 52: raw is None → return None
    assert _deserialize_subject(None) is None


def test_deserialize_subject_present() -> None:
    # line 53: non-None raw → SubjectRef
    result = _deserialize_subject({"scheme": "opaque", "value": "abc-123"})
    assert result is not None
    assert result.scheme == "opaque"
    assert result.value == "abc-123"


# ── _deserialize_event: non-Z timestamp branch (line 84) ─────────────────────

def test_deserialize_non_z_timestamp(tmp_path: Path) -> None:
    """Line 84: timestamp ends with +00:00 instead of Z."""
    backend = JsonlStorageBackend(tmp_path / "chain.jsonl")
    ev = _build_event(0)
    backend.append(ev)
    backend.close()

    # Patch the Z-suffix to +00:00
    raw = (tmp_path / "chain.jsonl").read_text(encoding="utf-8")
    patched = raw.replace("T12:00:00.000000Z", "T12:00:00.000000+00:00")
    (tmp_path / "chain.jsonl").write_text(patched, encoding="utf-8")

    fresh = JsonlStorageBackend(tmp_path / "chain.jsonl")
    result = fresh.read_all()
    assert len(result) == 1
    assert result[0].event.timestamp == ev.event.timestamp


# ── append error path (lines 178-179): OSError triggers StorageWriteError ────

def test_append_oserror_raises_write_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backend = JsonlStorageBackend(tmp_path / "chain.jsonl")

    def boom(fd: int) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("attestplane.storage.jsonl.os.fsync", boom)
    with pytest.raises(StorageWriteError, match="failed to persist"):
        backend.append(_build_event(0))


# ── scan: read_bytes OSError (lines 193-194) ─────────────────────────────────

def test_scan_read_oserror_raises_read_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "chain.jsonl"
    path.write_text("{}\n", encoding="utf-8")

    original_read_bytes = Path.read_bytes

    def failing_read_bytes(self: Path) -> bytes:
        if self == path:
            raise OSError("permission denied")
        return original_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", failing_read_bytes)
    backend = JsonlStorageBackend(path)
    with pytest.raises(StorageReadError, match="failed to read chain"):
        backend.scan()


# ── scan: invalid UTF-8 (lines 215-224) ──────────────────────────────────────

def test_scan_invalid_utf8_detected(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl"
    # Write a valid line, then a line with invalid UTF-8 bytes
    backend = JsonlStorageBackend(path)
    backend.append(_build_event(0))
    backend.close()

    # Append raw invalid-UTF-8 bytes followed by newline
    with path.open("ab") as f:
        f.write(b"\xff\xfe bad utf8 \n")

    scan = JsonlStorageBackend(path).scan()
    assert scan.ok is False
    assert scan.complete is False
    assert any(i.kind == "invalid_utf8" for i in scan.issues)


# ── scan: unknown storage_record_version (lines 251-262) ─────────────────────

def test_scan_unknown_record_version_detected(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl"
    # Write a JSON line with a future record version
    path.write_text(
        json.dumps(
            {
                "storage_record_version": 99,
                "seq": 0,
                "prev_hash_hex": "a" * 64,
                "event_hash_hex": "b" * 64,
                "event": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    scan = JsonlStorageBackend(path).scan()
    assert scan.ok is False
    assert any(i.kind == "unknown_record_version" for i in scan.issues)


def test_scan_supported_record_version_ok(tmp_path: Path) -> None:
    # version == 1 must NOT cause an issue (the != branch is False → continue)
    backend = JsonlStorageBackend(tmp_path / "chain.jsonl")
    ev = _build_event(0)
    backend.append(ev)
    backend.close()

    # Inject storage_record_version=1 into the written line
    raw = (tmp_path / "chain.jsonl").read_text(encoding="utf-8")
    obj = json.loads(raw.strip())
    obj["storage_record_version"] = 1
    (tmp_path / "chain.jsonl").write_text(json.dumps(obj) + "\n", encoding="utf-8")

    scan = JsonlStorageBackend(tmp_path / "chain.jsonl").scan()
    assert scan.ok is True
    assert len(scan.events) == 1


# ── scan: malformed_event (lines 277-286) ────────────────────────────────────

def test_scan_malformed_event_detected(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl"
    # Valid structure but event sub-dict missing required fields
    path.write_text(
        json.dumps(
            {
                "seq": 0,
                "prev_hash_hex": "a" * 64,
                "event_hash_hex": "b" * 64,
                "event": {"timestamp": "not-a-valid-ts"},  # missing many fields
            }
        )
        + "\n",
        encoding="utf-8",
    )
    scan = JsonlStorageBackend(path).scan()
    assert scan.ok is False
    assert any(i.kind == "malformed_event" for i in scan.issues)


def test_scan_malformed_event_read_all_raises(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl"
    path.write_text(
        json.dumps(
            {
                "seq": 0,
                "prev_hash_hex": "a" * 64,
                "event_hash_hex": "b" * 64,
                "event": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(StorageReadError, match="malformed_event"):
        JsonlStorageBackend(path).read_all()


# ── AbstractStorageBackend abstract method stubs (base.py 107, 118, 128, 136) ─

class _MinimalBackend(AbstractStorageBackend):
    """Minimal concrete subclass to reach the abstract raise NotImplementedError stubs."""

    def append(self, event: ChainedEvent) -> None:
        # Call super() to hit line 107 in base.py
        super().append(event)  # type: ignore[safe-super]

    def read_all(self) -> list[ChainedEvent]:
        # Call super() to hit line 118 in base.py
        return super().read_all()  # type: ignore[safe-super]

    def head(self) -> ChainHead:
        # Call super() to hit line 128 in base.py
        return super().head()  # type: ignore[safe-super]

    def close(self) -> None:
        # Call super() to hit line 136 in base.py (the return)
        super().close()


def test_abstract_append_raises_not_implemented() -> None:
    b = _MinimalBackend()
    with pytest.raises(NotImplementedError):
        b.append(_build_event(0))


def test_abstract_read_all_raises_not_implemented() -> None:
    b = _MinimalBackend()
    with pytest.raises(NotImplementedError):
        b.read_all()


def test_abstract_head_raises_not_implemented() -> None:
    b = _MinimalBackend()
    with pytest.raises(NotImplementedError):
        b.head()


def test_abstract_close_default_returns_none() -> None:
    b = _MinimalBackend()
    b.close()  # returns None implicitly


# ── scan: event with subject_ref and human_verifier present (round-trip) ─────

# ── base.py line 91: StorageBoundaryError raised ─────────────────────────────

def test_boundary_error_raised_on_forbidden_verb() -> None:
    # line 91: offenders non-empty → raise StorageBoundaryError
    with pytest.raises(StorageBoundaryError, match="forbidden mutating method"):
        type(
            "MutatingBackend",
            (AbstractStorageBackend,),
            {
                "append": lambda self, e: None,
                "read_all": lambda self: [],
                "head": lambda self: genesis_head(),
                "delete": lambda self, *a: None,
            },
        )


# ── base.py lines 139, 142: __enter__ / __exit__ ─────────────────────────────

class _ConcreteBackend(AbstractStorageBackend):
    def __init__(self) -> None:
        self._events: list[ChainedEvent] = []

    def append(self, event: ChainedEvent) -> None:
        self._events.append(event)

    def read_all(self) -> list[ChainedEvent]:
        return list(self._events)

    def head(self) -> ChainHead:
        from attestplane.hashchain import head_of

        return head_of(self._events)


def test_abstract_backend_context_manager() -> None:
    # lines 138-142: __enter__ returns self, __exit__ calls close
    b = _ConcreteBackend()
    with b as ctx:
        assert ctx is b  # line 139: __enter__ returns self
    # __exit__ called close() without error (line 142)


def test_abstract_backend_context_manager_with_exception() -> None:
    # __exit__ is called even when an exception propagates
    b = _ConcreteBackend()
    try:
        with b:
            raise ValueError("deliberate")
    except ValueError:
        pass


# ── jsonl.py: _ensure_open_for_append called twice (163->166 branch) ─────────

def test_ensure_open_for_append_handle_reuse(tmp_path: Path) -> None:
    # When _handle is already open, _ensure_open_for_append returns existing handle
    backend = JsonlStorageBackend(tmp_path / "chain.jsonl")
    chain = _build_chain(2)
    backend.append(chain[0])  # opens the handle
    backend.append(chain[1])  # reuses the handle (line 163: _handle is not None → skip)
    backend.close()
    result = JsonlStorageBackend(tmp_path / "chain.jsonl").read_all()
    assert len(result) == 2


# ── jsonl.py: durable=False skips fsync (176->exit) ─────────────────────────

def test_append_durable_false_skips_fsync(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def _fake_fsync(fd: int) -> None:
        calls.append(fd)

    monkeypatch.setattr("attestplane.storage.jsonl.os.fsync", _fake_fsync)
    backend = JsonlStorageBackend(tmp_path / "chain.jsonl", durable=False)
    backend.append(_build_event(0))
    assert calls == []
    result = JsonlStorageBackend(tmp_path / "chain.jsonl").read_all()
    assert len(result) == 1


# ── jsonl.py: scan returns empty on non-existent path (line 190) ─────────────

def test_scan_nonexistent_path_returns_empty(tmp_path: Path) -> None:
    # line 189-190: path doesn't exist → complete=True, no events
    backend = JsonlStorageBackend(tmp_path / "nonexistent.jsonl")
    scan = backend.scan()
    assert scan.ok is True
    assert scan.complete is True
    assert scan.events == ()
    assert scan.issues == ()


# ── jsonl.py: partial_trailing_line (lines 204-212) ─────────────────────────

def test_scan_partial_trailing_line(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl"
    backend = JsonlStorageBackend(path)
    backend.append(_build_event(0))
    backend.close()
    # Append unterminated content
    path.write_bytes(path.read_bytes() + b'{"seq":1')

    scan = JsonlStorageBackend(path).scan()
    assert scan.ok is False
    assert any(i.kind == "partial_trailing_line" for i in scan.issues)
    with pytest.raises(StorageReadError, match="partial_trailing_line"):
        JsonlStorageBackend(path).read_all()


# ── jsonl.py: blank line continue (line 226) ─────────────────────────────────

def test_scan_blank_lines_tolerated(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl"
    backend = JsonlStorageBackend(path)
    backend.append(_build_event(0))
    backend.close()
    content = path.read_text(encoding="utf-8")
    path.write_text(content + "\n\n", encoding="utf-8")

    rehydrated = JsonlStorageBackend(path).read_all()
    assert len(rehydrated) == 1


# ── jsonl.py: malformed JSON (lines 229-238) ─────────────────────────────────

def test_scan_malformed_json_in_cov(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl"
    path.write_text("not valid json\n", encoding="utf-8")
    with pytest.raises(StorageReadError, match="malformed_json"):
        JsonlStorageBackend(path).read_all()


# ── jsonl.py: malformed_record non-dict (lines 240-248) ─────────────────────

def test_scan_non_dict_row_detected(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl"
    path.write_text("[]\n", encoding="utf-8")
    scan = JsonlStorageBackend(path).scan()
    assert any(i.kind == "malformed_record" for i in scan.issues)


# ── jsonl.py: missing_fields (lines 266-274) ─────────────────────────────────

def test_scan_missing_fields_in_cov(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl"
    path.write_text('{"seq":0}\n', encoding="utf-8")
    with pytest.raises(StorageReadError, match="missing_fields"):
        JsonlStorageBackend(path).read_all()


# ── jsonl.py: health_report (lines 302, 307) ─────────────────────────────────

def test_health_report_fields(tmp_path: Path) -> None:
    report: dict[str, Any] = JsonlStorageBackend(tmp_path / "chain.jsonl").health_report()
    assert report["backend"] == "jsonl"
    assert report["jsonl_backend_available"] is True
    assert report["multi_writer_safe"] is False
    assert report["repair_supported"] is False


# ── jsonl.py: head() method (line 302) ───────────────────────────────────────

def test_head_returns_genesis_for_empty(tmp_path: Path) -> None:
    from attestplane.hashchain import genesis_head

    backend = JsonlStorageBackend(tmp_path / "chain.jsonl")
    assert backend.head() == genesis_head()


def test_head_matches_last_appended(tmp_path: Path) -> None:
    backend = JsonlStorageBackend(tmp_path / "chain.jsonl")
    chain = _build_chain(2)
    for ev in chain:
        backend.append(ev)
    head = backend.head()
    assert head.seq == chain[-1].seq
    assert head.event_hash == chain[-1].event_hash


# ── jsonl.py: close when handle is None (322->exit) ─────────────────────────

def test_close_when_no_handle_opened(tmp_path: Path) -> None:
    # handle is None because we never appended
    backend = JsonlStorageBackend(tmp_path / "chain.jsonl")
    backend.close()  # should not raise


def test_close_idempotent_in_cov(tmp_path: Path) -> None:
    backend = JsonlStorageBackend(tmp_path / "chain.jsonl")
    backend.append(_build_event(0))
    backend.close()
    backend.close()  # second close → _handle is None → 322->exit branch


# ── jsonl.py: context manager ────────────────────────────────────────────────

def test_jsonl_context_manager(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl"
    with JsonlStorageBackend(path) as backend:
        backend.append(_build_event(0))
    result = JsonlStorageBackend(path).read_all()
    assert len(result) == 1


def test_round_trip_with_subject_ref_and_human_verifier(tmp_path: Path) -> None:
    """Ensures _serialize_subject non-None path exercised via full round-trip."""
    ts = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    draft = EventDraft(
        event_type="ai_decision",
        actor="agent://test/0",
        payload={"x": 1},
        subject_ref=SubjectRef(scheme="opaque", value="subj-001"),
        human_verifier=SubjectRef(scheme="sha256_salted", value="verifier-hash"),
    )
    ev = chain_extend(genesis_head(), draft, now=ts, event_id="00000000-0000-7000-8000-000000000099")

    backend = JsonlStorageBackend(tmp_path / "chain.jsonl")
    backend.append(ev)
    backend.close()

    result = JsonlStorageBackend(tmp_path / "chain.jsonl").read_all()
    assert len(result) == 1
    r = result[0]
    assert r.event.subject_ref is not None
    assert r.event.subject_ref.scheme == "opaque"
    assert r.event.subject_ref.value == "subj-001"
    assert r.event.human_verifier is not None
    assert r.event.human_verifier.value == "verifier-hash"
