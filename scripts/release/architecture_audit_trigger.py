#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Prepare development-plan artifacts for stable release milestones.

This script is intentionally read-only unless the GitHub workflow passes its
outputs to ``gh issue create``. It never creates or moves git tags, never
publishes packages, and never calls external AI services directly.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STABLE_TAG_RE = re.compile(r"^v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")
RE_RELEASE_PREP = re.compile(r"^chore\(release\): prepare v\d+\.\d+\.\d+(-\w+)?$")
AUDIT_LABEL = "architecture-audit"
PLAN_LABEL = "development-plan"
TASK_LABEL = "planned-task"
MEDIUM_UPGRADE_LABEL = "upgrade-medium"
ARCHITECTURE_UPGRADE_LABEL = "upgrade-architecture"
AUDITED_LABEL = "audited"
MILESTONE_STABLE_RELEASES = 50


@dataclass(frozen=True, order=True)
class StableVersion:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, tag: str) -> "StableVersion":
        match = STABLE_TAG_RE.fullmatch(tag.strip())
        if match is None:
            raise ValueError(f"not a suffix-free stable tag: {tag}")
        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
        )

    @property
    def tag(self) -> str:
        return f"v{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class CommitInfo:
    sha: str
    time: str
    author: str
    subject: str

    @property
    def kind(self) -> str:
        if RE_RELEASE_PREP.fullmatch(self.subject):
            return "release-prep"
        if self.subject.startswith("Merge "):
            return "merge"
        return "real"

    def as_dict(self) -> dict[str, str]:
        return {
            "sha": self.sha,
            "time": self.time,
            "author": self.author,
            "subject": self.subject,
            "kind": self.kind,
        }


@dataclass(frozen=True)
class AuditDecision:
    action: str
    reason: str
    plan_level: str
    milestone_tag: str
    anchor_tag: str | None
    stable_release_count: int
    real_commit_count: int
    issue_title: str

    @property
    def should_open_issue(self) -> bool:
        return self.action in {"medium-plan", "architecture-plan"}

    @property
    def should_upload_artifact(self) -> bool:
        return self.action in {"medium-plan", "architecture-plan", "manifest-only"}

    @property
    def upgrade_label(self) -> str:
        if self.plan_level == "architecture":
            return ARCHITECTURE_UPGRADE_LABEL
        if self.plan_level == "medium":
            return MEDIUM_UPGRADE_LABEL
        return ""


