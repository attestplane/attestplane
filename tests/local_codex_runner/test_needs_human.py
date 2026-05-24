import json
from pathlib import Path

from scripts.local_codex_runner.ci_watch import CIWatchResult
from scripts.local_codex_runner.config import RunnerConfig
from scripts.local_codex_runner.gate_runner import CI_FAILED_GATE, GateReport
from scripts.local_codex_runner.github_cli import CheckStatus, RunnerCommandError
from scripts.local_codex_runner.models import IssueTask
from scripts.local_codex_runner.needs_human import (
    branch_checked_out_elsewhere,
    recover_needs_human,
    recover_needs_human_for_labels,
)


class FakeGH:
    def __init__(self, issues=None, prs=None, checks=None) -> None:
        self.issues = issues or []
        self.prs = prs or []
        self.checks = checks or []
        self.added: list[tuple[int, list[str]]] = []
        self.removed: list[tuple[int, list[str]]] = []
        self.comments: list[tuple[int, str]] = []
        self.ensured: list[list[str]] = []

    def list_issues(self, repo: str, label: str, limit: int):
        return self.issues[:limit]

    def list_pull_requests(self, repo: str, base: str, limit: int):
        return self.prs[:limit]

    def view_pull_request(self, repo: str, pr_number: int):
        for item in self.prs:
            if item.get("number") == pr_number:
                return item
        return {}

    def pr_checks(self, repo: str, pr_number_or_branch: str):
        return self.checks

    def remove_labels(self, repo: str, issue_number: int, labels: list[str]) -> None:
        self.removed.append((issue_number, labels))

    def add_labels(self, repo: str, issue_number: int, labels: list[str]) -> None:
        self.added.append((issue_number, labels))

    def ensure_labels(self, repo: str, labels: list[str]) -> None:
        self.ensured.append(labels)

    def comment_issue(self, repo: str, issue_number: int, body: str) -> None:
        self.comments.append((issue_number, body))

    def run_view_failed_logs(self, repo: str, pr_number_or_branch: str) -> str:
        return "pytest failed"


def issue(number: int, labels: list[str] | None = None) -> IssueTask:
    return IssueTask(number, f"Issue {number}", "", "", labels or [])


def pr(number: int, issue_number: int, author: str = "runner-bot") -> dict[str, object]:
    return {
        "author": {"login": author},
        "baseRefName": "main",
        "headRefName": f"codex/issue-{issue_number}-fix",
        "labels": [],
        "number": number,
        "title": f"Fix #{issue_number}",
    }


def base_config(tmp_path: Path, *, dry_run: bool = True) -> RunnerConfig:
    return RunnerConfig(
        repo="o/r",
        workdir=str(tmp_path),
        dry_run=dry_run,
        auto_recover_needs_human=True,
        max_needs_human_recoveries_per_run=2,
        max_needs_human_attempts=2,
        state_path="state.json",
    )


def test_dry_run_ci_failure_is_classified_without_writing(tmp_path: Path) -> None:
    config = base_config(tmp_path)
    gh = FakeGH(
        issues=[issue(12, ["auto-codex-approved", "codex-needs-human"])],
        prs=[pr(5, 12)],
        checks=[CheckStatus("lint", "FAILURE", "fail")],
    )

    summary = recover_needs_human(config, gh)

    assert summary["results"][0]["action"] == "would_fix_ci"
    assert summary["results"][0]["reason"] == "ci_failed"
    assert summary["results"][0]["attempt"] == 1
    assert gh.added == []
    assert gh.removed == []
    assert not (tmp_path / "state.json").exists()


def test_green_pr_needs_human_is_cleared_without_codex_repair(tmp_path: Path) -> None:
    config = base_config(tmp_path, dry_run=False)
    config.allowed_pr_authors = ["runner-bot"]
    gh = FakeGH(
        issues=[issue(22, ["auto-codex-approved", "codex-needs-human"])],
        prs=[pr(9, 22)],
        checks=[CheckStatus("ci", "SUCCESS", "pass")],
    )

    summary = recover_needs_human(config, gh)

    assert summary["results"][0]["action"] == "marked_ci_green"
    assert summary["results"][0]["reason"] == "ci_passed"
    assert gh.ensured == [["codex-recovered", "codex-ci-green"]]
    assert gh.removed == [(22, ["codex-needs-human"])]
    assert gh.added == [(22, ["codex-recovered", "codex-ci-green"]), (9, ["codex-ci-green"])]
    assert gh.comments


