#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Recover selected ``codex-needs-human`` states without weakening redlines."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from scripts.local_codex_runner.ci_watch import classify_checks, wait_for_ci
from scripts.local_codex_runner.codex_driver import CodexDriver
from scripts.local_codex_runner.config import RunnerConfig
from scripts.local_codex_runner.gate_runner import GateRunner
from scripts.local_codex_runner.git_ops import GitOps, GitSafetyError
from scripts.local_codex_runner.github_cli import GitHubCLI, RunnerCommandError
from scripts.local_codex_runner.models import IssueTask
from scripts.local_codex_runner.prompt_builder import PromptBuilder
from scripts.local_codex_runner.state_store import load_state, save_state


UNKNOWN_REASON = "unknown"
POLICY_REASON = "policy_boundary"


@dataclass(frozen=True)
class StopSignal:
    reason: str
    signature: str
    detail: str | None = None


@dataclass(frozen=True)
class NeedsHumanRecovery:
    issue_number: int
    action: str
    reason: str
    attempt: int
    pr_number: int | None = None
    branch: str | None = None
    signature: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def recover_needs_human(config: RunnerConfig, gh: GitHubCLI) -> dict[str, object]:
    """Classify and recover bounded needs-human issues for one poll cycle."""
    return recover_needs_human_for_labels(config, gh, include_labels=None, exclude_labels=None)


def recover_needs_human_for_labels(
    config: RunnerConfig,
    gh: GitHubCLI,
    *,
    include_labels: set[str] | None = None,
    exclude_labels: set[str] | None = None,
) -> dict[str, object]:
    """Classify and recover needs-human issues inside the current lane scope."""
    if not config.auto_recover_needs_human:
        return {"enabled": False, "results": []}

    state = load_state(config.state_file())
    issues = gh.list_issues(
        config.repo or "",
        config.needs_human_label,
        max(1, config.max_needs_human_recoveries_per_run * 10),
    )
    prs = gh.list_pull_requests(config.repo or "", config.base_branch, 100)
    results: list[NeedsHumanRecovery] = []
    recoverable_reasons = set(config.needs_human_recoverable_reasons)
    policy_block_labels = set(config.needs_human_policy_block_labels)
    recoveries = 0

    for issue in issues:
        if recoveries >= config.max_needs_human_recoveries_per_run:
            break
        if not issue_in_lane(issue, include_labels, exclude_labels):
            continue
        labels = set(issue.labels)
        if labels.intersection(policy_block_labels):
            results.append(
                NeedsHumanRecovery(
                    issue.number,
                    "kept",
                    POLICY_REASON,
                    0,
                    detail=f"blocking label present: {sorted(labels.intersection(policy_block_labels))}",
                )
            )
            continue
        if config.approved_label not in labels:
            results.append(
                NeedsHumanRecovery(issue.number, "kept", POLICY_REASON, 0, detail="missing approved label")
            )
            continue

        pr = find_issue_pr(issue.number, prs)
        signal = classify_issue_needs_human(config, issue, pr, gh)
        key = f"needs-human:{issue.number}:{signal.reason}:{signal.signature}"
        attempt = state.retry_counts.get(key, 0)
        if signal.reason not in recoverable_reasons:
            results.append(
                NeedsHumanRecovery(
                    issue.number,
                    "kept",
                    signal.reason,
                    attempt,
                    pr_number=pr_number(pr),
                    branch=pr_branch(pr),
                    signature=signal.signature,
                    detail=signal.detail,
                )
            )
            continue
        if attempt >= config.max_needs_human_attempts:
            results.append(
                NeedsHumanRecovery(
                    issue.number,
                    "kept",
                    signal.reason,
                    attempt,
                    pr_number=pr_number(pr),
                    branch=pr_branch(pr),
                    signature=signal.signature,
                    detail="attempt cap reached",
                )
            )
            continue

        attempt += 1
        if not config.dry_run:
            state.retry_counts[key] = attempt
            save_state(config.state_file(), state)
        if pr is None:
            results.append(requeue_issue(config, gh, issue, signal, attempt))
            recoveries += 1
            continue
        results.append(recover_ci_pr(config, gh, issue, pr, signal, attempt))
        recoveries += 1
    return {"enabled": True, "results": [item.to_dict() for item in results]}


