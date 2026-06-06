# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
"""SQLite audit log and pipeline-state store for autodev-train."""

import logging
import os
import socket
import sqlite3
import threading
import weakref
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_log = logging.getLogger("autodev.db")

DB_PATH = Path(os.environ.get(
    "AUTODEV_DB_PATH",
    Path(__file__).resolve().parents[3] / "data" / "autodev_state.db"
))

_MERGE_LOCK_TTL = 3000  # seconds — must exceed merge_pr start_to_close_timeout (2700s = 45min)
# so a legitimate long-running merge never loses its lock to a TTL-based eviction. (H1 fix)

_DDL = """
CREATE TABLE IF NOT EXISTS pipeline_merge_lock (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    holder_pid   INTEGER NOT NULL,
    holder_host  TEXT    NOT NULL,
    workflow_id  TEXT    NOT NULL,
    run_id       TEXT    NOT NULL,
    pr_number    INTEGER NOT NULL DEFAULT 0,
    acquired_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    issue_number  INTEGER PRIMARY KEY,
    workflow_id   TEXT,
    stage         TEXT    NOT NULL DEFAULT 'pending',
    pr_number     INTEGER,
    branch        TEXT,
    review_decision TEXT,
    error         TEXT,
    impl_commit_sha TEXT,
    retry_count   INTEGER DEFAULT 0,
    created_at    TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at    TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS stage_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_number  INTEGER NOT NULL,
    stage         TEXT    NOT NULL,
    status        TEXT    NOT NULL,
    detail        TEXT    DEFAULT '',
    created_at    TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_stage_events_issue
    ON stage_events(issue_number, created_at);
"""


_local = threading.local()

# Track every open connection across threads so checkpoint_all() can WAL-flush them all
# without needing each thread to submit a task to itself. WeakSet entries auto-expire when
# the connection object is GC'd (i.e. after checkpoint_and_close() clears _local.conn). (C1 fix)
_all_conns: weakref.WeakSet[sqlite3.Connection] = weakref.WeakSet()
_all_conns_lock = threading.Lock()

# Cached once so each new thread connection doesn't re-attempt the migration DDL. (L8 fix)
_impl_sha_migrated = False
_impl_sha_lock = threading.Lock()

# Dedicated connection + mutex for merge-lock operations.
# Using a single connection (not thread-local) ensures the ROLLBACK guard in
# acquire_merge_lock operates on the same connection that held the prior transaction,
# regardless of which asyncio.to_thread worker thread dispatches the call. (H2 fix)
_merge_lock_mu = threading.Lock()
_merge_lock_conn: sqlite3.Connection | None = None


def _get_lock_conn() -> sqlite3.Connection:
    global _merge_lock_conn
    if _merge_lock_conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _merge_lock_conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _merge_lock_conn.row_factory = sqlite3.Row
        _merge_lock_conn.execute("PRAGMA journal_mode=WAL")
        _merge_lock_conn.execute("PRAGMA busy_timeout=5000")  # H2 fix: avoid spurious SQLITE_BUSY under writer contention
        with _all_conns_lock:
            _all_conns.add(_merge_lock_conn)  # L2 fix: include in checkpoint_all() sweep
    return _merge_lock_conn


def _conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA busy_timeout=5000")  # H2 fix: avoid spurious SQLITE_BUSY
        _local.conn.executescript(_DDL)
        # Migrate existing DBs: add impl_commit_sha if missing.
        # Double-checked locking avoids redundant ALTER attempts after the first thread
        # confirms the migration. (L8 fix)
        global _impl_sha_migrated
        if not _impl_sha_migrated:
            with _impl_sha_lock:
                if not _impl_sha_migrated:
                    try:
                        _local.conn.execute(
                            "ALTER TABLE pipeline_runs ADD COLUMN impl_commit_sha TEXT"
                        )
                        _local.conn.commit()
                    except sqlite3.OperationalError:
                        pass  # column already exists in DDL or prior migration
                    _impl_sha_migrated = True
        with _all_conns_lock:
            _all_conns.add(_local.conn)
    return _local.conn


