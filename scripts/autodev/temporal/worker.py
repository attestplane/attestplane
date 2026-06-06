# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
"""Temporal worker entrypoint for autodev-train pipeline.

Run:
    python3.11 -m scripts.autodev.temporal.worker

Environment:
    TEMPORAL_ADDRESS      Temporal gRPC address (default: localhost:7233)
    DEEPSEEK_API_KEY      DeepSeek API key for Qwen Code review
    GH_TOKEN / GITHUB_TOKEN  GitHub PAT for gh CLI calls
    CODEX_HOME            Codex config dir (default: ~/codex-home)
    AUTODEV_MAIN_REPO     Path to main attestplane checkout
    AUTODEV_DB_PATH       SQLite DB path (default: data/autodev_state.db)
    AUTODEV_CONCURRENCY   Max concurrent implement activities (default: 10)
"""

import asyncio
import concurrent.futures
import logging
import os
import signal
import sqlite3

from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.worker import Worker

from .activities import (
    create_pr_activity,
    fix_ci_activity,
    implement_activity,
    merge_pr_activity,
    post_review_activity,
    review_pr_activity,
)
from .workflow import AutodevPipeline
from . import db as _db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
log = logging.getLogger("autodev.worker")

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TASK_QUEUE = "autodev"
REVIEW_QUEUE = "review"
MAX_IMPLEMENT = int(os.environ.get("AUTODEV_CONCURRENCY", "10"))
MAX_REVIEW = min(MAX_IMPLEMENT * 2, 40)  # cap to avoid exhausting Temporal poller + SQLite limits (L3 fix)
DB_PATH = os.environ.get(
    "AUTODEV_DB_PATH",
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "data", "autodev_state.db"
        )
    ),
)


async def _cleanup_orphaned_runs(client: Client, db_path: str) -> int:
    if not os.path.exists(db_path):
        log.info("Cleaned 0 orphaned pipeline runs at startup")
        return 0

    # COMPLETED workflows finished normally; their DB stage was set by the final activity.
    # Overwriting them with 'failed' would erase merge-success records. (M1 fix)
    _TERMINAL = {
        WorkflowExecutionStatus.FAILED,
        WorkflowExecutionStatus.TERMINATED,
        WorkflowExecutionStatus.TIMED_OUT,
        WorkflowExecutionStatus.CANCELED,
    }

    # Phase 1: read candidate rows without holding any write lock or connection.
    # Separating DB reads from async network calls avoids holding a SQLite write
    # transaction open across awaits (which blocks other writers for minutes). (M2 fix)
    # asyncio.to_thread prevents SQLite I/O from blocking the event loop. (L3 fix)
    def _phase1_read() -> list[tuple]:
        with sqlite3.connect(db_path) as conn:
            return conn.execute(
                """
                SELECT issue_number FROM pipeline_runs
                WHERE stage NOT IN ('merged', 'failed', 'merge_conflict', 'no_changes')
                """
            ).fetchall()

    rows = await asyncio.to_thread(_phase1_read)

    # Phase 2: inspect each workflow via Temporal gRPC (awaits, no DB connection held).
    orphaned: list[int] = []
    for (issue_number,) in rows:
        try:
            handle = client.get_workflow_handle(f"autodev-issue-{issue_number}")
            description = await handle.describe()
        except Exception as exc:
            # Cannot determine status — skip conservatively (do NOT mark as orphan).
            log.warning(
                "Could not describe workflow for issue #%d: %s — skipping cleanup",
                issue_number, exc,
            )
            continue

        if description.status in _TERMINAL:
            orphaned.append(issue_number)

    # Phase 3: write all updates in a single batch transaction (no awaits). (L3 fix)
    if orphaned:
        def _phase3_write(_orphaned: list[int]) -> None:
            with sqlite3.connect(db_path) as conn:
                for _issue in _orphaned:
                    conn.execute(
                        """
                        UPDATE pipeline_runs
                        SET stage='failed',
                            error='orphaned: workflow terminal at startup',
                            updated_at=strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
                        WHERE issue_number=?
                        """,
                        [_issue],
                    )
                # Commit the batch before checkpointing: wal_checkpoint(TRUNCATE)
                # cannot run inside an open write transaction (SQLITE_LOCKED). (M3 fix)
                conn.commit()
                # Flush WAL so thread-local worker connections see orphan updates immediately.
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        await asyncio.to_thread(_phase3_write, orphaned)

    log.info("Cleaned %d orphaned pipeline runs at startup", len(orphaned))
    return len(orphaned)


