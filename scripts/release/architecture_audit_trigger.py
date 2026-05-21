#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Prepare architecture-gap audit artifacts for stable release milestones.

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
AUDITED_LABEL = "audited"
FULL_AUDIT_MIN_REAL_COMMITS = 5
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
    milestone_tag: str
    anchor_tag: str | None
    stable_release_count: int
    real_commit_count: int
    issue_title: str

    @property
    def should_open_issue(self) -> bool:
        return self.action == "full-audit"

    @property
    def should_upload_artifact(self) -> bool:
        return self.action in {"full-audit", "manifest-only"}


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
    return version.major >= 1 and version.minor > 0 and version.minor % 5 == 0 and version.patch == 0


def is_audit_anchor_release(version: StableVersion) -> bool:
    return version.major >= 1 and version.patch == 0 and version.minor % 5 == 0


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
    issue_title = f"Architecture gap audit for {milestone_tag}"

    if not is_milestone_release(milestone):
        return AuditDecision(
            action="skip",
            reason="not_architecture_audit_milestone",
            milestone_tag=milestone_tag,
            anchor_tag=anchor_tag,
            stable_release_count=stable_release_count,
            real_commit_count=len(real_commits),
            issue_title=issue_title,
        )
    if stable_release_count < MILESTONE_STABLE_RELEASES:
        return AuditDecision(
            action="skip",
            reason="stable_release_count_below_50",
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
            milestone_tag=milestone_tag,
            anchor_tag=anchor_tag,
            stable_release_count=stable_release_count,
            real_commit_count=0,
            issue_title=issue_title,
        )
    if len(real_commits) < FULL_AUDIT_MIN_REAL_COMMITS:
        return AuditDecision(
            action="manifest-only",
            reason="substantive_changes_below_full_audit_threshold",
            milestone_tag=milestone_tag,
            anchor_tag=anchor_tag,
            stable_release_count=stable_release_count,
            real_commit_count=len(real_commits),
            issue_title=issue_title,
        )
    return AuditDecision(
        action="full-audit",
        reason="milestone_and_substantive_changes",
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
        "stable_release_count": decision.stable_release_count,
        "real_commit_count": len(real_commits),
        "release_prep_commit_count": release_prep_count,
        "recent_real_commits": recent_real_commits(commits),
    }


def render_issue_body(manifest: dict[str, object]) -> str:
    milestone_tag = str(manifest["milestone_tag"])
    anchor_tag = manifest.get("anchor_tag") or "repository start"
    recent = manifest.get("recent_real_commits")
    lines: list[str] = [
        "## Architecture Gap Audit Request",
        "",
        f"- milestone: `{milestone_tag}`",
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
        "The review should identify architecture and product-functionality gaps",
        "introduced or revealed over this 50-stable-release window. Return P0/P1/P2",
        "items, concrete affected modules, and validation or migration work needed",
        "before the next milestone. Do not include secrets, do not move release",
        "tags, and do not block already published packages.",
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
            "## Completion Contract",
            "",
            f"Close this issue and keep labels `{AUDIT_LABEL}` + `{AUDITED_LABEL}`",
            "after the Opus/maintainer audit has produced accepted follow-up work.",
        ],
    )
    return "\n".join(lines) + "\n"


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
    if decision.should_upload_artifact:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        stem = f"architecture-gap-audit-{milestone.tag}"
        manifest_path = args.output_dir / f"{stem}.json"
        report_path = args.output_dir / f"{stem}.md"
        issue_body = render_issue_body(manifest)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        report_path.write_text(issue_body, encoding="utf-8")

    write_outputs(
        {
            "action": decision.action,
            "reason": decision.reason,
            "should_open_issue": str(decision.should_open_issue).lower(),
            "should_upload_artifact": str(decision.should_upload_artifact).lower(),
            "issue_title": decision.issue_title,
            "issue_body": issue_body,
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