def test_kept_issue_does_not_consume_recovery_quota(tmp_path: Path) -> None:
    config = base_config(tmp_path)
    config.max_needs_human_recoveries_per_run = 1
    evidence_dir = tmp_path / "docs/validation/local_codex_runner/issue-18"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "failure.txt").write_text("429 rate limit\n", encoding="utf-8")
    gh = FakeGH(
        issues=[
            issue(17, ["auto-codex-approved", "codex-needs-human", "codex-policy-blocked"]),
            issue(18, ["auto-codex-approved", "codex-needs-human"]),
        ]
    )

    summary = recover_needs_human(config, gh)

    assert [item["issue_number"] for item in summary["results"]] == [17, 18]
    assert summary["results"][1]["action"] == "would_requeue"


def test_unknown_evidence_stays_human_blocked(tmp_path: Path) -> None:
    config = base_config(tmp_path)
    gh = FakeGH(issues=[issue(13, ["auto-codex-approved", "codex-needs-human"])])

    summary = recover_needs_human(config, gh)

    assert summary["results"][0]["action"] == "kept"
    assert summary["results"][0]["reason"] == "unknown"


def test_rate_limit_evidence_requeues_issue(tmp_path: Path) -> None:
    config = base_config(tmp_path, dry_run=False)
    evidence_dir = tmp_path / "docs/validation/local_codex_runner/issue-14"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "failure.txt").write_text("Codex usage limit reached; try again later\n", encoding="utf-8")
    gh = FakeGH(issues=[issue(14, ["auto-codex-approved", "codex-needs-human"])])

    summary = recover_needs_human(config, gh)

    assert summary["results"][0]["action"] == "requeued"
    assert summary["results"][0]["reason"] == "rate_limit"
    assert gh.ensured == [["codex-recovered"]]
    assert gh.removed == [(14, ["codex-needs-human"])]
    assert gh.added == [(14, ["codex-recovered"])]
    assert gh.comments
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert list(state["retry_counts"].values()) == [1]


def test_policy_blocking_label_is_never_recovered(tmp_path: Path) -> None:
    config = base_config(tmp_path, dry_run=False)
    gh = FakeGH(issues=[issue(15, ["auto-codex-approved", "codex-needs-human", "codex-policy-blocked"])])

    summary = recover_needs_human(config, gh)

    assert summary["results"][0]["action"] == "kept"
    assert summary["results"][0]["reason"] == "policy_boundary"
    assert gh.added == []
    assert gh.removed == []


def test_live_pr_recovery_requires_author_allowlist(tmp_path: Path) -> None:
    config = base_config(tmp_path, dry_run=False)
    gh = FakeGH(
        issues=[issue(16, ["auto-codex-approved", "codex-needs-human"])],
        prs=[pr(7, 16)],
        checks=[CheckStatus("lint", "FAILURE", "fail")],
    )

    summary = recover_needs_human(config, gh)

    assert summary["results"][0]["action"] == "kept"
    assert summary["results"][0]["reason"] == "policy_boundary"
    assert "allowed_pr_authors" in summary["results"][0]["detail"]


def test_pr_branch_must_match_issue_number(tmp_path: Path) -> None:
    config = base_config(tmp_path)
    wrong_branch = pr(8, 999)
    wrong_branch["title"] = "Fix #19"
    gh = FakeGH(
        issues=[issue(19, ["auto-codex-approved", "codex-needs-human"])],
        prs=[wrong_branch],
        checks=[CheckStatus("lint", "FAILURE", "fail")],
    )

    summary = recover_needs_human(config, gh)

    assert summary["results"][0]["action"] == "kept"
    assert summary["results"][0]["reason"] == "policy_boundary"
    assert "not runner-owned" in summary["results"][0]["detail"]


