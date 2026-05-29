from pathlib import Path

from scripts.local_codex_runner.models import IssueTask
from scripts.local_codex_runner.prompt_builder import PromptBuilder


def test_prompt_contains_issue_and_red_lines(tmp_path: Path) -> None:
    task = IssueTask(
        9,
        "Claim gap",
        "Body with token=secret123",
        "https://issue",
        ["auto-codex-approved", "claim-safety"],
    )

    path = PromptBuilder(tmp_path).build("02_code.md", task)
    text = path.read_text(encoding="utf-8")

    assert "Claim gap" in text
    assert "claim-safety" in text
    assert "Do not lower P0/P1 severity" in text
    assert "[REDACTED]" in text


def test_pr_body_contains_fixes(tmp_path: Path) -> None:
    task = IssueTask(9, "Claim gap", "", "", ["auto-codex-approved"])

    body = PromptBuilder(tmp_path).build_pr_body(
        task, validation="pytest", evidence="docs/validation/x", residual_risks="None"
    )

    assert "Fixes #9" in body
    assert "No package publish" in body
