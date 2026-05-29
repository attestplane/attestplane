from pathlib import Path

import pytest
from scripts.local_codex_runner.git_ops import (
    GitOps,
    GitSafetyError,
    is_forbidden_path,
    is_transient_evidence_path,
    slugify,
)


class FakeGit(GitOps):
    def __init__(self, outputs):
        super().__init__(Path("fake-attestplane"))
        self.outputs = outputs

    def run(self, args):
        self.commands_run.append(" ".join(args))
        return self.outputs.get(" ".join(args), "")


def test_dirty_worktree_fails() -> None:
    git = FakeGit({"status --porcelain": " M file.py\n"})

    with pytest.raises(GitSafetyError):
        git.ensure_clean_worktree()


def test_branch_slug_deterministic() -> None:
    assert slugify("P0: Nightly Anchor Failure!") == "p0-nightly-anchor-failure"


def test_main_branch_commit_is_rejected() -> None:
    git = FakeGit({"branch --show-current": "main\n", "status --porcelain": " M x\n"})

    with pytest.raises(GitSafetyError):
        git.commit_all(12, "Fix #12")


def test_commit_uses_dco_signoff() -> None:
    git = FakeGit(
        {
            "branch --show-current": "codex/issue-12-fix\n",
            "status --porcelain": " M x\n",
        }
    )

    git.commit_all(12, "Fix #12")

    assert "commit -s -m Fix #12" in git.commands_run


def test_remote_checkout_ref_uses_detached_origin_branch() -> None:
    git = FakeGit({})

    git.checkout_base_and_pull("origin/main")

    assert git.commands_run == ["fetch origin main", "checkout --detach origin/main"]


def test_remote_issue_branch_checkout_is_limited_to_codex_branches() -> None:
    git = FakeGit({"branch --show-current": "main\n"})

    git.checkout_remote_branch("codex/issue-12-fix")

    assert git.commands_run == [
        "fetch origin codex/issue-12-fix",
        "branch --show-current",
        "checkout -B codex/issue-12-fix origin/codex/issue-12-fix",
    ]


def test_remote_issue_branch_checkout_preserves_unpushed_current_branch() -> None:
    git = FakeGit(
        {
            "branch --show-current": "codex/issue-12-fix\n",
            "rev-list --count origin/codex/issue-12-fix..HEAD": "1\n",
        }
    )

    git.checkout_remote_branch("codex/issue-12-fix")

    assert git.commands_run == [
        "fetch origin codex/issue-12-fix",
        "branch --show-current",
        "rev-list --count origin/codex/issue-12-fix..HEAD",
    ]


def test_remote_branch_checkout_rejects_main_and_non_codex() -> None:
    git = FakeGit({})

    with pytest.raises(GitSafetyError):
        git.checkout_remote_branch("main")
    with pytest.raises(GitSafetyError):
        git.checkout_remote_branch("feature/unsafe")


def test_forbidden_file_changed_is_rejected() -> None:
    assert is_forbidden_path(".env")
    assert is_forbidden_path("release/credentials.json")


def test_commit_removes_transient_prompt_and_log_evidence() -> None:
    status = "\n".join(
        [
            " M CHANGELOG.md",
            "?? docs/validation/local_codex_runner/issue-12/01_plan.prompt.md",
            "?? docs/validation/local_codex_runner/issue-12/codex_code.log",
            "?? docs/validation/local_codex_runner/issue-12/failure.txt",
            " M docs/validation/local_codex_runner/issue-12/gate_report.md",
            "?? docs/validation/local_codex_runner/issue-12/runner_result.json",
            "?? docs/validation/local_codex_runner/issue-12/runner_result.md",
            "",
        ]
    )
    git = FakeGit(
        {
            "branch --show-current": "codex/issue-12-fix\n",
            "status --porcelain": status,
            "status --porcelain --untracked-files=all": status,
        }
    )

    git.commit_all(12, "Fix #12")

    assert (
        "restore --worktree --staged -- docs/validation/local_codex_runner/issue-12/gate_report.md"
    ) in git.commands_run
    assert (
        "clean -f -- docs/validation/local_codex_runner/issue-12/01_plan.prompt.md "
        "docs/validation/local_codex_runner/issue-12/codex_code.log "
        "docs/validation/local_codex_runner/issue-12/failure.txt "
        "docs/validation/local_codex_runner/issue-12/runner_result.json "
        "docs/validation/local_codex_runner/issue-12/runner_result.md"
    ) in git.commands_run
    assert "add -A" in git.commands_run


def test_transient_evidence_path_only_matches_runner_prompts_and_logs() -> None:
    assert is_transient_evidence_path(
        "docs/validation/local_codex_runner/issue-12/01_plan.prompt.md"
    )
    assert is_transient_evidence_path(
        "docs/validation/local_codex_runner/issue-12/codex_review.log"
    )
    assert is_transient_evidence_path(
        "docs/validation/local_codex_runner/issue-12/failure.txt"
    )
    assert is_transient_evidence_path(
        "docs/validation/local_codex_runner/issue-12/gate_report.md"
    )
    assert is_transient_evidence_path(
        "docs/validation/local_codex_runner/issue-12/gate_report.json"
    )
    assert is_transient_evidence_path(
        "docs/validation/local_codex_runner/issue-12/runner_result.json"
    )
    assert is_transient_evidence_path(
        "docs/validation/local_codex_runner/issue-12/runner_result.md"
    )
    assert not is_transient_evidence_path(
        "docs/validation/local_codex_runner/issue-12/codex_review_report.md"
    )
