from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts/release/plan_to_issues.py"

spec = importlib.util.spec_from_file_location("plan_to_issues", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
plan_to_issues = importlib.util.module_from_spec(spec)
sys.modules["plan_to_issues"] = plan_to_issues
spec.loader.exec_module(plan_to_issues)


def test_parse_opus_issue_sections_into_planned_tasks() -> None:
    markdown = """
**ISSUE 1 · [P0][release] Consolidate release pipeline fix-forward cases**
- Source planning issue: #61
- Priority: P0
- Affected modules: release scripts
- Acceptance criteria:
  1. Adds regression coverage.
- Validation commands:
  - pytest

**ISSUE 2 · [P1][docs][test] Turn quickstart into smoke coverage**
- Priority: P1
- Acceptance criteria:
  1. Runs commands from docs.
"""

    tasks = plan_to_issues.parse_plan(markdown, source_issue=61)

    assert [task.title for task in tasks] == [
        "[P0][release] Consolidate release pipeline fix-forward cases",
        "[P1][docs][test] Turn quickstart into smoke coverage",
    ]
    assert tasks[0].priority == "P0"
    assert "planned-task" in tasks[0].labels
    assert "priority-P0" in tasks[0].labels
    assert "area:release-integrity" in tasks[0].labels
    assert "Source planning issue: #61" in tasks[1].body
    assert "priority:P1" in tasks[1].labels
    assert "area:docs" in tasks[1].labels


def test_parse_heading_style_issue_sections() -> None:
    markdown = """
### ISSUE 3 - [P2][security] Monitor OpenSSF Scorecard regressions

Priority: P2
Acceptance criteria:
- Opens an issue on regression.
"""

    tasks = plan_to_issues.parse_plan(markdown, source_issue=99)

    assert len(tasks) == 1
    assert tasks[0].title == "[P2][security] Monitor OpenSSF Scorecard regressions"
    assert tasks[0].priority == "P2"
    assert "priority:P2" in tasks[0].labels
    assert "type:security" in tasks[0].labels
    assert "Source planning issue: #99" in tasks[0].body


def test_parse_architecture_module_labels() -> None:
    markdown = """
**ISSUE 1 · [P0][architecture][compatibility] Define compatibility contract**
- Acceptance criteria:
  1. Adds migration contract.
"""

    tasks = plan_to_issues.parse_plan(markdown, source_issue=123)

    assert tasks[0].title == "[P0][architecture][compatibility] Define compatibility contract"
    assert "planned-task" in tasks[0].labels
    assert "priority-P0" in tasks[0].labels
    assert "architecture-audit" in tasks[0].labels
    assert "area:conformance" in tasks[0].labels