def issue_in_lane(
    issue: IssueTask,
    include_labels: set[str] | None,
    exclude_labels: set[str] | None,
) -> bool:
    labels = set(issue.labels)
    if include_labels and not labels.intersection(include_labels):
        return False
    return not (exclude_labels and labels.intersection(exclude_labels))


def find_issue_pr(issue_number: int, prs: list[dict[str, object]]) -> dict[str, object] | None:
    needle = f"#{issue_number}"
    for pr in prs:
        title = str(pr.get("title", ""))
        head = str(pr.get("headRefName", ""))
        if needle in title or head.startswith(f"codex/issue-{issue_number}-"):
            return pr
    return None


def pr_number(pr: dict[str, object] | None) -> int | None:
    if pr is None or pr.get("number") is None:
        return None
    return int(pr["number"])


def pr_branch(pr: dict[str, object] | None) -> str | None:
    if pr is None:
        return None
    return str(pr.get("headRefName") or "") or None


def classify_issue_needs_human(
    config: RunnerConfig,
    issue: IssueTask,
    pr: dict[str, object] | None,
    gh: GitHubCLI,
) -> StopSignal:
    if pr is not None:
        owner_detail = validate_recovery_pr(config, issue.number, pr)
        if owner_detail is not None:
            return StopSignal(POLICY_REASON, stable_signature(owner_detail), owner_detail)
        branch = pr_branch(pr)
        worktree_detail = branch_checked_out_elsewhere(config, branch)
        if worktree_detail is not None:
            return StopSignal("local_workspace_blocked", stable_signature(worktree_detail), worktree_detail)
        checks = gh.pr_checks(config.repo or "", str(pr_number(pr) or pr_branch(pr) or ""))
        failed = [check for check in checks if check.bucket in {"fail", "cancel"}]
        status = classify_checks(checks)
        if status == "FAIL":
            names = ",".join(sorted(check.name for check in failed if check.name)) or "failed-check"
            return StopSignal("ci_failed", stable_signature(names), names)
        if status == "PENDING":
            return StopSignal("ci_pending", stable_signature("ci_pending"), "checks still pending")
        return StopSignal("ci_passed", stable_signature("ci_passed"), "checks already pass")

    if config.pr_opened_label in issue.labels:
        return StopSignal("missing_pr", stable_signature("missing_pr"), "issue has PR label but no matching PR")
    return classify_local_evidence(config, issue.number)


def validate_recovery_pr(config: RunnerConfig, issue_number: int, pr: dict[str, object]) -> str | None:
    branch = pr_branch(pr)
    if not branch or not branch.startswith(f"codex/issue-{issue_number}-"):
        return f"branch {branch or 'n/a'} is not runner-owned for issue {issue_number}"
    if pr.get("baseRefName") and str(pr["baseRefName"]) != config.base_branch:
        return f"base branch is {pr['baseRefName']}, expected {config.base_branch}"
    labels = pr_label_names(pr)
    blockers = sorted(set(labels).intersection(config.needs_human_policy_block_labels))
    if blockers:
        return f"blocking PR label present: {blockers}"
    author = pr_author_login(pr)
    if config.allowed_pr_authors and author not in set(config.allowed_pr_authors):
        return f"PR author {author or 'n/a'} is not allowlisted"
    if not config.allowed_pr_authors and not config.dry_run:
        return "allowed_pr_authors is required before live needs-human PR recovery"
    return None


def pr_author_login(pr: dict[str, object]) -> str | None:
    author = pr.get("author")
    if isinstance(author, dict):
        login = author.get("login")
        return str(login) if login else None
    return None


def pr_label_names(pr: dict[str, object]) -> list[str]:
    labels = pr.get("labels")
    if not isinstance(labels, list):
        return []
    return [str(label.get("name", label)) for label in labels if label]


