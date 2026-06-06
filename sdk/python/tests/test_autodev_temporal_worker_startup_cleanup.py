# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors

from __future__ import annotations

import asyncio
import importlib.util
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

from temporalio.client import WorkflowExecutionStatus

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKER_PATH = REPO_ROOT / "scripts/autodev/temporal/worker.py"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

spec = importlib.util.spec_from_file_location(
    "scripts.autodev.temporal.worker",
    WORKER_PATH,
    submodule_search_locations=[str(WORKER_PATH.parent)],
)
assert spec is not None and spec.loader is not None
worker = importlib.util.module_from_spec(spec)
sys.modules["scripts.autodev.temporal.worker"] = worker
spec.loader.exec_module(worker)


class _FakeHandle:
    def __init__(self, status: WorkflowExecutionStatus | None, raises: bool = False):
        self._status = status
        self._raises = raises

    async def describe(self) -> SimpleNamespace:
        if self._raises:
            raise RuntimeError("describe failed")
        return SimpleNamespace(status=self._status)


class _FakeClient:
    def __init__(self, handles: dict[str, _FakeHandle]):
        self.handles = handles
        self.requested: list[str] = []

    def get_workflow_handle(self, workflow_id: str) -> _FakeHandle:
        self.requested.append(workflow_id)
        return self.handles[workflow_id]


def test_cleanup_orphaned_runs_marks_terminal_workflows_failed(tmp_path: Path) -> None:
    # Startup cleanup only fails runs whose Temporal workflow is in a TERMINAL
    # state (FAILED/TERMINATED/TIMED_OUT/CANCELED). It conservatively leaves:
    #   - RUNNING workflows (still live),
    #   - COMPLETED workflows (finished normally; overwriting would erase
    #     merge-success records — M1),
    #   - workflows whose describe() raises (status unknown — skip, don't guess).
    # Rows already in a terminal DB stage (merged/failed/...) are not candidates.
    db_path = tmp_path / "autodev_state.db"
    with closing(sqlite3.connect(db_path)) as connection, connection:
        connection.execute(
            """
            CREATE TABLE pipeline_runs (
                issue_number INTEGER PRIMARY KEY,
                stage TEXT NOT NULL,
                error TEXT,
                updated_at TEXT
            )
            """
        )
        connection.executemany(
            "INSERT INTO pipeline_runs (issue_number, stage) VALUES (?, ?)",
            [
                (1, "implementing"),  # RUNNING -> leave
                (2, "reviewing"),     # COMPLETED -> leave (preserve success)
                (3, "approved"),      # describe raises -> skip
                (4, "merged"),        # not a candidate (terminal DB stage)
                (5, "failed"),        # not a candidate
                (6, "implementing"),  # TERMINATED -> mark failed
            ],
        )

    client = _FakeClient(
        {
            "autodev-issue-1": _FakeHandle(WorkflowExecutionStatus.RUNNING),
            "autodev-issue-2": _FakeHandle(WorkflowExecutionStatus.COMPLETED),
            "autodev-issue-3": _FakeHandle(None, raises=True),
            "autodev-issue-6": _FakeHandle(WorkflowExecutionStatus.TERMINATED),
        }
    )

    cleaned = asyncio.run(worker._cleanup_orphaned_runs(client, db_path))

    # Only issue 6 (TERMINATED) is orphaned.
    assert cleaned == 1
    # Only non-terminal-DB-stage rows are inspected; 4 (merged) and 5 (failed) skipped.
    assert client.requested == [
        "autodev-issue-1",
        "autodev-issue-2",
        "autodev-issue-3",
        "autodev-issue-6",
    ]

    with closing(sqlite3.connect(db_path)) as connection, connection:
        rows = connection.execute(
            "SELECT issue_number, stage, error FROM pipeline_runs ORDER BY issue_number"
        ).fetchall()

    assert rows == [
        (1, "implementing", None),
        (2, "reviewing", None),
        (3, "approved", None),
        (4, "merged", None),
        (5, "failed", None),
        (6, "failed", "orphaned: workflow terminal at startup"),
    ]
