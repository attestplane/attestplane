from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts/release/architecture_audit_trigger.py"

spec = importlib.util.spec_from_file_location("architecture_audit_trigger", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
architecture_audit_trigger = importlib.util.module_from_spec(spec)
sys.modules["architecture_audit_trigger"] = architecture_audit_trigger
spec.loader.exec_module(architecture_audit_trigger)


def versions(count: int) -> list[object]:
    return [architecture_audit_trigger.StableVersion(1, index // 10, index % 10) for index in range(count)]


def commit(subject: str) -> object:
    return architecture_audit_trigger.CommitInfo(
        sha="a" * 40,
        time="2026-05-21T00:00:00+00:00",
        author="Test",
        subject=subject,
    )


def test_is_milestone_release_matches_50_stable_release_boundaries() -> None:
    parse = architecture_audit_trigger.StableVersion.parse

    assert architecture_audit_trigger.is_milestone_release(parse("v1.5.0")) is True
    assert architecture_audit_trigger.is_milestone_release(parse("v1.10.0")) is True
    assert architecture_audit_trigger.is_milestone_release(parse("v2.0.0")) is True
    assert architecture_audit_trigger.is_milestone_release(parse("v1.4.10")) is False
    assert architecture_audit_trigger.is_milestone_release(parse("v1.5.1")) is False
    assert architecture_audit_trigger.is_milestone_release(parse("v0.5.0")) is False


def test_classify_upgrade_level_separates_daily_medium_and_architecture() -> None:
    parse = architecture_audit_trigger.StableVersion.parse

    assert architecture_audit_trigger.classify_upgrade_level(parse("v1.4.9")) == "daily"
    assert architecture_audit_trigger.classify_upgrade_level(parse("v1.5.0")) == "medium"
    assert architecture_audit_trigger.classify_upgrade_level(parse("v2.0.0")) == "architecture"


def test_decide_audit_skips_daily_small_upgrade() -> None:
    stable_tags = versions(51)
    commits = [commit("feat: add meaningful product work")]

    decision = architecture_audit_trigger.decide_audit(
        milestone_tag="v1.4.9",
        anchor_tag=None,
        stable_tags=stable_tags,
        commits=commits,
    )

    assert decision.action == "daily-plan"
    assert decision.reason == "daily_small_upgrade"
    assert decision.should_open_issue is True
    assert decision.should_upload_artifact is True
    assert decision.upgrade_label == "upgrade-daily"


def test_decide_audit_skips_daily_small_upgrade_when_no_real_work_exists() -> None:
    stable_tags = versions(51)
    commits = [commit("chore(release): prepare v1.4.9")]

    decision = architecture_audit_trigger.decide_audit(
        milestone_tag="v1.4.9",
        anchor_tag=None,
        stable_tags=stable_tags,
        commits=commits,
    )

    assert decision.action == "skip"
    assert decision.reason == "daily_small_upgrade"


def test_fallback_anchor_prefers_prior_five_minor_boundary() -> None:
    parse = architecture_audit_trigger.StableVersion.parse
    tags = [parse("v1.0.0"), *versions(56)]

    assert architecture_audit_trigger.fallback_anchor_tag(tags, parse("v1.5.0")) == "v1.0.0"


def test_decide_audit_requests_medium_plan_even_before_50_stable_releases() -> None:
    stable_tags = [architecture_audit_trigger.StableVersion(1, 5, 0)]
    commits = [
        commit("feat: capability one"),
        commit("fix: edge case two"),
        commit("docs: explain three"),
        commit("test: cover four"),
        commit("refactor: simplify five"),
    ]

    decision = architecture_audit_trigger.decide_audit(
        milestone_tag="v1.5.0",
        anchor_tag=None,
        stable_tags=stable_tags,
        commits=commits,
    )

    assert decision.action == "medium-plan"
    assert decision.reason == "half_version_medium_upgrade"
    assert decision.upgrade_label == "upgrade-medium"


def test_decide_audit_skips_pure_release_prep_window() -> None:
    stable_tags = versions(51)
    commits = [commit("chore(release): prepare v1.5.0")]

    decision = architecture_audit_trigger.decide_audit(
        milestone_tag="v1.5.0",
        anchor_tag=None,
        stable_tags=stable_tags,
        commits=commits,
    )

    assert decision.action == "skip"
    assert decision.reason == "no_substantive_changes_since_anchor"


def test_decide_audit_requests_medium_plan_for_half_version_with_any_real_work() -> None:
    stable_tags = versions(51)
    commits = [
        commit("feat: add one capability"),
    ]

    decision = architecture_audit_trigger.decide_audit(
        milestone_tag="v1.5.0",
        anchor_tag=None,
        stable_tags=stable_tags,
        commits=commits,
    )

    assert decision.action == "medium-plan"
    assert decision.reason == "half_version_medium_upgrade"
    assert decision.should_upload_artifact is True
    assert decision.should_open_issue is True


def test_decide_audit_requests_medium_plan_for_half_version_with_real_work() -> None:
    stable_tags = versions(51)
    commits = [
        commit("feat: capability one"),
        commit("fix: edge case two"),
        commit("docs: explain three"),
        commit("test: cover four"),
        commit("refactor: simplify five"),
    ]

    decision = architecture_audit_trigger.decide_audit(
        milestone_tag="v1.5.0",
        anchor_tag=None,
        stable_tags=stable_tags,
        commits=commits,
    )

    assert decision.action == "medium-plan"
    assert decision.reason == "half_version_medium_upgrade"
    assert decision.should_open_issue is True


def test_decide_audit_requests_architecture_plan_for_integer_version() -> None:
    stable_tags = versions(60)
    commits = [commit("feat: major architecture surface")]

    decision = architecture_audit_trigger.decide_audit(
        milestone_tag="v2.0.0",
        anchor_tag=None,
        stable_tags=stable_tags,
        commits=commits,
    )

    assert decision.action == "architecture-plan"
    assert decision.reason == "integer_version_architecture_upgrade"
    assert decision.upgrade_label == "upgrade-architecture"


def test_render_issue_body_contains_local_opus_prompt() -> None:
    manifest = {
        "milestone_tag": "v1.5.0",
        "anchor_tag": "v1.0.0",
        "head_sha": "abc123",
        "stable_release_count": 50,
        "real_commit_count": 5,
        "release_prep_commit_count": 45,
        "action": "medium-plan",
        "reason": "half_version_medium_upgrade",
        "plan_level": "medium",
        "recent_real_commits": [{"sha": "abc123", "time": "2026-05-21", "subject": "feat: x"}],
        "open_issues": [
            {
                "number": 62,
                "title": "[P0][release] Existing release train regression suite",
                "labels": ["planned-task", "priority-P0"],
            }
        ],
    }

    body = architecture_audit_trigger.render_issue_body(manifest)

    assert "ask_opus.sh architect" in body
    assert "architecture-gap-audit-v1.5.0.md" in body
    assert "plan-to-issues" in body
    assert "The workflow posts that plan" in body
    assert "`planned-task`" in body
    assert "Execution rule: work only starts from those generated task issues" in body
    assert "Current Open GitHub Issues" in body
    assert "#62 [P0][release] Existing release train regression suite" in body


def test_render_auto_plan_contains_issue_ready_sections_for_each_level() -> None:
    daily_manifest = {
        "milestone_tag": "v1.4.9",
        "anchor_tag": "v1.4.8",
        "head_sha": "abc123",
        "plan_level": "daily",
        "recent_real_commits": [{"sha": "abc123", "subject": "feat: small fix"}],
    }
    medium_manifest = {
        "milestone_tag": "v1.5.0",
        "anchor_tag": "v1.4.9",
        "head_sha": "def456",
        "plan_level": "medium",
        "recent_real_commits": [{"sha": "def456", "subject": "feat: feature"}],
    }
    architecture_manifest = {
        "milestone_tag": "v2.0.0",
        "anchor_tag": "v1.5.0",
        "head_sha": "ghi789",
        "plan_level": "architecture",
        "recent_real_commits": [{"sha": "ghi789", "subject": "feat: architecture surface"}],
    }

    daily_plan = architecture_audit_trigger.render_auto_plan(daily_manifest)
    medium_plan = architecture_audit_trigger.render_auto_plan(medium_manifest)
    architecture_plan = architecture_audit_trigger.render_auto_plan(architecture_manifest)

    assert "Auto-Generated Daily Plan" in daily_plan
    assert "ISSUE 1" in daily_plan
    assert "[P0][release]" in daily_plan
    assert "Auto-Generated Medium Plan" in medium_plan
    assert "ISSUE 4" in medium_plan
    assert "Auto-Generated Architecture Plan" in architecture_plan
    assert "ISSUE 5" in architecture_plan
    assert "[P0][architecture][compatibility]" in architecture_plan
    assert "planned-task" in architecture_plan


def test_consult_opus_for_plan_uses_issue_ready_fake_response(monkeypatch) -> None:
    manifest = {
        "milestone_tag": "v1.5.9",
        "anchor_tag": "v1.5.8",
        "head_sha": "abc123",
        "plan_level": "daily",
        "recent_real_commits": [{"sha": "abc123", "subject": "feat: improve daily task source"}],
    }
    fake_plan = """
## Opus Daily Plan

**ISSUE 1 · [P1][automation] Wire daily task source to open issues**
- Priority: P1
- Affected modules: release train
- Acceptance criteria:
  1. Daily tasks are generated from current open issues.
- Validation commands:
  - `git diff --check`
- Rollout / migration notes: no release bypass.
""".strip()
    monkeypatch.setenv(architecture_audit_trigger.OPUS_PLAN_FAKE_RESPONSE_ENV, fake_plan)

    accepted = architecture_audit_trigger.consult_opus_for_plan(manifest, "request body")

    assert accepted.source == "opus-fake-response"
    assert accepted.fallback_reason == ""
    assert "Plan source: opus-fake-response" in accepted.body
    assert "[P1][automation] Wire daily task source to open issues" in accepted.body
    assert "ATT_PLAN_SCHEMA_V1_START" not in accepted.body


def test_consult_opus_for_plan_falls_back_when_opus_unconfigured(monkeypatch) -> None:
    manifest = {
        "milestone_tag": "v1.5.9",
        "anchor_tag": "v1.5.8",
        "head_sha": "abc123",
        "plan_level": "daily",
        "recent_real_commits": [{"sha": "abc123", "subject": "feat: improve daily task source"}],
    }
    monkeypatch.delenv(architecture_audit_trigger.OPUS_PLAN_FAKE_RESPONSE_ENV, raising=False)
    monkeypatch.delenv(architecture_audit_trigger.OPUS_PLAN_COMMAND_ENV, raising=False)

    accepted = architecture_audit_trigger.consult_opus_for_plan(manifest, "request body")

    assert accepted.source == "deterministic-template"
    assert accepted.fallback_reason == "opus_command_not_configured"
    assert "Opus consultation fallback reason: opus_command_not_configured" in accepted.body
    assert "Auto-Generated Daily Plan" in accepted.body


def test_consult_opus_for_plan_rejects_non_issue_ready_output(monkeypatch) -> None:
    manifest = {
        "milestone_tag": "v1.5.9",
        "anchor_tag": "v1.5.8",
        "head_sha": "abc123",
        "plan_level": "daily",
        "recent_real_commits": [{"sha": "abc123", "subject": "feat: improve daily task source"}],
    }
    monkeypatch.setenv(architecture_audit_trigger.OPUS_PLAN_FAKE_RESPONSE_ENV, "Looks good, no tasks.")

    accepted = architecture_audit_trigger.consult_opus_for_plan(manifest, "request body")

    assert accepted.source == "deterministic-template"
    assert accepted.fallback_reason == "fake_response_not_issue_ready"
    assert "Auto-Generated Daily Plan" in accepted.body


def test_build_plan_payload_produces_structured_plan_block() -> None:
    manifest = {
        "milestone_tag": "v1.5.0",
        "anchor_tag": "v1.4.9",
        "head_sha": "abc123",
        "plan_level": "medium",
        "recent_real_commits": [{"sha": "abc123", "subject": "feat: x"}],
        "open_issues": [
            {
                "number": 62,
                "title": "[P0][release] Existing release train regression suite",
                "labels": ["planned-task", "priority-P0"],
            }
        ],
    }

    payload = architecture_audit_trigger.build_plan_payload(manifest)
    plan_with_id = architecture_audit_trigger.with_plan_id(payload)
    block = architecture_audit_trigger.append_plan_block("## Auto-Generated Medium Plan", plan_with_id)

    assert payload["consultation_level"] == "feature"
    assert payload["schema"] == "attestplane.plan.v1"
    assert plan_with_id["plan_id"]
    assert plan_with_id["open_issues"] == manifest["open_issues"]
    assert "ATT_PLAN_SCHEMA_V1_START" in block
    assert "plan_id" in block


def test_load_open_issues_normalizes_github_issue_json(tmp_path: Path) -> None:
    issues_path = tmp_path / "open-issues.json"
    issues_path.write_text(
        """
[
  {
    "number": 62,
    "title": "[P0][release] Existing work",
    "labels": [{"name": "planned-task"}, {"name": "priority-P0"}],
    "url": "https://github.example/issues/62",
    "updatedAt": "2026-05-21T00:00:00Z"
  },
  {"number": "bad", "title": "ignored", "labels": []}
]
""".strip(),
        encoding="utf-8",
    )

    issues = architecture_audit_trigger.load_open_issues(issues_path)

    assert issues == [
        {
            "number": 62,
            "title": "[P0][release] Existing work",
            "labels": ["planned-task", "priority-P0"],
            "url": "https://github.example/issues/62",
            "updatedAt": "2026-05-21T00:00:00Z",
        }
    ]
