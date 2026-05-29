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

from temporalio.client import Client
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
log = logging.getLogger("autodev.worker")

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TASK_QUEUE = "autodev"
REVIEW_QUEUE = "review"
MAX_IMPLEMENT = int(os.environ.get("AUTODEV_CONCURRENCY", "10"))
MAX_REVIEW = MAX_IMPLEMENT * 2


async def _main() -> None:
    log.info("Connecting to Temporal at %s ...", TEMPORAL_ADDRESS)
    client = await Client.connect(TEMPORAL_ADDRESS)

    implement_pool = concurrent.futures.ThreadPoolExecutor(
        max_workers=MAX_IMPLEMENT,
        thread_name_prefix="autodev-impl",
    )
    review_pool = concurrent.futures.ThreadPoolExecutor(
        max_workers=MAX_REVIEW,
        thread_name_prefix="autodev-review",
    )

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
        activity_executor=implement_pool,
        max_concurrent_activities=MAX_IMPLEMENT,
        max_concurrent_workflow_tasks=MAX_IMPLEMENT * 2,
    )

    # Review queue: new workflows dispatch here (P0 decoupling).
    # review slots never block implement slots.
    review_worker = Worker(
        client,
        task_queue=REVIEW_QUEUE,
        activities=[review_pr_activity, post_review_activity, merge_pr_activity],
        activity_executor=review_pool,
        max_concurrent_activities=MAX_REVIEW,
        max_concurrent_workflow_tasks=MAX_REVIEW,
    )

    log.info(
        "autodev-train workers ready -- implement=%s (%d slots)  review=%s (%d slots)",
        TASK_QUEUE, MAX_IMPLEMENT,
        REVIEW_QUEUE, MAX_REVIEW,
    )

    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def _shutdown(sig: int) -> None:
        log.info("Received signal %d, shutting down ...", sig)
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown, sig)

    async with implement_worker, review_worker:
        await stop_event.wait()

    implement_pool.shutdown(wait=False)
    review_pool.shutdown(wait=False)
    log.info("Worker stopped.")


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