def test_recovery_respects_lane_filters(tmp_path: Path) -> None:
    config = base_config(tmp_path)
    p0_evidence = tmp_path / "docs/validation/local_codex_runner/issue-20"
    p1_evidence = tmp_path / "docs/validation/local_codex_runner/issue-21"
    p0_evidence.mkdir(parents=True)
    p1_evidence.mkdir(parents=True)
    (p0_evidence / "failure.txt").write_text("429 rate limit\n", encoding="utf-8")
    (p1_evidence / "failure.txt").write_text("429 rate limit\n", encoding="utf-8")
    gh = FakeGH(
        issues=[
            issue(20, ["auto-codex-approved", "codex-needs-human", "priority-P0"]),
            issue(21, ["auto-codex-approved", "codex-needs-human", "priority-P1"]),
        ]
    )

    summary = recover_needs_human_for_labels(config, gh, include_labels={"priority-P1"})

    assert [item["issue_number"] for item in summary["results"]] == [21]
    assert summary["results"][0]["action"] == "would_requeue"


def test_needs_human_issue_list_outage_is_reported_without_crashing(tmp_path: Path) -> None:
    config = base_config(tmp_path)

    class FailingGH:
        def list_issues(self, repo: str, label: str, limit: int):
            raise RunnerCommandError(
                ["gh", "issue", "list"],
                1,
                "proxyconnect tcp: dial tcp 127.0.0.1:7897: connect: connection refused",
            )

    summary = recover_needs_human(config, FailingGH())  # type: ignore[arg-type]

    assert summary["enabled"] is True
    assert summary["results"] == []
    assert summary["external_errors"][0]["stage"] == "list_needs_human"
    assert "proxyconnect tcp" in summary["external_errors"][0]["error"]


def test_needs_human_pr_list_outage_is_reported_without_crashing(tmp_path: Path) -> None:
    config = base_config(tmp_path)

    class FailingGH:
        def list_issues(self, repo: str, label: str, limit: int):
            return [issue(22, ["auto-codex-approved", "codex-needs-human"])]

        def list_pull_requests(self, repo: str, base: str, limit: int):
            raise RunnerCommandError(
                ["gh", "pr", "list"],
                1,
                'Post "https://api.github.com/graphql": EOF',
            )

    summary = recover_needs_human(config, FailingGH())  # type: ignore[arg-type]

    assert summary["enabled"] is True
    assert summary["results"] == []
    assert summary["external_errors"][0]["stage"] == "list_pull_requests"
    assert "api.github.com/graphql" in summary["external_errors"][0]["error"]


def test_recovery_scans_past_newer_out_of_lane_issues(tmp_path: Path) -> None:
    config = base_config(tmp_path)
    config.max_needs_human_recoveries_per_run = 1
    config.needs_human_scan_limit = 20
    evidence_dir = tmp_path / "docs/validation/local_codex_runner/issue-30"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "failure.txt").write_text("429 rate limit\n", encoding="utf-8")
    gh = FakeGH(
        issues=[
            *[
                issue(number, ["auto-codex-approved", "codex-needs-human", "priority-P1"])
                for number in range(100, 110)
            ],
            issue(30, ["auto-codex-approved", "codex-needs-human", "priority-P0"]),
        ]
    )

    summary = recover_needs_human_for_labels(config, gh, include_labels={"priority-P0"})

    assert [item["issue_number"] for item in summary["results"]] == [30]
    assert summary["results"][0]["action"] == "would_requeue"


def test_branch_checked_out_elsewhere_detects_other_worktree(monkeypatch, tmp_path: Path) -> None:
    config = base_config(tmp_path, dry_run=False)

    class FakeGit:
        def __init__(self, workdir):
            pass

        def run(self, args):
            return (
                f"worktree {tmp_path}\n"
                "HEAD abc\n"
                "branch refs/heads/main\n"
                "\n"
                "worktree /tmp/other-lane\n"
                "HEAD def\n"
                "branch refs/heads/codex/issue-1-fix\n"
                "\n"
            )

    monkeypatch.setattr("scripts.local_codex_runner.needs_human.GitOps", FakeGit)

    assert branch_checked_out_elsewhere(config, "codex/issue-1-fix") == (
        "branch codex/issue-1-fix is already checked out at /tmp/other-lane"
    )