def branch_checked_out_elsewhere(config: RunnerConfig, branch: str | None) -> str | None:
    if config.dry_run:
        return None
    if not branch:
        return None
    git = GitOps(config.workdir_path())
    try:
        output = git.run(["worktree", "list", "--porcelain"])
    except RunnerCommandError as exc:
        return f"could not inspect worktrees: {exc}"
    current_path = str(config.workdir_path())
    path: str | None = None
    branch_ref: str | None = None
    for raw_line in [*output.splitlines(), ""]:
        line = raw_line.strip()
        if not line:
            if path and branch_ref == f"refs/heads/{branch}" and path != current_path:
                return f"branch {branch} is already checked out at {path}"
            path = None
            branch_ref = None
            continue
        if line.startswith("worktree "):
            path = line.removeprefix("worktree ")
        elif line.startswith("branch "):
            branch_ref = line.removeprefix("branch ")
    return None


def classify_local_evidence(config: RunnerConfig, issue_number: int) -> StopSignal:
    evidence_dir = config.evidence_root() / f"issue-{issue_number}"
    text = read_evidence_text(evidence_dir)
    lowered = text.lower()
    if not lowered.strip():
        return StopSignal(UNKNOWN_REASON, stable_signature("no-evidence"), "no local failure evidence")
    if any(token in lowered for token in ("rate limit", "usage limit", "quota", "429", "try again later")):
        return StopSignal(
            "rate_limit",
            stable_signature(first_matching_line(text, ("limit", "quota", "429"))),
            "model/API quota evidence",
        )
    if any(
        token in lowered
        for token in (
            "timed out",
            "timeout",
            "connection reset",
            "could not resolve",
            "failed to connect",
            "port 443",
            "network",
        )
    ):
        return StopSignal(
            "network_timeout",
            stable_signature(first_matching_line(text, ("timeout", "connect", "network", "443"))),
            "network timeout evidence",
        )
    if "policy" in lowered or "forbidden" in lowered or "refusing to push" in lowered:
        return StopSignal(
            POLICY_REASON,
            stable_signature(first_matching_line(text, ("policy", "forbidden", "refusing"))),
            "policy or redline evidence",
        )
    return StopSignal(UNKNOWN_REASON, stable_signature(first_error_line(text)), "failure evidence is not recoverable")


def read_evidence_text(evidence_dir: Path) -> str:
    chunks: list[str] = []
    for filename in ("failure.txt", "runner_result.json", "runner_result.md"):
        path = evidence_dir / filename
        if path.exists():
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def first_matching_line(text: str, needles: tuple[str, ...]) -> str:
    lowered_needles = tuple(needle.lower() for needle in needles)
    for line in text.splitlines():
        lowered = line.lower()
        if any(needle in lowered for needle in lowered_needles):
            return normalize_line(line)
    return first_error_line(text)


def first_error_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return normalize_line(line)
    return "empty"


def normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())[:240]


