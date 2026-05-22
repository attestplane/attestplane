#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Run the local Codex auto-repair flow for one issue."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.local_codex_runner.codex_driver import CodexDriver
from scripts.local_codex_runner.config import RunnerConfig, add_common_args, load_config, overrides_from_args
from scripts.local_codex_runner.gate_runner import GateReport, GateRunner
from scripts.local_codex_runner.git_ops import GitOps
from scripts.local_codex_runner.github_cli import GitHubCLI
from scripts.local_codex_runner.models import IssueTask, RunnerResult, RunnerStatus, should_process_issue
from scripts.local_codex_runner.prompt_builder import PromptBuilder
from scripts.local_codex_runner.review_guard import run_review_guard
from scripts.local_codex_runner.state_store import load_state, save_state


def run_issue(
    config: RunnerConfig,
    issue_number: int | None,
    include_labels: set[str] | None = None,
    exclude_labels: set[str] | None = None,
) -> RunnerResult:
    workdir = config.workdir_path()
    gh = GitHubCLI(dry_run=config.dry_run)
    git = GitOps(workdir)
    builder = PromptBuilder(config.evidence_root())
    state = load_state(config.state_file())
    task = fetch_task(gh, config, issue_number)
    evidence_dir = builder.issue_dir(task.number)
    result = RunnerResult(
        issue_number=task.number,
        branch=None,
        pr_url=None,
        status=RunnerStatus.DRY_RUN if config.dry_run else RunnerStatus.SKIPPED,
        plan_path=None,
        evidence_dir=str(evidence_dir),
    )
    try:
        gh.current_auth_status()
        if not should_process_issue(
            task,
            approved_label=config.approved_label,
            pr_opened_label=config.pr_opened_label,
            needs_human_label=config.needs_human_label,
            include_labels=include_labels,
            exclude_labels=exclude_labels,
        ):
            result.status = RunnerStatus.SKIPPED
            result.local_test_summary = "Issue labels do not match runner queue policy."
            return write_result(result.finish(), evidence_dir, state, config)
        if (
            config.in_progress_label in task.labels
            and str(task.number) not in state.branch_mappings
            and not config.dry_run
        ):
            result.status = RunnerStatus.SKIPPED
            result.local_test_summary = "Issue is already in progress and not owned by local state."
            return write_result(result.finish(), evidence_dir, state, config)

        if not config.dry_run:
            gh.add_labels(config.repo or "", task.number, [config.in_progress_label])
            if not config.allow_dirty:
                git.ensure_clean_worktree()
            git.checkout_base_and_pull(config.checkout_ref())
            branch = git.create_branch(task.number, task.title)
        else:
            branch = f"codex/issue-{task.number}-{safe_branch_slug(task.title)}"
            (evidence_dir / "dry_run_actions.md").write_text(
                "\n".join(
                    [
                        "# Dry-Run Planned Actions",
                        "",
                        f"- Would add label `{config.in_progress_label}`.",
                        f"- Would ensure clean worktree and check out `{config.checkout_ref()}`.",
                        f"- Would create branch `{branch}`.",
                        "- Would run Codex plan/code/review prompts.",
                        "- Would run local gates after code changes.",
                        "- Would commit, push, create PR, and watch CI only when dry_run=false.",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
        result.branch = branch
        state.mark_active(task.number, branch)
        save_state(config.state_file(), state)

        codex = CodexDriver(
            command=config.codex_command,
            command_template=config.codex_command_template,
            sandbox=config.codex_sandbox,
            dry_run=config.dry_run,
        )
        plan_prompt = builder.build("01_plan.md", task, output_name="01_plan.prompt.md")
        result.plan_path = str(evidence_dir / "plan.md")
        codex.run_codex(plan_prompt, workdir, evidence_dir / "codex_plan.log")
        code_prompt = builder.build("02_code.md", task, output_name="02_code.prompt.md")
        codex.run_codex(code_prompt, workdir, evidence_dir / "codex_code.log")

        gate = dry_run_gate() if config.dry_run else run_local_gate(config, task, evidence_dir)
        result.local_test_summary = gate.summary()
        for round_index in range(config.max_local_fix_rounds):
            if config.dry_run or gate.status == "PASS":
                break
            fix_prompt = builder.build(
                "03_fix_tests.md",
                task,
                extra={"gate_log": gate.summary()},
                output_name=f"03_fix_tests_round_{round_index + 1}.prompt.md",
            )
            codex.run_codex(fix_prompt, workdir, evidence_dir / f"codex_fix_tests_round_{round_index + 1}.log")
            gate = run_local_gate(config, task, evidence_dir)
            result.local_test_summary = gate.summary()
        if gate.status != "PASS":
            result.status = RunnerStatus.LOCAL_FAILED
            if not config.allow_push_on_local_failure:
                return fail_issue(config, gh, task, result, evidence_dir, state)

        review_prompt = builder.build("04_review.md", task, output_name="04_review.prompt.md")
        codex.run_codex(review_prompt, workdir, evidence_dir / "codex_review.log")
        changed_files = [] if config.dry_run else git.changed_files()
        diff = "" if config.dry_run else git.diff()
        review_guard = run_review_guard(
            diff=diff,
            codex_review_report=(evidence_dir / "codex_review.log").read_text(encoding="utf-8"),
            issue_labels=task.labels,
            changed_files=changed_files,
            evidence_dir=evidence_dir,
        )
        if review_guard.status == "FAIL":
            result.status = RunnerStatus.REVIEW_BLOCKED
            result.residual_risks = review_guard.blocking_reasons
            return fail_issue(config, gh, task, result, evidence_dir, state)

        pr_body = builder.build_pr_body(
            task,
            validation=gate.summary(),
            evidence=str(evidence_dir),
            residual_risks="\n".join(review_guard.warnings) or "None",
        )
        (evidence_dir / "pr_body.md").write_text(pr_body, encoding="utf-8")
        if config.dry_run:
            result.status = RunnerStatus.DRY_RUN
            return write_result(result.finish(), evidence_dir, state, config)

        git.commit_all(task.number, f"Fix #{task.number}: {task.title}")
        git.push_branch(branch)
        if config.create_pr:
            pr_url = gh.create_pr(
                config.repo or "",
                f"Fix #{task.number}: {task.title}",
                pr_body,
                config.base_branch,
                branch,
            )
            result.pr_url = pr_url
            gh.add_labels(config.repo or "", task.number, [config.pr_opened_label])
            gh.remove_labels(config.repo or "", task.number, [config.in_progress_label])
            gh.comment_issue(config.repo or "", task.number, f"Local Codex runner opened PR: {pr_url}")
        if config.watch_ci and config.create_pr and result.pr_url:
            ci = wait_for_ci_round(config, gh, branch)
            for round_index in range(config.max_ci_fix_rounds):
                if ci.status == "PASS":
                    break
                failed_logs = gh.run_view_failed_logs(config.repo or "", branch)
                fix_prompt = builder.build(
                    "03_fix_tests.md",
                    task,
                    extra={"gate_log": failed_logs, "ci_summary": ci.summary},
                    output_name=f"03_fix_ci_round_{round_index + 1}.prompt.md",
                )
                codex.run_codex(fix_prompt, workdir, evidence_dir / f"codex_fix_ci_round_{round_index + 1}.log")
                gate = run_local_gate(config, task, evidence_dir)
                result.local_test_summary = gate.summary()
                if gate.status != "PASS":
                    result.status = RunnerStatus.LOCAL_FAILED
                    return fail_issue(config, gh, task, result, evidence_dir, state)
                git.commit_all(task.number, f"Fix #{task.number}: CI follow-up round {round_index + 1}")
                git.push_branch(branch)
                ci = wait_for_ci_round(config, gh, branch)
            result.ci_summary = ci.summary
            if ci.status == "PASS":
                gh.add_labels(config.repo or "", task.number, [config.ci_green_label])
            else:
                result.status = RunnerStatus.CI_FAILED
                return fail_issue(config, gh, task, result, evidence_dir, state)
        result.status = RunnerStatus.SUCCESS
        return write_result(result.finish(), evidence_dir, state, config)
    except Exception as exc:
        result.status = RunnerStatus.LOCAL_FAILED
        append_residual_risk(result, str(exc))
        (evidence_dir / "failure.txt").write_text(str(exc) + "\n", encoding="utf-8")
        return fail_issue(config, gh, task if "task" in locals() else None, result, evidence_dir, state)
    finally:
        commands = []
        for candidate in ("gh", "git"):
            obj = locals().get(candidate)
            if obj is not None:
                commands.extend(getattr(obj, "commands_run", []))
        result.commands_run = commands


def fetch_task(gh: GitHubCLI, config: RunnerConfig, issue_number: int | None) -> IssueTask:
    if issue_number is not None:
        return gh.view_issue(config.repo or "", issue_number)
    issues = gh.list_issues(config.repo or "", config.approved_label, config.max_issues_per_run)
    if not issues:
        raise RuntimeError("No open approved issues found")
    return issues[0]


def run_local_gate(config: RunnerConfig, task: IssueTask, evidence_dir: Path) -> GateReport:
    runner = GateRunner(
        config.workdir_path(),
        config.gate_matrix_file(),
        timeout_seconds=config.gate_timeout_seconds,
    )
    return runner.run(
        task.labels,
        evidence_dir,
    )


def dry_run_gate() -> GateReport:
    from scripts.local_codex_runner.gate_runner import GateCommandResult

    return GateReport(
        status="PASS",
        selected_gate="dry-run",
        commands=[GateCommandResult("dry-run: local gates are planned but not executed", 0, "", "")],
    )


def wait_for_ci_round(config: RunnerConfig, gh: GitHubCLI, branch: str):
    from scripts.local_codex_runner.ci_watch import wait_for_ci

    return wait_for_ci(
        gh,
        repo=config.repo or "",
        pr_number_or_branch=branch,
        timeout_seconds=config.ci_timeout_seconds,
        poll_seconds=config.ci_poll_seconds,
    )


def safe_branch_slug(title: str) -> str:
    from scripts.local_codex_runner.git_ops import slugify

    return slugify(title)


def append_residual_risk(result: RunnerResult, risk: str) -> None:
    """Append a residual risk while tolerating legacy scalar state values."""
    existing: Any = result.residual_risks
    if isinstance(existing, list):
        existing.append(risk)
        return
    if existing is None:
        result.residual_risks = [risk]
        return
    result.residual_risks = [str(existing), risk]


def fail_issue(
    config: RunnerConfig,
    gh: GitHubCLI,
    task: IssueTask | None,
    result: RunnerResult,
    evidence_dir: Path,
    state,
) -> RunnerResult:
    if task is not None and not config.dry_run:
        gh.add_labels(config.repo or "", task.number, [config.needs_human_label])
        gh.remove_labels(config.repo or "", task.number, [config.in_progress_label])
        gh.comment_issue(
            config.repo or "",
            task.number,
            f"Local Codex runner stopped: {result.status.value}\nEvidence: {evidence_dir}",
        )
    return write_result(result.finish(), evidence_dir, state, config)


def write_result(result: RunnerResult, evidence_dir: Path, state, config: RunnerConfig) -> RunnerResult:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "runner_result.json").write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (evidence_dir / "runner_result.md").write_text(render_result(result), encoding="utf-8")
    state.mark_finished(result.issue_number, result)
    save_state(config.state_file(), state)
    return result


def render_result(result: RunnerResult) -> str:
    return (
        f"# Local Codex Runner Result\n\n"
        f"- Issue: #{result.issue_number}\n"
        f"- Status: {result.status.value}\n"
        f"- Branch: {result.branch or 'n/a'}\n"
        f"- PR: {result.pr_url or 'n/a'}\n"
        f"- Evidence: {result.evidence_dir}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    args = parser.parse_args()
    config = load_config(args.config, overrides_from_args(args))
    result = run_issue(config, args.issue_number, set(args.include_label or []), set(args.exclude_label or []))
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.status in {RunnerStatus.SUCCESS, RunnerStatus.DRY_RUN, RunnerStatus.SKIPPED} else 1


if __name__ == "__main__":
    raise SystemExit(main())