def run_git(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def stable_tag_versions(tags: list[str]) -> list[StableVersion]:
    versions: list[StableVersion] = []
    for tag in tags:
        try:
            versions.append(StableVersion.parse(tag))
        except ValueError:
            continue
    return sorted(set(versions))


def read_stable_tags() -> list[StableVersion]:
    stdout = run_git(["tag", "--list", "v*.*.*"])
    return stable_tag_versions([line.strip() for line in stdout.splitlines() if line.strip()])


def is_milestone_release(version: StableVersion) -> bool:
    return classify_upgrade_level(version) in {"medium", "architecture"}


def is_audit_anchor_release(version: StableVersion) -> bool:
    return version.major >= 1 and version.patch == 0 and version.minor % 5 == 0


def classify_upgrade_level(version: StableVersion) -> str:
    if version.major >= 1 and version.minor == 0 and version.patch == 0:
        return "architecture"
    if version.major >= 1 and version.minor > 0 and version.minor % 5 == 0 and version.patch == 0:
        return "medium"
    return "daily"


def tag_index(tags: list[StableVersion], tag: str) -> int | None:
    try:
        version = StableVersion.parse(tag)
    except ValueError:
        return None
    try:
        return tags.index(version)
    except ValueError:
        return None


def fallback_anchor_tag(tags: list[StableVersion], milestone: StableVersion) -> str | None:
    older = [version for version in tags if version < milestone]
    if not older:
        return None
    anchor_boundaries = [version for version in older if is_audit_anchor_release(version)]
    if anchor_boundaries:
        return anchor_boundaries[-1].tag
    if len(older) >= MILESTONE_STABLE_RELEASES:
        return older[-MILESTONE_STABLE_RELEASES].tag
    return older[0].tag


def count_stable_releases(tags: list[StableVersion], anchor_tag: str | None, milestone: StableVersion) -> int:
    relevant = [version for version in tags if version <= milestone]
    if anchor_tag is None:
        return len(relevant)
    anchor_idx = tag_index(relevant, anchor_tag)
    if anchor_idx is None:
        return len(relevant)
    return len(relevant[anchor_idx + 1 :])


def read_commit_range(anchor_tag: str | None, milestone_tag: str) -> list[CommitInfo]:
    git_range = milestone_tag if anchor_tag is None else f"{anchor_tag}..{milestone_tag}"
    stdout = run_git(
        [
            "log",
            "--no-merges",
            "--pretty=tformat:%H%x09%cI%x09%an%x09%s",
            git_range,
        ],
    )
    commits: list[CommitInfo] = []
    for line in stdout.splitlines():
        if not line:
            continue
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        commits.append(CommitInfo(*parts))
    return commits


def substantive_commits(commits: list[CommitInfo]) -> list[CommitInfo]:
    return [commit for commit in commits if commit.kind == "real"]


def decide_audit(
    *,
    milestone_tag: str,
    anchor_tag: str | None,
    stable_tags: list[StableVersion],
    commits: list[CommitInfo],
) -> AuditDecision:
    milestone = StableVersion.parse(milestone_tag)
    real_commits = substantive_commits(commits)
    stable_release_count = count_stable_releases(stable_tags, anchor_tag, milestone)
    plan_level = classify_upgrade_level(milestone)
    issue_title = f"{plan_level.title()} development plan for {milestone_tag}"

    if plan_level == "daily":
        return AuditDecision(
            action="skip",
            reason="daily_small_upgrade",
            plan_level=plan_level,
            milestone_tag=milestone_tag,
            anchor_tag=anchor_tag,
            stable_release_count=stable_release_count,
            real_commit_count=len(real_commits),
            issue_title=issue_title,
        )
    if not real_commits:
        return AuditDecision(
            action="skip",
            reason="no_substantive_changes_since_anchor",
            plan_level=plan_level,
            milestone_tag=milestone_tag,
            anchor_tag=anchor_tag,
            stable_release_count=stable_release_count,
            real_commit_count=0,
            issue_title=issue_title,
        )
    if plan_level == "architecture":
        return AuditDecision(
            action="architecture-plan",
            reason="integer_version_architecture_upgrade",
            plan_level=plan_level,
            milestone_tag=milestone_tag,
            anchor_tag=anchor_tag,
            stable_release_count=stable_release_count,
            real_commit_count=len(real_commits),
            issue_title=issue_title,
        )
    return AuditDecision(
        action="medium-plan",
        reason="half_version_medium_upgrade",
        plan_level=plan_level,
        milestone_tag=milestone_tag,
        anchor_tag=anchor_tag,
        stable_release_count=stable_release_count,
        real_commit_count=len(real_commits),
        issue_title=issue_title,
    )


def recent_real_commits(commits: list[CommitInfo], limit: int = 20) -> list[dict[str, str]]:
    return [commit.as_dict() for commit in substantive_commits(commits)[:limit]]


def build_manifest(
    *,
    decision: AuditDecision,
    commits: list[CommitInfo],
    head_sha: str,
    previous_audit_issue: str | None,
) -> dict[str, object]:
    release_prep_count = sum(1 for commit in commits if commit.kind == "release-prep")
    real_commits = substantive_commits(commits)
    return {
        "schema": "attestplane_architecture_gap_audit.v1",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "milestone_tag": decision.milestone_tag,
        "anchor_tag": decision.anchor_tag,
        "head_sha": head_sha,
        "previous_audit_issue": previous_audit_issue,
        "action": decision.action,
        "reason": decision.reason,
        "plan_level": decision.plan_level,
        "stable_release_count": decision.stable_release_count,
        "real_commit_count": len(real_commits),
        "release_prep_commit_count": release_prep_count,
        "recent_real_commits": recent_real_commits(commits),
    }


def render_issue_body(manifest: dict[str, object]) -> str:
    milestone_tag = str(manifest["milestone_tag"])
    anchor_tag = manifest.get("anchor_tag") or "repository start"
    plan_level = str(manifest.get("plan_level", "medium"))
    recent = manifest.get("recent_real_commits")
    lines: list[str] = [
        "## Development Plan Request",
        "",
        f"- milestone: `{milestone_tag}`",
        f"- plan_level: `{plan_level}`",
        f"- anchor: `{anchor_tag}`",
        f"- head_sha: `{manifest['head_sha']}`",
        f"- stable releases since anchor: `{manifest['stable_release_count']}`",
        f"- real commits since anchor: `{manifest['real_commit_count']}`",
        f"- release-prep commits since anchor: `{manifest['release_prep_commit_count']}`",
        f"- decision: `{manifest['action']}` / `{manifest['reason']}`",
        "",
        "## Opus Prompt",
        "",
        "Run locally from the repository root after downloading the workflow artifact:",
        "",
        "```bash",
        "ask_opus.sh architect \"$(cat reports/architecture-audits/"
        f"architecture-gap-audit-{milestone_tag}.md)\"",
        "```",
        "",
        "The review should first produce a concise plan, then decompose the",
        "accepted plan into issue-ready P0/P1/P2 sections. Paste the accepted",
        "plan back as a comment on this issue; the `plan-to-issues` workflow",
        f"will convert those sections into GitHub issues with `{TASK_LABEL}` plus",
        "the appropriate priority/module labels. No planned task should be",
        "implemented directly from this planning issue, the Opus output, or",
        "chat. Daily small upgrades stay on the",
        "release train; `x.5.0` milestones should focus on medium product and",
        "architecture gaps; integer `x.0.0` milestones should focus on",
        "architecture-level redesign, compatibility, security boundaries, and",
        "migration risk. Return issue-ready P0/P1/P2 tasks with owners, affected",
        "modules, acceptance criteria, and validation commands. Do not include",
        "secrets, do not move release tags, and do not block already published",
        "packages.",
        "",
        "## Recent Real Commits",
        "",
    ]
    if isinstance(recent, list) and recent:
        for item in recent:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- `{str(item.get('sha', ''))[:12]}` {item.get('time', '')} "
                f"{item.get('subject', '')}",
            )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Issue-First Completion Contract",
            "",
            "1. Run the Opus/maintainer plan review from this issue.",
            "2. Paste the accepted issue-ready plan as a comment on this issue.",
            f"3. Let the `plan-to-issues` workflow create one GitHub issue per accepted P0/P1/P2 task with `{TASK_LABEL}`.",
            "4. Link every generated task issue back here before implementation starts.",
            "5. Close this planning issue with labels "
            f"`{PLAN_LABEL}`, `{AUDIT_LABEL}`, and `{AUDITED_LABEL}` only after",
            "the follow-up issue set is created and the milestone owner accepts the plan.",
            "",
            "## Planned Task Issue Template",
            "",
            "Use this shape for each generated task issue:",
            "",
            "```markdown",
            "Title: [P1][module] Concrete task title",
            "",
            "Source planning issue: #<this issue>",
            "Priority: P0 | P1 | P2",
            "Affected modules:",
            "Acceptance criteria:",
            "Validation commands:",
            "Rollout / migration notes:",
            "```",
            "",
            "Execution rule: work only starts from those generated task issues, one",
            "issue at a time, with validation recorded on the task issue before close.",
        ],
    )
    return "\n".join(lines) + "\n"


