# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for :class:`attestplane.storage.jsonl.JsonlStorageBackend` and
:class:`attestplane.storage.base.AbstractStorageBackend`."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from attestplane.hashchain import chain_extend, genesis_head, verify_chain
from attestplane.storage import (
    AbstractStorageBackend,
    JsonlStorageBackend,
    StorageBoundaryError,
    StorageError,
    StorageReadError,
)
from attestplane.types import ChainedEvent, ChainHead, EventDraft


def _build_chain(n: int) -> list[ChainedEvent]:
    ts = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    chain: list[ChainedEvent] = []
    head: ChainHead = genesis_head()
    for i in range(n):
        draft = EventDraft(
            event_type="ai_decision",
            actor=f"agent://test/{i}",
            payload={"index": i},
        )
        event = chain_extend(head, draft, now=ts,
                             event_id=f"00000000-0000-7000-8000-{i:012d}")
        chain.append(event)
        head = ChainHead(seq=event.seq, event_hash=event.event_hash)
    return chain


def test_empty_backend_reads_empty(tmp_path: Path) -> None:
    backend = JsonlStorageBackend(tmp_path / "chain.jsonl")
    assert backend.read_all() == []
    assert backend.head() == genesis_head()


def test_append_then_read_round_trips(tmp_path: Path) -> None:
    backend = JsonlStorageBackend(tmp_path / "chain.jsonl")
    original = _build_chain(3)
    for event in original:
        backend.append(event)

    rehydrated = backend.read_all()

    assert len(rehydrated) == 3
    for actual, expected in zip(rehydrated, original, strict=True):
        assert actual.seq == expected.seq
        assert actual.prev_hash == expected.prev_hash
        assert actual.event_hash == expected.event_hash
        assert actual.event == expected.event


def test_rehydrated_chain_verifies(tmp_path: Path) -> None:
    backend = JsonlStorageBackend(tmp_path / "chain.jsonl")
    for event in _build_chain(5):
        backend.append(event)

    result = verify_chain(backend.read_all())
    assert result.ok is True
    assert result.first_bad_index is None


def test_head_matches_last_append(tmp_path: Path) -> None:
    backend = JsonlStorageBackend(tmp_path / "chain.jsonl")
    chain = _build_chain(2)
    for event in chain:
        backend.append(event)

    head = backend.head()
    assert head.seq == chain[-1].seq
    assert head.event_hash == chain[-1].event_hash


def test_persistence_across_instances(tmp_path: Path) -> None:
    """Closing and reopening at the same path yields the same chain."""
    path = tmp_path / "chain.jsonl"
    backend = JsonlStorageBackend(path)
    chain = _build_chain(2)
    for event in chain:
        backend.append(event)
    backend.close()

    fresh = JsonlStorageBackend(path)
    assert fresh.read_all() == chain


