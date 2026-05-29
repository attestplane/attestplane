# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
"""SQLite audit log and pipeline-state store for autodev-train."""

import sqlite3
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

DB_PATH = Path(os.environ.get(
    "AUTODEV_DB_PATH",
    Path(__file__).resolve().parents[4] / "data" / "autodev_state.db"
))

_DDL = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    issue_number  INTEGER PRIMARY KEY,
    workflow_id   TEXT,
    stage         TEXT    NOT NULL DEFAULT 'pending',
    pr_number     INTEGER,
    branch        TEXT,
    review_decision TEXT,
    error         TEXT,
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
"""


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript(_DDL)
    return c


def upsert_run(issue_number: int, **kwargs) -> None:
    kwargs["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with _conn() as c:
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join(["?"] * len(kwargs))
        updates = ", ".join(f"{k}=excluded.{k}" for k in kwargs.keys())
        c.execute(
            f"INSERT INTO pipeline_runs (issue_number, {cols}) "
            f"VALUES (?, {placeholders}) "
            f"ON CONFLICT(issue_number) DO UPDATE SET {updates}, "
            f"updated_at=excluded.updated_at",
            [issue_number, *kwargs.values()],
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