def render_auto_architecture_plan(manifest: dict[str, object]) -> str:
    milestone_tag = str(manifest["milestone_tag"])
    anchor_tag = manifest.get("anchor_tag") or "repository start"
    head_sha = str(manifest["head_sha"])
    recent = manifest.get("recent_real_commits")
    recent_lines: list[str] = []
    if isinstance(recent, list):
        for item in recent[:10]:
            if isinstance(item, dict):
                recent_lines.append(f"- `{str(item.get('sha', ''))[:12]}` {item.get('subject', '')}")
    recent_block = "\n".join(recent_lines) if recent_lines else "- none"
    return f"""## Auto-Accepted Architecture Plan

Milestone: `{milestone_tag}`
Anchor: `{anchor_tag}`
Head SHA: `{head_sha}`

This plan was generated and accepted automatically for an integer-version
architecture milestone. It creates planning issues only; implementation still
starts from the generated `planned-task` issues, one issue at a time.

Recent real commits considered:

{recent_block}

**ISSUE 1 · [P0][architecture][compatibility] Define the {milestone_tag} compatibility and migration contract**
- Priority: P0
- Affected modules: SDK public APIs, storage formats, proof bundle schema, verifier behavior, release notes
- Acceptance criteria:
  1. Document backward compatibility guarantees from `{anchor_tag}` to `{milestone_tag}`.
  2. List intentional breaking changes, migration steps, and unsupported historical behavior.
  3. Add or update compatibility fixtures covering the prior audited anchor and `{milestone_tag}`.
  4. Release notes link to the migration contract before any implementation issue closes.
- Validation commands:
  - `sdk/python/.venv/bin/python -m pytest sdk/python/tests -k "compat or proof_bundle or verifier" -x`
  - `npm test --prefix sdk/typescript -- --runInBand`
  - `git diff --check`
- Rollout / migration notes: Do not break existing stable artifacts without a documented migration path.

**ISSUE 2 · [P0][security][boundary] Review architecture-level security and trust boundaries**
- Priority: P0
- Affected modules: signing, anchoring, verifier trust roots, release provenance, SECURITY.md, threat model
- Acceptance criteria:
  1. Identify all trust boundaries affected by the architecture milestone.
  2. Update threat model claims, arguments, and evidence for new or changed boundaries.
  3. Verify signing/provenance workflows remain forward-only and do not expose secrets.
  4. Record any deferred security boundary work as follow-up issues before close.
- Validation commands:
  - `sdk/python/.venv/bin/python -m pytest sdk/python/tests -k "signing or anchoring or trust or provenance" -x`
  - `git diff --check`
- Rollout / migration notes: No secrets in issue bodies, logs, PR descriptions, or commits.

**ISSUE 3 · [P0][release] Prove release rollback and forward-only recovery for {milestone_tag}**
- Priority: P0
- Affected modules: release train, release-cd, sign-release, slsa-provenance, artifact manifests
- Acceptance criteria:
  1. Document safe recovery paths for failed tag publication, failed signing, failed provenance, and registry lag.
  2. Add regression coverage for prepared-but-unpublished major versions.
  3. Confirm the release train never force-pushes, retags, or publishes around failed gates.
  4. Validate npm latest and PyPI latest only advance after release-cd success.
- Validation commands:
  - `sdk/python/.venv/bin/python -m pytest sdk/python/tests -k "stable_auto_train or release_cd" -x`
  - `scripts/check-release-assets-prep.sh`
  - `git diff --check`
- Rollout / migration notes: Treat GitHub/network/registry propagation as external blockers, not reasons to bypass gates.

**ISSUE 4 · [P1][docs][governance] Publish the {milestone_tag} architecture decision record set**
- Priority: P1
- Affected modules: docs/adr, docs/architecture, docs/runbooks, governance docs
- Acceptance criteria:
  1. Add an architecture milestone overview that explains what changed and why.
  2. Link ADRs to generated P0/P1/P2 planned-task issues.
  3. Mark unresolved architectural risks explicitly, with owner issue links.
  4. Keep claim wording within alpha/stable evidence boundaries.
- Validation commands:
  - `markdown-link-check docs/**/*.md`
  - `git diff --check`
- Rollout / migration notes: Documentation can land incrementally, but every architecture claim needs evidence or a gap link.

**ISSUE 5 · [P1][test][conformance] Expand cross-SDK and verifier conformance for {milestone_tag}**
- Priority: P1
- Affected modules: Python SDK, TypeScript SDK, verifier conformance fixtures, cross-SDK roundtrip tests
- Acceptance criteria:
  1. Add conformance vectors that exercise new or changed architecture behavior.
  2. Verify Python and TypeScript SDKs agree on canonical serialization and verification results.
  3. Ensure failing vectors produce stable, documented error codes.
  4. Record unsupported edge cases as planned follow-up issues.
- Validation commands:
  - `sdk/python/.venv/bin/python -m pytest sdk/python/tests -k "conformance or canonical or roundtrip" -x`
  - `npm test --prefix sdk/typescript -- --runInBand`
  - `git diff --check`
- Rollout / migration notes: Conformance expansion should precede feature implementation where practical.
"""