def upsert_run(issue_number: int, **kwargs) -> None:
    """Upsert a pipeline_runs row.

    None is only valid for *nullable* columns in the UPDATE path — passing None explicitly
    clears that column to SQL NULL (e.g. error=None after a successful stage transition).
    NOT NULL columns (stage, updated_at) must never receive None; the INSERT path filters
    them out but the UPDATE path will write SQL NULL and violate the schema constraint. (M3)
    """
    kwargs["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # INSERT: exclude None to respect NOT NULL schema defaults (e.g. stage TEXT NOT NULL).
    insert_kwargs = {k: v for k, v in kwargs.items() if v is not None or k == "updated_at"}
    # UPDATE: include None as SQL NULL so callers can explicitly clear columns like error. (C2 fix)
    # Callers that don't pass a key don't touch the existing column value — only passed keys
    # are updated, including those explicitly set to None (= clear).
    update_kwargs = {k: v for k, v in kwargs.items() if k != "updated_at"}
    with _conn() as c:
        cols = ", ".join(insert_kwargs.keys())
        placeholders = ", ".join(["?"] * len(insert_kwargs))
        update_cols = list(update_kwargs.keys())
        if update_cols:
            # Use direct binding (not excluded.*) so None cols set to SQL NULL, not excluded.col. (C2 fix)
            updates = ", ".join(f"{k}=?" for k in update_cols) + ", updated_at=excluded.updated_at"
            c.execute(
                f"INSERT INTO pipeline_runs (issue_number, {cols}) "
                f"VALUES (?, {placeholders}) "
                f"ON CONFLICT(issue_number) DO UPDATE SET {updates}",
                [issue_number, *insert_kwargs.values(), *[update_kwargs[k] for k in update_cols]],
            )
        else:
            c.execute(
                f"INSERT INTO pipeline_runs (issue_number, {cols}) "
                f"VALUES (?, {placeholders}) "
                f"ON CONFLICT(issue_number) DO UPDATE SET updated_at=excluded.updated_at",
                [issue_number, *insert_kwargs.values()],
            )


def clear_run_for_retry(issue_number: int) -> None:
    """Explicitly NULL-out pr_number / branch / impl_commit_sha / error for a fresh retry.

    upsert_run() filters None kwargs so those columns can't be cleared via **kwargs.
    This function issues a direct UPDATE to reset them correctly. (M2 fix)
    """
    with _conn() as c:
        c.execute(
            "UPDATE pipeline_runs SET pr_number=NULL, branch=NULL, impl_commit_sha=NULL, "
            "error=NULL, updated_at=? WHERE issue_number=?",
            [datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), issue_number],
        )


def get_run(issue_number: int) -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM pipeline_runs WHERE issue_number=?", [issue_number]
        ).fetchone()
    return dict(row) if row else None


def log_event(issue_number: int, stage: str, status: str, detail: str = "") -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO stage_events (issue_number, stage, status, detail) VALUES (?,?,?,?)",
            [issue_number, stage, status, detail],
        )


def has_event(issue_number: int, stage: str, status: str) -> bool:
    """Return True if a matching stage_events row already exists — idempotency gate. (H6 fix)"""
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM stage_events WHERE issue_number=? AND stage=? AND status=?",
            [issue_number, stage, status],
        ).fetchone()
    return row is not None


def acquire_merge_lock(workflow_id: str, run_id: str, pr_number: int = 0) -> bool:
    """Try to acquire the singleton merge lock. Returns True if acquired.

    Stale locks (dead PID on same host, or age > TTL) are force-expired first.
    The lock row carries workflow_id + run_id so release() is safe on retry.

    Uses BEGIN IMMEDIATE so the SELECT + DELETE + INSERT runs as a single atomic
    transaction, eliminating the TOCTOU race where two callers both see a stale
    lock, both DELETE it, and both try to INSERT.

    Serialized via _merge_lock_mu so ROLLBACK is always on the same connection that
    held the prior BEGIN IMMEDIATE, regardless of which thread asyncio.to_thread picks. (H2 fix)
    """
    with _merge_lock_mu:
        return _acquire_merge_lock_impl(workflow_id, run_id, pr_number)


