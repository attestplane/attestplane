#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Prompt rendering for staged local Codex repair."""

from __future__ import annotations

from pathlib import Path

from scripts.local_codex_runner.github_cli import redact
from scripts.local_codex_runner.models import IssueTask


PROMPT_DIR = Path(__file__).with_name("prompts")


class PromptBuilder:
    def __init__(self, evidence_root: Path) -> None:
        self.evidence_root = evidence_root

    def issue_dir(self, issue_number: int) -> Path:
        path = self.evidence_root / f"issue-{issue_number}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def build(
        self,
        template_name: str,
        task: IssueTask,
        *,
        extra: dict[str, str] | None = None,
        output_name: str | None = None,
    ) -> Path:
        issue_dir = self.issue_dir(task.number)
        template = (PROMPT_DIR / template_name).read_text(encoding="utf-8")
        values = {
            "issue_number": str(task.number),
            "issue_title": task.title,
            "issue_body": task.body,
            "issue_url": task.url,
            "issue_labels": ", ".join(task.labels),
            "evidence_dir": str(issue_dir),
            "plan_path": str(issue_dir / "plan.md"),
            "review_json_path": str(issue_dir / "codex_review_report.json"),
            "review_md_path": str(issue_dir / "codex_review_report.md"),
            "gate_log": "",
            "ci_summary": "",
        }
        values.update(extra or {})
        rendered = render_template(template, values)
        output = issue_dir / (output_name or template_name)
        output.write_text(redact(rendered), encoding="utf-8")
        return output

    def build_pr_body(self, task: IssueTask, *, validation: str, evidence: str, residual_risks: str) -> str:
        template = (PROMPT_DIR / "05_pr_body.md").read_text(encoding="utf-8")
        return redact(
            render_template(
                template,
                {
                    "issue_number": str(task.number),
                    "issue_title": task.title,
                    "issue_labels": ", ".join(task.labels),
                    "validation": validation,
                    "evidence": evidence,
                    "residual_risks": residual_risks,
                },
            )
        )


def render_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", redact(str(value)))
    return rendered