def write_outputs(outputs: dict[str, str]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        for key, value in outputs.items():
            if "\n" in value:
                delimiter = f"EOF_{key}"
                handle.write(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")
            else:
                handle.write(f"{key}={value}\n")


def resolve_anchor(
    explicit_anchor: str | None,
    previous_issue_anchor: str | None,
    tags: list[StableVersion],
    milestone: StableVersion,
) -> str | None:
    if explicit_anchor:
        return explicit_anchor
    if previous_issue_anchor:
        return previous_issue_anchor
    return fallback_anchor_tag(tags, milestone)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--milestone-tag", required=True)
    parser.add_argument("--anchor-tag")
    parser.add_argument("--previous-audit-issue")
    parser.add_argument("--previous-audit-anchor")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/architecture-audits"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        milestone = StableVersion.parse(args.milestone_tag)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    stable_tags = read_stable_tags()
    anchor_tag = resolve_anchor(
        args.anchor_tag,
        args.previous_audit_anchor,
        stable_tags,
        milestone,
    )
    commits = read_commit_range(anchor_tag, milestone.tag)
    decision = decide_audit(
        milestone_tag=milestone.tag,
        anchor_tag=anchor_tag,
        stable_tags=stable_tags,
        commits=commits,
    )
    head_sha = run_git(["rev-list", "-n", "1", milestone.tag])
    manifest = build_manifest(
        decision=decision,
        commits=commits,
        head_sha=head_sha,
        previous_audit_issue=args.previous_audit_issue,
    )

    issue_body = ""
    auto_issue_plan = ""
    if decision.should_upload_artifact:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        stem = f"architecture-gap-audit-{milestone.tag}"
        manifest_path = args.output_dir / f"{stem}.json"
        report_path = args.output_dir / f"{stem}.md"
        auto_plan_path = args.output_dir / f"architecture-task-plan-{milestone.tag}.md"
        issue_body = render_issue_body(manifest)
        if decision.action == "architecture-plan":
            auto_issue_plan = render_auto_architecture_plan(manifest)
            auto_plan_path.write_text(auto_issue_plan, encoding="utf-8")
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        report_path.write_text(issue_body, encoding="utf-8")

    write_outputs(
        {
            "action": decision.action,
            "reason": decision.reason,
            "should_open_issue": str(decision.should_open_issue).lower(),
            "should_upload_artifact": str(decision.should_upload_artifact).lower(),
            "should_auto_accept_plan": str(decision.action == "architecture-plan").lower(),
            "issue_title": decision.issue_title,
            "issue_body": issue_body,
            "auto_issue_plan": auto_issue_plan,
            "upgrade_label": decision.upgrade_label,
            "anchor_tag": anchor_tag or "",
        }
    )

    if args.json:
        print(json.dumps(manifest, indent=2, sort_keys=False))
    else:
        print(f"{decision.action}: {decision.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