def test_context_manager_closes_file(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl"
    with JsonlStorageBackend(path) as backend:
        backend.append(_build_chain(1)[0])
    # File should be closed; second open should work without errors.
    fresh = JsonlStorageBackend(path)
    assert len(fresh.read_all()) == 1


def test_malformed_line_raises_read_error(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl"
    path.write_text("not valid json\n", encoding="utf-8")
    backend = JsonlStorageBackend(path)

    with pytest.raises(StorageReadError, match="malformed_json"):
        backend.read_all()


def test_missing_field_raises_read_error(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl"
    path.write_text('{"seq":0}\n', encoding="utf-8")
    backend = JsonlStorageBackend(path)

    with pytest.raises(StorageReadError, match="missing_fields"):
        backend.read_all()


def test_blank_lines_tolerated(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl"
    backend = JsonlStorageBackend(path)
    chain = _build_chain(2)
    for event in chain:
        backend.append(event)

    # Manually inject a blank line.
    content = path.read_text(encoding="utf-8")
    path.write_text(content + "\n\n", encoding="utf-8")

    rehydrated = backend.read_all()
    assert len(rehydrated) == 2


@pytest.mark.parametrize(
    "forbidden_method",
    ["delete", "remove", "purge", "truncate",
     "update", "mutate", "rewrite", "overwrite", "compact"],
)
def test_forbidden_mutating_verb_rejected(forbidden_method: str) -> None:
    """ADR-0002 § immutability: storage backends MUST NOT expose mutating verbs."""

    def make_bad_subclass() -> None:
        namespace = {
            "append": lambda self, event: None,
            "read_all": lambda self: [],
            "head": lambda self: genesis_head(),
            forbidden_method: lambda self, *a, **kw: None,
        }
        type("BadBackend", (AbstractStorageBackend,), namespace)

    with pytest.raises(StorageBoundaryError, match="forbidden mutating method"):
        make_bad_subclass()


def test_private_method_with_forbidden_stem_allowed() -> None:
    """Leading underscore exempts from the boundary check."""

    class BackendWithPrivateHelper(AbstractStorageBackend):
        def __init__(self) -> None:
            self._events: list[ChainedEvent] = []

        def append(self, event: ChainedEvent) -> None:
            self._delete_old_cache_if_any()
            self._events.append(event)

        def read_all(self) -> list[ChainedEvent]:
            return list(self._events)

        def head(self) -> ChainHead:
            from attestplane.hashchain import head_of
            return head_of(self._events)

        def _delete_old_cache_if_any(self) -> None:
            return

    backend = BackendWithPrivateHelper()
    backend.append(_build_chain(1)[0])
    assert len(backend.read_all()) == 1


def test_abstract_backend_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        AbstractStorageBackend()  # type: ignore[abstract]


def test_close_is_idempotent(tmp_path: Path) -> None:
    backend = JsonlStorageBackend(tmp_path / "chain.jsonl")
    backend.append(_build_chain(1)[0])
    backend.close()
    backend.close()  # second call must not raise


def test_storage_error_hierarchy() -> None:
    from attestplane.storage import StorageWriteError

    assert issubclass(StorageReadError, StorageError)
    assert issubclass(StorageWriteError, StorageError)


def test_appending_after_close_reopens(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl"
    backend = JsonlStorageBackend(path)
    chain = _build_chain(2)
    backend.append(chain[0])
    backend.close()
    backend.append(chain[1])
    backend.close()

    rehydrated = JsonlStorageBackend(path).read_all()
    assert rehydrated == chain


def test_append_writes_newline_terminated_record(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl"
    JsonlStorageBackend(path).append(_build_chain(1)[0])

    data = path.read_bytes()

    assert data.endswith(b"\n")
    assert len(data.splitlines()) == 1


def test_append_fsync_called_when_durable_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []

    def fake_fsync(fd: int) -> None:
        calls.append(fd)

    monkeypatch.setattr("attestplane.storage.jsonl.os.fsync", fake_fsync)
    JsonlStorageBackend(tmp_path / "chain.jsonl", durable=True).append(_build_chain(1)[0])

    assert len(calls) == 1


def test_append_skips_fsync_when_durable_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []

    def fake_fsync(fd: int) -> None:
        calls.append(fd)

    monkeypatch.setattr("attestplane.storage.jsonl.os.fsync", fake_fsync)
    JsonlStorageBackend(tmp_path / "chain.jsonl", durable=False).append(_build_chain(1)[0])

    assert calls == []


def test_partial_trailing_line_detected_with_byte_offset(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl"
    backend = JsonlStorageBackend(path)
    backend.append(_build_chain(1)[0])
    backend.close()
    path.write_bytes(path.read_bytes() + b'{"seq":1')

    scan = JsonlStorageBackend(path).scan()

    assert scan.ok is False
    assert scan.complete is False
    assert len(scan.events) == 1
    assert scan.issues[0].kind == "partial_trailing_line"
    assert scan.issues[0].line_no == 2
    with pytest.raises(StorageReadError, match="partial_trailing_line"):
        JsonlStorageBackend(path).read_all()


def test_malformed_json_middle_line_reports_valid_prefix(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl"
    backend = JsonlStorageBackend(path)
    chain = _build_chain(2)
    for event in chain:
        backend.append(event)
    backend.close()
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(f"{lines[0]}\nnot valid json\n{lines[1]}\n", encoding="utf-8")

    scan = JsonlStorageBackend(path).scan()

    assert scan.ok is False
    assert scan.complete is False
    assert list(scan.events) == [chain[0]]
    assert scan.issues[0].kind == "malformed_json"
    assert scan.issues[0].line_no == 2


def test_malformed_record_line_detected(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl"
    path.write_text("[]\n", encoding="utf-8")

    scan = JsonlStorageBackend(path).scan()

    assert scan.issues[0].kind == "malformed_record"


def test_health_report_declares_alpha_concurrency_semantics(tmp_path: Path) -> None:
    report: dict[str, Any] = JsonlStorageBackend(tmp_path / "chain.jsonl").health_report()

    assert report["jsonl_backend_available"] is True
    assert report["durable_fsync_enabled"] is True
    assert report["multi_writer_safe"] is False
    assert report["file_lock_supported"] is False
    assert report["concurrent_append_behavior"] == "single_process_thread_lock_only"
    assert report["repair_supported"] is False
