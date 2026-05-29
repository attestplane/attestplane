# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
"""Temporal worker entrypoint for autodev-train pipeline.

Run:
    python3.11 -m scripts.autodev.temporal.worker

Environment:
    TEMPORAL_ADDRESS   Temporal gRPC address (default: localhost:7233)
    DEEPSEEK_API_KEY   DeepSeek API key for Qwen Code review
    GH_TOKEN / GITHUB_TOKEN  GitHub PAT for gh CLI calls
    CODEX_HOME         Codex config dir (default: ~/codex-home)
    AUTODEV_MAIN_REPO  Path to main attestplane checkout (default: ~/projects/attestplane)
    AUTODEV_DB_PATH    SQLite DB path (default: data/autodev_state.db)
"""

import asyncio
import logging
import os
import signal
import sys

from temporalio.client import Client
from temporalio.worker import Worker

from .activities import (
    create_pr_activity,
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
MAX_CONCURRENT_ACTIVITIES = int(os.environ.get("AUTODEV_CONCURRENCY", "5"))


async def _main() -> None:
    log.info("Connecting to Temporal at %s …", TEMPORAL_ADDRESS)
    client = await Client.connect(TEMPORAL_ADDRESS)

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[AutodevPipeline],
        activities=[
            implement_activity,
            create_pr_activity,
            review_pr_activity,
            post_review_activity,
            merge_pr_activity,
        ],
        # Each activity slot = 1 parallel codex exec / qwen call
        max_concurrent_activities=MAX_CONCURRENT_ACTIVITIES,
        max_concurrent_workflow_tasks=MAX_CONCURRENT_ACTIVITIES * 2,
    )

    log.info(
        "autodev-train worker ready (task_queue=%s, max_concurrent_activities=%d)",
        TASK_QUEUE,
        MAX_CONCURRENT_ACTIVITIES,
    )

    # Graceful shutdown on SIGTERM / SIGINT
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def _shutdown(sig: int) -> None:
        log.info("Received signal %d, shutting down …", sig)
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown, sig)

    async with worker:
        await stop_event.wait()

    log.info("Worker stopped.")


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
