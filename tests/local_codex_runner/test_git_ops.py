from pathlib import Path

import pytest

from scripts.local_codex_runner.git_ops import GitOps, GitSafetyError, is_forbidden_path, slugify


class FakeGit(GitOps):
    def __init__(self, outputs):
        super().__init__(Path("/tmp/fake-attestplane"))
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
            "diff --name-only HEAD": "x\n",
        }
    )

    git.commit_all(12, "Fix #12")

    assert "commit -s -m Fix #12" in git.commands_run


def test_forbidden_file_changed_is_rejected() -> None:
    assert is_forbidden_path(".env")
    assert is_forbidden_path("release/credentials.json")
