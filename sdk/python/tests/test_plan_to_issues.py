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


def test_parse_structured_plan_payload_into_planned_tasks() -> None:
    markdown = """
## Auto-Generated Medium Plan

<!-- ATT_PLAN_SCHEMA_V1_START -->
```json
{"anchor_tag":"v1.4.9","consultation_level":"feature","head_sha":"abc123","issues":[{"acceptance_criteria":["Document the user-visible boundary."],"modules":["release notes","release train"],"ordinal":1,"priority":"P0","rollout_notes":"Keep the release boundary explicit and small.","title":"[P0][release] Define the v1.5.0 release boundary and scope","validation_commands":["git diff --check"]}],"milestone_tag":"v1.5.0","plan_id":"deadbeef","plan_level":"medium","recent_real_commits":[],"schema":"attestplane.plan.v1","schema_version":1}
```
<!-- ATT_PLAN_SCHEMA_V1_END -->
"""

    tasks = plan_to_issues.parse_plan(markdown, source_issue=61)

    assert len(tasks) == 1
    assert tasks[0].plan_id == "deadbeef"
    assert "Plan ID: `deadbeef`" in tasks[0].body
    assert "Plan schema: `attestplane.plan.v1`" in tasks[0].body
    assert "priority-P0" in tasks[0].labels
    assert "area:release-integrity" in tasks[0].labels