def stable_signature(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def requeue_issue(
    config: RunnerConfig,
    gh: GitHubCLI,
    issue: IssueTask,
    signal: StopSignal,
    attempt: int,
) -> NeedsHumanRecovery:
    if config.dry_run:
        action = "would_requeue"
    else:
        action = "requeued"
        gh.remove_labels(config.repo or "", issue.number, [config.needs_human_label])
        gh.add_labels(config.repo or "", issue.number, [config.needs_human_recovered_label])
        gh.comment_issue(
            config.repo or "",
            issue.number,
            (
                f"Local Codex runner recovered `{config.needs_human_label}`: {signal.reason}; "
                f"signature `{signal.signature}`; queued retry attempt {attempt}."
            ),
        )
    return NeedsHumanRecovery(
        issue.number,
        action,
        signal.reason,
        attempt,
        signature=signal.signature,
        detail=signal.detail,
    )


def recover_ci_pr(
    config: RunnerConfig,
    gh: GitHubCLI,
    issue: IssueTask,
    pr: dict[str, object],
    signal: StopSignal,
    attempt: int,
) -> NeedsHumanRecovery:
    branch = pr_branch(pr)
    number = pr_number(pr)
    owner_detail = validate_recovery_pr(config, issue.number, pr)
    if owner_detail is not None:
        return NeedsHumanRecovery(
            issue.number,
            "kept",
            POLICY_REASON,
            attempt,
            pr_number=number,
            branch=branch,
            signature=signal.signature,
            detail=owner_detail,
        )
    if config.dry_run:
        return NeedsHumanRecovery(
            issue.number,
            "would_fix_ci",
            signal.reason,
            attempt,
            pr_number=number,
            branch=branch,
            signature=signal.signature,
            detail=signal.detail,
        )

    workdir = config.workdir_path()
    git = GitOps(workdir)
    builder = PromptBuilder(config.evidence_root())
    evidence_dir = builder.issue_dir(issue.number)
    try:
        git.remove_transient_evidence()
        git.ensure_clean_worktree()
        git.checkout_remote_branch(branch or "")
    except (GitSafetyError, RunnerCommandError) as exc:
        return NeedsHumanRecovery(
            issue.number,
            "kept",
            "local_workspace_blocked",
            attempt,
            pr_number=number,
            branch=branch,
            signature=signal.signature,
            detail=str(exc),
        )
    fresh_pr = gh.view_pull_request(config.repo or "", number or 0)
    fresh_owner_detail = validate_recovery_pr(config, issue.number, fresh_pr)
    if fresh_owner_detail is not None:
        return NeedsHumanRecovery(
            issue.number,
            "kept",
            POLICY_REASON,
            attempt,
            pr_number=number,
            branch=branch,
            signature=signal.signature,
            detail=fresh_owner_detail,
        )
    failed_logs = gh.run_view_failed_logs(config.repo or "", str(number or branch))
    codex = CodexDriver(
        command=config.codex_command,
        command_template=config.codex_command_template,
        model=config.codex_model,
        sandbox=config.codex_sandbox,
        dry_run=False,
    )
    fix_prompt = builder.build(
        "03_fix_tests.md",
        issue,
        extra={"gate_log": failed_logs, "ci_summary": failed_logs},
        output_name=f"03_needs_human_ci_recovery_round_{attempt}.prompt.md",
    )
    recovery_log = evidence_dir / f"codex_needs_human_ci_recovery_round_{attempt}.log"
    codex.run_codex(fix_prompt, workdir, recovery_log)
    gate = GateRunner(
        workdir,
        config.gate_matrix_file(),
        timeout_seconds=config.gate_timeout_seconds,
    ).run(issue.labels, evidence_dir)
    if gate.status != "PASS":
        return NeedsHumanRecovery(
            issue.number,
            "kept",
            "local_failed",
            attempt,
            pr_number=number,
            branch=branch,
            signature=signal.signature,
            detail=gate.summary(),
        )
    git.commit_all(
        issue.number,
        f"Fix #{issue.number}: needs-human CI recovery round {attempt}",
        expected_branch=branch,
    )
    gh.comment_issue(
        config.repo or "",
        issue.number,
        (
            f"Local Codex runner attempting `{config.needs_human_label}` CI recovery; "
            f"reason `{signal.reason}`; signature `{signal.signature}`; attempt {attempt}."
        ),
    )
    git.push_branch(branch or "")
    ci = wait_for_ci(
        gh,
        repo=config.repo or "",
        pr_number_or_branch=str(number or branch),
        timeout_seconds=config.ci_timeout_seconds,
        poll_seconds=config.ci_poll_seconds,
    )
    if ci.status == "PASS":
        gh.remove_labels(config.repo or "", issue.number, [config.needs_human_label])
        gh.add_labels(config.repo or "", issue.number, [config.needs_human_recovered_label, config.ci_green_label])
        if number is not None:
            gh.add_labels(config.repo or "", number, [config.ci_green_label])
        gh.comment_issue(
            config.repo or "",
            issue.number,
            (
                f"Local Codex runner recovered `{config.needs_human_label}` via CI follow-up attempt {attempt}.\n"
                f"Reason: `{signal.reason}`\nSignature: `{signal.signature}`\nEvidence: {evidence_dir}"
            ),
        )
        return NeedsHumanRecovery(
            issue.number,
            "fixed_ci",
            signal.reason,
            attempt,
            pr_number=number,
            branch=branch,
            signature=signal.signature,
        )
    return NeedsHumanRecovery(
        issue.number,
        "kept",
        "ci_failed",
        attempt,
        pr_number=number,
        branch=branch,
        signature=signal.signature,
        detail=ci.summary,
    )


def render_summary(summary: dict[str, object]) -> str:
    return json.dumps(summary, indent=2, sort_keys=True)