def test_ci_recovery_codex_failure_is_reported_without_crashing(monkeypatch, tmp_path: Path) -> None:
    config = base_config(tmp_path, dry_run=False)
    config.allowed_pr_authors = ["runner-bot"]

    class FakeGit:
        def __init__(self, workdir):
            pass

        def run(self, args):
            return f"worktree {tmp_path}\nHEAD abc\nbranch refs/heads/main\n\n"

        def remove_transient_evidence(self):
            pass

        def ensure_clean_worktree(self):
            pass

        def current_branch(self):
            return "main"

        def checkout_remote_branch(self, branch):
            pass

        def has_unpushed_commits(self, branch):
            return False

    class FailingCodex:
        def __init__(self, **kwargs):
            pass

        def run_codex(self, prompt_file, workdir, log_path, timeout=None):
            raise RunnerCommandError(["codex", "exec"], 1, "HTTP error: 403 Forbidden")

    monkeypatch.setattr("scripts.local_codex_runner.needs_human.GitOps", FakeGit)
    monkeypatch.setattr("scripts.local_codex_runner.needs_human.CodexDriver", FailingCodex)

    gh = FakeGH(
        issues=[issue(31, ["auto-codex-approved", "codex-needs-human"])],
        prs=[pr(11, 31)],
        checks=[CheckStatus("pytest", "FAILURE", "fail")],
    )

    summary = recover_needs_human(config, gh)

    assert summary["results"][0]["action"] == "kept"
    assert summary["results"][0]["reason"] == "external_model_api_blocker"
    assert summary["results"][0]["attempt"] == 0
    assert "backend blocked recovery" in summary["results"][0]["detail"]
    assert gh.added == []
    assert gh.removed == []
    assert not (tmp_path / "state.json").exists()


def test_external_codex_backend_failure_does_not_poison_attempt_cap(monkeypatch, tmp_path: Path) -> None:
    config = base_config(tmp_path, dry_run=False)
    config.allowed_pr_authors = ["runner-bot"]

    class FakeGit:
        def __init__(self, workdir):
            pass

        def run(self, args):
            return f"worktree {tmp_path}\nHEAD abc\nbranch refs/heads/main\n\n"

        def remove_transient_evidence(self):
            pass

        def ensure_clean_worktree(self):
            pass

        def current_branch(self):
            return "main"

        def checkout_remote_branch(self, branch):
            pass

        def has_unpushed_commits(self, branch):
            return False

    class FailingCodex:
        def __init__(self, **kwargs):
            pass

        def run_codex(self, prompt_file, workdir, log_path, timeout=None):
            raise RunnerCommandError(
                ["codex", "exec"],
                1,
                "POST https://chatgpt.com/backend-api/codex/responses failed: 403 Forbidden",
            )

    monkeypatch.setattr("scripts.local_codex_runner.needs_human.GitOps", FakeGit)
    monkeypatch.setattr("scripts.local_codex_runner.needs_human.CodexDriver", FailingCodex)

    gh = FakeGH(
        issues=[issue(32, ["auto-codex-approved", "codex-needs-human"])],
        prs=[pr(12, 32)],
        checks=[CheckStatus("pytest", "FAILURE", "fail")],
    )

    first = recover_needs_human(config, gh)
    second = recover_needs_human(config, gh)

    assert first["results"][0]["reason"] == "external_model_api_blocker"
    assert second["results"][0]["reason"] == "external_model_api_blocker"
    assert first["results"][0]["attempt"] == 0
    assert second["results"][0]["attempt"] == 0
    assert not (tmp_path / "state.json").exists()