async def _main() -> None:
    log.info("Connecting to Temporal at %s ...", TEMPORAL_ADDRESS)
    client = await Client.connect(TEMPORAL_ADDRESS)
    try:
        await _cleanup_orphaned_runs(client, DB_PATH)
    except Exception as _cleanup_exc:
        # Startup cleanup failure must never prevent the worker from running. (MEDIUM-11 fix)
        log.warning("Orphaned-run cleanup failed (non-fatal): %s", _cleanup_exc)

    # All activities are async def — they run on the asyncio event loop, not an executor pool.
    # activity_executor is only used by Temporal for synchronous activities; omitting it lets
    # Temporal use its built-in default. max_concurrent_activities is the real rate limiter. (H1 fix)

    # Size the default executor used by asyncio.to_thread() across all activities.
    # Without this, CPython's default = min(32, cpu_count+4) which can undersize under
    # high concurrent-activity counts. (M4 fix)
    _thread_pool = concurrent.futures.ThreadPoolExecutor(
        max_workers=MAX_IMPLEMENT + MAX_REVIEW + 8,
        thread_name_prefix="autodev-io",
    )
    asyncio.get_running_loop().set_default_executor(_thread_pool)

    # Main queue: implement + create_pr (Codex slots, P1 = 10 concurrent).
    # Also registers review activities here for backwards-compat with any
    # tasks that were dispatched to "autodev" before P0 queue split.
    implement_worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[AutodevPipeline],
        activities=[
            implement_activity,
            create_pr_activity,
            fix_ci_activity,
            review_pr_activity,
            post_review_activity,
            merge_pr_activity,
        ],
        max_concurrent_activities=MAX_IMPLEMENT,
        max_concurrent_workflow_tasks=MAX_IMPLEMENT * 2,
    )

    # Review queue: new workflows dispatch here (P0 decoupling).
    # fix_ci moved here from implement queue so it never occupies Codex slots. (M4 fix)
    review_worker = Worker(
        client,
        task_queue=REVIEW_QUEUE,
        activities=[
            create_pr_activity, fix_ci_activity,
            review_pr_activity, post_review_activity, merge_pr_activity,
        ],
        max_concurrent_activities=MAX_REVIEW,
        max_concurrent_workflow_tasks=MAX_REVIEW,
    )

    log.info(
        "autodev-train workers ready -- implement=%s (%d slots)  review=%s (%d slots)",
        TASK_QUEUE,
        MAX_IMPLEMENT,
        REVIEW_QUEUE,
        MAX_REVIEW,
    )

    loop = asyncio.get_running_loop()  # M7: get_event_loop() is deprecated in Python 3.10+
    stop_event = asyncio.Event()

    def _shutdown(sig: int) -> None:
        log.info("Received signal %d, shutting down ...", sig)
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):  # L9: SIGHUP for ops reload
        loop.add_signal_handler(sig, _shutdown, sig)

    async with implement_worker, review_worker:
        await stop_event.wait()

    # Temporal's async-with block drains all in-flight activities before returning,
    # so by the time we reach here all asyncio.to_thread SQLite calls have finished.
    # checkpoint_all() is safe to call without a separate pool drain. (H1 / C3 fix)
    _db.checkpoint_all()  # checkpoints every thread-local connection + event-loop thread's
    log.info("Worker stopped.")


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