def _acquire_merge_lock_impl(workflow_id: str, run_id: str, pr_number: int) -> bool:
    pid = os.getpid()
    host = socket.gethostname()
    now = datetime.now(timezone.utc)
    conn = _get_lock_conn()

    # Roll back any dangling transaction from a prior failed call on this connection.
    # Without this, BEGIN IMMEDIATE raises OperationalError even when we own the connection,
    # masking genuine "locked by another writer" errors and causing false negatives. (C2 fix)
    try:
        conn.execute("ROLLBACK")
    except sqlite3.OperationalError:
        pass  # no active transaction to roll back — expected on first acquire call (H8 fix)

    try:
        conn.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError:
        return False  # another writer holds the db write lock

    try:
        row = conn.execute("SELECT * FROM pipeline_merge_lock WHERE id=1").fetchone()
        if row:
            row = dict(row)
            if row["workflow_id"] == workflow_id and row["run_id"] == run_id:
                # Own stale lock from a prior attempt — evict so retry re-acquires immediately.
                conn.execute("DELETE FROM pipeline_merge_lock WHERE id=1")
            else:
                if row["holder_host"] == host:
                    try:
                        os.kill(row["holder_pid"], 0)
                        alive = True
                    except ProcessLookupError:
                        alive = False
                    except PermissionError:
                        # Zombie / cross-user: conservatively treat as alive, but TTL
                        # still applies — the lock will be force-expired when age >= TTL
                        # so zombie processes cannot block indefinitely. (M5 fix)
                        alive = True
                else:
                    alive = True  # remote host: rely on TTL

                acquired_at = datetime.fromisoformat(row["acquired_at"].replace("Z", "+00:00"))
                age = (now - acquired_at).total_seconds()

                if alive and age < _MERGE_LOCK_TTL:
                    conn.rollback()
                    return False  # actively held

                # age >= TTL: force-expire regardless of alive status (includes PermissionError case)
                conn.execute("DELETE FROM pipeline_merge_lock WHERE id=1")

        conn.execute(
            "INSERT INTO pipeline_merge_lock "
            "(id, holder_pid, holder_host, workflow_id, run_id, pr_number, acquired_at) "
            "VALUES (1,?,?,?,?,?,?)",
            [pid, host, workflow_id, run_id, pr_number,
             now.strftime("%Y-%m-%dT%H:%M:%SZ")],
        )
        conn.commit()
        return True
    except Exception:
        _log.exception("_acquire_merge_lock_impl unexpected error — releasing lock and returning False")  # M2 fix
        try:
            conn.rollback()
        except Exception:
            pass
        return False


def verify_merge_lock(workflow_id: str, run_id: str) -> bool:
    """Return True if this workflow+run still owns the merge lock.

    Called immediately before squash-merge as a last safety check — the lock
    could have been evicted by TTL expiry or a concurrent worker restart. (H4 fix)
    """
    with _merge_lock_mu:
        conn = _get_lock_conn()
        row = conn.execute(
            "SELECT 1 FROM pipeline_merge_lock WHERE id=1 AND workflow_id=? AND run_id=?",
            [workflow_id, run_id],
        ).fetchone()
    return row is not None


def release_merge_lock(workflow_id: str, run_id: str) -> None:
    """Release the lock only if this workflow/run still owns it."""
    with _merge_lock_mu:
        conn = _get_lock_conn()
        conn.execute(
            "DELETE FROM pipeline_merge_lock WHERE id=1 AND workflow_id=? AND run_id=?",
            [workflow_id, run_id],
        )
        conn.commit()


def checkpoint_and_close() -> None:
    """WAL checkpoint + close this thread's connection. Call from each worker thread at shutdown."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        with _all_conns_lock:
            _all_conns.discard(conn)
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.commit()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        _local.conn = None


def checkpoint_all() -> None:
    """Checkpoint and close ALL tracked connections from any thread.

    Safe to call from the event loop thread after all worker threads have drained,
    because connections are created with check_same_thread=False. Eliminates the
    non-determinism of submitting N checkpoint tasks to a N-thread pool where a
    single hot thread may handle multiple tasks while others go uncheckpointed. (C1 fix)
    """
    with _all_conns_lock:
        conns = list(_all_conns)
        _all_conns.clear()
    for conn in conns:
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.commit()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
    # Also flush this calling thread's own connection (the event-loop thread).
    checkpoint_and_close()
