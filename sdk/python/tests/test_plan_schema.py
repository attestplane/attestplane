from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts/release/plan_schema.py"

spec = importlib.util.spec_from_file_location("plan_schema", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
plan_schema = importlib.util.module_from_spec(spec)
sys.modules["plan_schema"] = plan_schema
spec.loader.exec_module(plan_schema)


def test_structured_plan_block_round_trips_and_is_idempotent() -> None:
    payload = {
        "schema": plan_schema.PLAN_SCHEMA_NAME,
        "schema_version": plan_schema.PLAN_SCHEMA_VERSION,
        "milestone_tag": "v1.5.0",
        "anchor_tag": "v1.4.9",
        "head_sha": "abc123",
        "plan_level": "medium",
        "consultation_level": "feature",
        "recent_real_commits": [{"sha": "abc123", "subject": "feat: x"}],
        "issues": [
            {
                "ordinal": 1,
                "title": "[P0][release] Define the v1.5.0 release boundary and scope",
                "priority": "P0",
                "modules": ["release notes", "release train"],
                "acceptance_criteria": ["Document the boundary."],
                "validation_commands": ["git diff --check"],
                "rollout_notes": "Keep the release boundary explicit and small.",
            },
        ],
    }
    plan_with_id = plan_schema.with_plan_id(payload)
    comment = plan_schema.append_plan_block("## Plan body", plan_with_id)

    extracted = plan_schema.extract_plan_payload(comment)

    assert extracted is not None
    assert extracted["plan_id"] == plan_with_id["plan_id"]
    assert extracted["schema"] == plan_schema.PLAN_SCHEMA_NAME
    assert extracted["consultation_level"] == "feature"
    assert plan_schema.compute_plan_id(extracted) == plan_with_id["plan_id"]


def test_plan_issue_body_includes_source_and_plan_id() -> None:
    body = plan_schema.plan_issue_body(
        source_issue=61,
        plan_id="deadbeef",
        plan_schema=plan_schema.PLAN_SCHEMA_NAME,
        task={
            "title": "[P1][docs] Publish release note",
            "priority": "P1",
            "modules": ["docs/release-notes"],
            "acceptance_criteria": ["Document the delta."],
            "validation_commands": ["git diff --check"],
            "rollout_notes": "Incremental is fine.",
        },
    )

    assert "Source planning issue: #61" in body
    assert "Plan schema: `attestplane.plan.v1`" in body
    assert "Plan ID: `deadbeef`" in body
    assert "Acceptance criteria:" in body
