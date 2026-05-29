# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
"""AutodevPipeline Temporal workflow: implement → create PR → review → merge."""

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .activities import (
        implement_activity,
        create_pr_activity,
        review_pr_activity,
        post_review_activity,
        merge_pr_activity,
    )

# implement + create_pr run on the main queue (Codex slots).
# review + post_review + merge run on a separate queue so review never
# blocks an implement slot (P0 decoupling).
_TASK_QUEUE = "autodev"
_REVIEW_QUEUE = "review"

_retry_3 = RetryPolicy(
    maximum_attempts=3,
    backoff_coefficient=2.0,
    initial_interval=timedelta(seconds=10),
    maximum_interval=timedelta(minutes=5),
)
_retry_5 = RetryPolicy(
    maximum_attempts=5,
    backoff_coefficient=2.0,
    initial_interval=timedelta(seconds=5),
    maximum_interval=timedelta(minutes=2),
)


@dataclass
class PipelineInput:
    issue_number: int
    issue_title: str
    issue_body: str


@workflow.defn(name="AutodevPipeline")
class AutodevPipeline:
    @workflow.run
    async def run(self, inp: PipelineInput) -> str:
        n = inp.issue_number

        impl = await workflow.execute_activity(
            implement_activity,
            args=[n, inp.issue_title, inp.issue_body],
            task_queue=_TASK_QUEUE,
            start_to_close_timeout=timedelta(minutes=50),
            retry_policy=_retry_3,
        )
        if not impl.get("has_changes"):
            return f"issue #{n}: no changes produced by Codex"

        pr = await workflow.execute_activity(
            create_pr_activity,
            args=[n, impl["branch"]],
            task_queue=_TASK_QUEUE,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=_retry_5,
        )

        review = await workflow.execute_activity(
            review_pr_activity,
            args=[n, pr["pr_number"]],
            task_queue=_REVIEW_QUEUE,
            start_to_close_timeout=timedelta(minutes=20),
            retry_policy=_retry_3,
        )

        await workflow.execute_activity(
            post_review_activity,
            args=[n, pr["pr_number"], review["decision"], review.get("output", "")],
            task_queue=_REVIEW_QUEUE,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=_retry_5,
        )

        if review["decision"] != "APPROVE":
            return f"issue #{n}: PR #{pr['pr_number']} REQUEST_CHANGES – not merging"

        await workflow.execute_activity(
            merge_pr_activity,
            args=[n, pr["pr_number"]],
            task_queue=_REVIEW_QUEUE,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=_retry_5,
        )

        return f"issue #{n}: merged PR #{pr['pr_number']} ✓"