def test_ci_recovery_pushes_existing_clean_local_commit(monkeypatch, tmp_path: Path) -> None:
    config = base_config(tmp_path, dry_run=False)
    config.allowed_pr_authors = ["runner-bot"]
    pushed: list[str] = []
    selected_gates: list[str | None] = []

    class FakeGit:
        def __init__(self, workdir):
            pass

        def run(self, args):
            return f"worktree {tmp_path}\nHEAD abc\nbranch refs/heads/main\n\n"

        def remove_transient_evidence(self):
            pass

        def ensure_clean_worktree(self):
            pass

        def current_branch(self):
            return "codex/issue-33-fix"

        def checkout_remote_branch(self, branch):
            pass

        def has_unpushed_commits(self, branch):
            return True

        def push_branch(self, branch):
            pushed.append(branch)

    class PassingGate:
        def __init__(self, workdir, matrix_path, *, timeout_seconds):
            pass

        def run(self, labels, evidence_dir, *, preferred_gate=None):
            selected_gates.append(preferred_gate)
            return GateReport(status="PASS", selected_gate=preferred_gate or "default", commands=[])

    class UnexpectedCodex:
        def __init__(self, **kwargs):
            pass

        def run_codex(self, prompt_file, workdir, log_path, timeout=None):
            raise AssertionError("existing clean commits should be pushed without another Codex repair")

    def passing_ci(*args, **kwargs):
        return CIWatchResult(status="PASS", summary="ok", checks=[CheckStatus("ci", "SUCCESS", "pass")])

    monkeypatch.setattr("scripts.local_codex_runner.needs_human.GitOps", FakeGit)
    monkeypatch.setattr("scripts.local_codex_runner.needs_human.GateRunner", PassingGate)
    monkeypatch.setattr("scripts.local_codex_runner.needs_human.CodexDriver", UnexpectedCodex)
    monkeypatch.setattr("scripts.local_codex_runner.needs_human.wait_for_ci", passing_ci)

    gh = FakeGH(
        issues=[issue(33, ["auto-codex-approved", "codex-needs-human"])],
        prs=[pr(13, 33)],
        checks=[CheckStatus("pytest", "FAILURE", "fail")],
    )

    summary = recover_needs_human(config, gh)

    assert summary["results"][0]["action"] == "fixed_ci"
    assert summary["results"][0]["reason"] == "ci_failed"
    assert pushed == ["codex/issue-33-fix"]
    assert selected_gates == [CI_FAILED_GATE]
    assert gh.removed == [(33, ["codex-needs-human"])]


def test_ci_recovery_attempt_cap_allows_existing_clean_local_commit(monkeypatch, tmp_path: Path) -> None:
    config = base_config(tmp_path, dry_run=False)
    config.allowed_pr_authors = ["runner-bot"]
    state_path = tmp_path / "state.json"
    state_path.write_text(
        "{\n"
        '  "active_issue_ids": [],\n'
        '  "branch_mappings": {},\n'
        '  "last_result": null,\n'
        '  "processed_issue_ids": [],\n'
        '  "retry_counts": {"needs-human:34:ci_failed:2b01214d32c382db": 2}\n'
        "}\n",
        encoding="utf-8",
    )
    pushed: list[str] = []

    class FakeGit:
        def __init__(self, workdir):
            pass

        def run(self, args):
            return f"worktree {tmp_path}\nHEAD abc\nbranch refs/heads/main\n\n"

        def remove_transient_evidence(self):
            pass

        def ensure_clean_worktree(self):
            pass

        def current_branch(self):
            return "codex/issue-34-fix"

        def checkout_remote_branch(self, branch):
            pass

        def has_unpushed_commits(self, branch):
            return True

        def push_branch(self, branch):
            pushed.append(branch)

    class PassingGate:
        def __init__(self, workdir, matrix_path, *, timeout_seconds):
            pass

        def run(self, labels, evidence_dir, *, preferred_gate=None):
            return GateReport(status="PASS", selected_gate=preferred_gate or "default", commands=[])

    def passing_ci(*args, **kwargs):
        return CIWatchResult(status="PASS", summary="ok", checks=[CheckStatus("ci", "SUCCESS", "pass")])

    monkeypatch.setattr("scripts.local_codex_runner.needs_human.GitOps", FakeGit)
    monkeypatch.setattr("scripts.local_codex_runner.needs_human.GateRunner", PassingGate)
    monkeypatch.setattr("scripts.local_codex_runner.needs_human.wait_for_ci", passing_ci)

    gh = FakeGH(
        issues=[issue(34, ["auto-codex-approved", "codex-needs-human"])],
        prs=[pr(14, 34)],
        checks=[CheckStatus("pytest", "FAILURE", "fail")],
    )

    summary = recover_needs_human(config, gh)

    assert summary["results"][0]["action"] == "fixed_ci"
    assert summary["results"][0]["attempt"] == 3
    assert pushed == ["codex/issue-34-fix"]
