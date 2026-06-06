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
        fix_ci_activity,
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
            task_queue=_REVIEW_QUEUE,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=_retry_5,
        )

        # Wait for CI; if it fails, run Codex once to auto-fix errors.
        # merge_pr_activity does its own final CI check before merging.
        # fix_ci runs on _REVIEW_QUEUE to avoid occupying implement slots for up to 30 min.
        # (M4 fix — restore P0 queue decoupling)
        fix_result = await workflow.execute_activity(
            fix_ci_activity,
            args=[n, pr["pr_number"]],
            task_queue=_REVIEW_QUEUE,
            start_to_close_timeout=timedelta(minutes=60),
            heartbeat_timeout=timedelta(minutes=3),
            retry_policy=_retry_3,
        )
        # C5 fix: consume the return value so CI failure is visible in workflow history.
        # We do NOT abort here — merge_pr_activity performs an independent CI gate before
        # squash-merging, so a failed fix_ci only means the fast-path is skipped.
        if not fix_result.get("ci_passed") and not fix_result.get("fixed"):
            workflow.logger.warning(
                "issue #%d PR #%d: CI not passing and auto-fix produced no changes — "
                "review will proceed but merge_pr will re-check CI before merging",
                n, pr["pr_number"],
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

        merge_result = await workflow.execute_activity(
            merge_pr_activity,
            args=[n, pr["pr_number"]],
            task_queue=_REVIEW_QUEUE,
            start_to_close_timeout=timedelta(minutes=45),  # H5: lock(600s)+rebase+CI(300s)+merge
            retry_policy=_retry_5,
        )

        if not merge_result.get("merged"):
            return f"issue #{n}: PR #{pr['pr_number']} not merged — {merge_result.get('reason', 'unknown')}"
        return f"issue #{n}: merged PR #{pr['pr_number']} ✓"
