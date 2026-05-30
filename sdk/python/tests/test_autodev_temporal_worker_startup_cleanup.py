# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors

from __future__ import annotations

import asyncio
import importlib.util
import sqlite3
import sys
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


def test_cleanup_orphaned_runs_marks_non_running_workflows_failed(tmp_path: Path) -> None:
    db_path = tmp_path / "autodev_state.db"
    with sqlite3.connect(db_path) as connection:
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
                (1, "implementing"),
                (2, "reviewing"),
                (3, "approved"),
                (4, "merged"),
                (5, "failed"),
            ],
        )

    client = _FakeClient(
        {
            "autodev-issue-1": _FakeHandle(WorkflowExecutionStatus.RUNNING),
            "autodev-issue-2": _FakeHandle(WorkflowExecutionStatus.COMPLETED),
            "autodev-issue-3": _FakeHandle(None, raises=True),
        }
    )

    cleaned = asyncio.run(worker._cleanup_orphaned_runs(client, db_path))

    assert cleaned == 2
    assert client.requested == [
        "autodev-issue-1",
        "autodev-issue-2",
        "autodev-issue-3",
    ]

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT issue_number, stage, error FROM pipeline_runs ORDER BY issue_number"
        ).fetchall()

    assert rows == [
        (1, "implementing", None),
        (2, "failed", "orphaned: workflow not running at startup"),
        (3, "failed", "orphaned: workflow not running at startup"),
        (4, "merged", None),
        (5, "failed", None),
    ]
