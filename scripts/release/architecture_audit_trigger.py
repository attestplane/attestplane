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
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

if str(Path(__file__).resolve().parents[2]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.release.plan_schema import PlanIssue, append_plan_block, with_plan_id  # noqa: E402

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
OPEN_ISSUE_CONTEXT_LIMIT = 100
OPUS_PLAN_COMMAND_ENV = "ATTESTPLANE_OPUS_PLAN_COMMAND"
OPUS_PLAN_FAKE_RESPONSE_ENV = "ATTESTPLANE_OPUS_PLAN_FAKE_RESPONSE"
OPUS_PLAN_TIMEOUT_ENV = "ATTESTPLANE_OPUS_PLAN_TIMEOUT_SECONDS"
DEFAULT_OPUS_PLAN_TIMEOUT_SECONDS = 180
ISSUE_READY_PLAN_RE = re.compile(
    r"(?im)^\s*(?:#+\s*)?(?:\*\*)?\s*ISSUE\s+\d+\s*[.:·-]\s*\[P[0-2]\]"
)
PRODUCT_DELTA_KEYWORDS = (
    "sdk",
    "python sdk",
    "typescript sdk",
    "verifier",
    "verification",
    "proof bundle",
    "proof-bundle",
    "canonical",
    "canonicalization",
    "conformance",
    "signature",
    "signing",
    "anchoring",
    "attestation",
    "evidence",
    "public api",
    "api contract",
    "cli",
    "schema",
    "roundtrip",
    "trust boundary",
)
SUPPORT_ONLY_ISSUE_KEYWORDS = (
    "release train",
    "release-cd",
    "sign-release",
    "slsa-provenance",
    "github actions",
    "workflow",
    "runner",
    "pypi",
    "npm",
    "dist-tag",
    "observability",
    "telemetry",
    "docs",
    "release notes",
)


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
        return self.action in {"daily-plan", "medium-plan", "architecture-plan"}

    @property
    def should_upload_artifact(self) -> bool:
        return self.action in {
            "daily-plan",
            "medium-plan",
            "architecture-plan",
            "manifest-only",
        }

    @property
    def upgrade_label(self) -> str:
        if self.plan_level == "architecture":
            return ARCHITECTURE_UPGRADE_LABEL
        if self.plan_level == "medium":
            return MEDIUM_UPGRADE_LABEL
        return "upgrade-daily"


@dataclass(frozen=True)
class AcceptedPlan:
    body: str
    source: str
    fallback_reason: str = ""


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
    return stable_tag_versions(
        [line.strip() for line in stdout.splitlines() if line.strip()]
    )


def is_milestone_release(version: StableVersion) -> bool:
    return classify_upgrade_level(version) in {"medium", "architecture"}


def is_audit_anchor_release(version: StableVersion) -> bool:
    return version.major >= 1 and version.patch == 0 and version.minor % 5 == 0


def classify_upgrade_level(version: StableVersion) -> str:
    if version.major >= 1 and version.minor == 0 and version.patch == 0:
        return "architecture"
    if (
        version.major >= 1
        and version.minor > 0
        and version.minor % 5 == 0
        and version.patch == 0
    ):
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


def fallback_anchor_tag(
    tags: list[StableVersion], milestone: StableVersion
) -> str | None:
    older = [version for version in tags if version < milestone]
    if not older:
        return None
    anchor_boundaries = [
        version for version in older if is_audit_anchor_release(version)
    ]
    if anchor_boundaries:
        return anchor_boundaries[-1].tag
    if len(older) >= MILESTONE_STABLE_RELEASES:
        return older[-MILESTONE_STABLE_RELEASES].tag
    return older[0].tag


def count_stable_releases(
    tags: list[StableVersion], anchor_tag: str | None, milestone: StableVersion
) -> int:
    relevant = [version for version in tags if version <= milestone]
    if anchor_tag is None:
        return len(relevant)
    anchor_idx = tag_index(relevant, anchor_tag)
    if anchor_idx is None:
        return len(relevant)
    return len(relevant[anchor_idx + 1 :])


def read_commit_range(anchor_tag: str | None, milestone_tag: str) -> list[CommitInfo]:
    git_range = (
        milestone_tag if anchor_tag is None else f"{anchor_tag}..{milestone_tag}"
    )
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
        if not real_commits:
            return AuditDecision(
                action="skip",
                reason="daily_small_upgrade",
                plan_level=plan_level,
                milestone_tag=milestone_tag,
                anchor_tag=anchor_tag,
                stable_release_count=stable_release_count,
                real_commit_count=0,
                issue_title=issue_title,
            )
        return AuditDecision(
            action="daily-plan",
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


def recent_real_commits(
    commits: list[CommitInfo], limit: int = 20
) -> list[dict[str, str]]:
    return [commit.as_dict() for commit in substantive_commits(commits)[:limit]]


def load_open_issues(path: Path | None) -> list[dict[str, object]]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("open issues payload must be a JSON list")
    issues: list[dict[str, object]] = []
    for item in payload[:OPEN_ISSUE_CONTEXT_LIMIT]:
        if not isinstance(item, dict):
            continue
        raw_labels = item.get("labels", [])
        labels: list[str] = []
        if isinstance(raw_labels, list):
            for label in raw_labels:
                if isinstance(label, dict) and isinstance(label.get("name"), str):
                    labels.append(label["name"])
                elif isinstance(label, str):
                    labels.append(label)
        number = item.get("number")
        title = item.get("title")
        if not isinstance(number, int) or not isinstance(title, str):
            continue
        issue: dict[str, object] = {
            "number": number,
            "title": title,
            "labels": labels,
        }
        for key in ("url", "updatedAt"):
            value = item.get(key)
            if isinstance(value, str):
                issue[key] = value
        issues.append(issue)
    return issues


def render_open_issues_block(open_issues: object, *, limit: int = 30) -> str:
    if not isinstance(open_issues, list) or not open_issues:
        return "- none"
    lines: list[str] = []

    def issue_context_sort_key(indexed_item: tuple[int, object]) -> tuple[int, int]:
        index, item = indexed_item
        if not isinstance(item, dict):
            return (3, index)
        text_parts = [str(item.get("title", ""))]
        labels = item.get("labels", [])
        if isinstance(labels, list):
            text_parts.extend(str(label) for label in labels if isinstance(label, str))
        issue_text = " ".join(text_parts).lower()
        if plan_has_product_delta(issue_text):
            return (0, index)
        if any(keyword in issue_text for keyword in SUPPORT_ONLY_ISSUE_KEYWORDS):
            return (2, index)
        return (1, index)

    ranked_issues = [
        item for _, item in sorted(enumerate(open_issues), key=issue_context_sort_key)
    ]
    for item in ranked_issues[:limit]:
        if not isinstance(item, dict):
            continue
        number = item.get("number")
        title = item.get("title")
        labels = item.get("labels", [])
        if not isinstance(number, int) or not isinstance(title, str):
            continue
        label_text = ""
        if isinstance(labels, list) and labels:
            label_names = [label for label in labels if isinstance(label, str)]
            if label_names:
                label_text = f" [{', '.join(label_names)}]"
        lines.append(f"- #{number} {title}{label_text}")
    return "\n".join(lines) if lines else "- none"


def issue_ready_plan(text: str) -> bool:
    return bool(ISSUE_READY_PLAN_RE.search(text))


def plan_has_product_delta(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in PRODUCT_DELTA_KEYWORDS)


def fallback_plan(manifest: dict[str, object], reason: str) -> AcceptedPlan:
    return AcceptedPlan(
        body=render_fallback_notice(reason) + render_auto_plan(manifest),
        source="deterministic-template",
        fallback_reason=reason,
    )


def build_opus_plan_prompt(manifest: dict[str, object], issue_body: str) -> str:
    plan_level = str(manifest.get("plan_level", "daily"))
    consultation_level = consultation_level_for(plan_level)
    return "\n".join(
        [
            f"Attestplane stable autodev {plan_level} development planning.",
            "",
            f"Consultation level: {consultation_level}",
            "Goal: generate the accepted development plan for this milestone.",
            "",
            "Return Markdown only. Include 1-5 issue-ready sections. Each section must start exactly like:",
            "",
            "**ISSUE 1 · [P1][module] Concrete task title**",
            "",
            "For every issue include:",
            "- Priority: P0 | P1 | P2",
            "- Affected modules:",
            "- Acceptance criteria:",
            "- Validation commands:",
            "- Rollout / migration notes:",
            "",
            "Rules:",
            "- Consider all open GitHub issues in the request.",
            "- Avoid duplicate planned-task issues; extend or reference existing issues when overlapping.",
            "- Do not include secrets.",
            "- Do not move tags, publish packages, merge PRs, or bypass release gates.",
            "- Product increment is mandatory for daily, medium, and architecture plans.",
            "- At least one P0/P1 issue must touch an Attestplane product module: SDK public APIs, verifier behavior, proof bundle schema/fixtures, canonicalization, conformance vectors, signing/anchoring, or CLI behavior.",
            "- Release train, CI, runner, docs, observability, and package metadata tasks may appear only as support tasks or when the request shows an active blocker.",
            "- Do not return a plan consisting only of release-boundary, docs, observability, workflow, or registry tasks.",
            "- If open issues are release/docs-only, still generate or extend at least one product implementation or conformance task.",
            "",
            issue_body,
        ]
    )


def render_fallback_notice(reason: str) -> str:
    return "\n".join(
        [
            "> Plan source: deterministic-template",
            f"> Opus consultation fallback reason: {reason}",
            "",
        ]
    )


def normalize_opus_plan(raw_output: str) -> str:
    return raw_output.strip() + "\n"


def consult_opus_for_plan(
    manifest: dict[str, object],
    issue_body: str,
    *,
    command: str | None = None,
    timeout_seconds: int = DEFAULT_OPUS_PLAN_TIMEOUT_SECONDS,
) -> AcceptedPlan:
    fake = os.environ.get(OPUS_PLAN_FAKE_RESPONSE_ENV)
    if fake is not None:
        plan = normalize_opus_plan(fake)
        if issue_ready_plan(plan):
            if not plan_has_product_delta(plan):
                return fallback_plan(manifest, "fake_response_without_product_delta")
            return AcceptedPlan(
                body=f"> Plan source: opus-fake-response\n\n{plan}",
                source="opus-fake-response",
            )
        return fallback_plan(manifest, "fake_response_not_issue_ready")

    resolved_command = command or os.environ.get(OPUS_PLAN_COMMAND_ENV, "").strip()
    if not resolved_command:
        return fallback_plan(manifest, "opus_command_not_configured")

    try:
        argv = shlex.split(resolved_command)
    except ValueError:
        return fallback_plan(manifest, "opus_command_invalid")
    if not argv:
        return fallback_plan(manifest, "opus_command_empty")

    prompt = build_opus_plan_prompt(manifest, issue_body)
    try:
        completed = subprocess.run(
            [*argv, prompt],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return fallback_plan(manifest, "opus_timeout")
    except FileNotFoundError:
        return fallback_plan(manifest, "opus_command_not_found")

    if completed.returncode != 0:
        return fallback_plan(manifest, f"opus_failed_rc_{completed.returncode}")

    plan = normalize_opus_plan(completed.stdout)
    if not issue_ready_plan(plan):
        return fallback_plan(manifest, "opus_output_not_issue_ready")
    if not plan_has_product_delta(plan):
        return fallback_plan(manifest, "opus_output_without_product_delta")
    return AcceptedPlan(body=f"> Plan source: opus-live\n\n{plan}", source="opus-live")


def build_manifest(
    *,
    decision: AuditDecision,
    commits: list[CommitInfo],
    head_sha: str,
    previous_audit_issue: str | None,
    open_issues: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    release_prep_count = sum(1 for commit in commits if commit.kind == "release-prep")
    real_commits = substantive_commits(commits)
    issue_context = open_issues or []
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
        "open_issue_count": len(issue_context),
        "open_issues": issue_context,
    }


def consultation_level_for(plan_level: str) -> str:
    if plan_level == "architecture":
        return "architecture"
    if plan_level == "medium":
        return "feature"
    return "diff"


def build_plan_payload(manifest: dict[str, object]) -> dict[str, object]:
    milestone_tag = str(manifest["milestone_tag"])
    anchor_tag = manifest.get("anchor_tag") or "repository start"
    plan_level = str(manifest.get("plan_level", "daily"))
    issue_specs: list[PlanIssue]

    if plan_level == "daily":
        issue_specs = [
            PlanIssue(
                ordinal=1,
                title=f"[P1][sdk][verifier] Add a verifier-facing product increment for {milestone_tag}",
                priority="P1",
                modules=(
                    "Python SDK verifier",
                    "TypeScript SDK verifier",
                    "proof bundle fixtures",
                ),
                acceptance_criteria=(
                    "Implement one small verifier or proof-bundle behavior that is visible to SDK users.",
                    "Keep the change backward compatible with the current stable proof bundle contract.",
                    "Record the product-facing behavior and validation evidence on the task issue before close.",
                ),
                validation_commands=(
                    "sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'verifier or proof_bundle or conformance' -x",
                    "npm test --prefix sdk/typescript -- --runInBand",
                    "git diff --check",
                ),
                rollout_notes="Daily work should land a real Attestplane product delta before any release-train-only task.",
            ),
            PlanIssue(
                ordinal=2,
                title="[P1][test][conformance] Pin cross-SDK coverage for the daily product change",
                priority="P1",
                modules=(
                    "Python SDK tests",
                    "TypeScript SDK tests",
                    "conformance fixtures",
                ),
                acceptance_criteria=(
                    "Add or update conformance coverage for the product behavior from issue 1.",
                    "Confirm Python and TypeScript validation expectations stay aligned.",
                    "Record the validation evidence on the task issue before close.",
                ),
                validation_commands=(
                    "sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'conformance or canonical or roundtrip' -x",
                    "npm test --prefix sdk/typescript -- --runInBand",
                    "git diff --check",
                ),
                rollout_notes="Coverage must follow the product change, not release metadata churn.",
            ),
            PlanIssue(
                ordinal=3,
                title=f"[P2][docs][api] Document the user-visible product delta for {milestone_tag}",
                priority="P2",
                modules=("docs", "SDK API docs", "release notes"),
                acceptance_criteria=(
                    "Document the verifier or proof-bundle behavior added by issue 1.",
                    "Link the documentation to the source planning issue and task issues.",
                    "Keep wording within claim boundaries and avoid secrets.",
                ),
                validation_commands=("git diff --check",),
                rollout_notes="Docs-only work cannot satisfy the daily plan unless issue 1 lands a product change.",
            ),
        ]
    elif plan_level == "medium":
        issue_specs = [
            PlanIssue(
                ordinal=1,
                title=f"[P0][sdk][api] Define the {milestone_tag} feature-level product contract",
                priority="P0",
                modules=(
                    "SDK public APIs",
                    "verifier behavior",
                    "proof bundle schema",
                    "CLI behavior",
                ),
                acceptance_criteria=(
                    f"Document the intended Attestplane product capability for {milestone_tag}.",
                    "Define compatibility expectations for SDK, verifier, proof bundle, and CLI users.",
                    "Link the plan back to the source planning issue before implementation starts.",
                ),
                validation_commands=("git diff --check",),
                rollout_notes="The feature boundary must describe product behavior, not release automation housekeeping.",
            ),
            PlanIssue(
                ordinal=2,
                title="[P1][verifier][proof-bundle] Implement the feature-sized verifier/proof-bundle increment",
                priority="P1",
                modules=(
                    "Python SDK verifier",
                    "TypeScript SDK verifier",
                    "proof bundle schema",
                    "fixtures",
                ),
                acceptance_criteria=(
                    "Implement the product contract from issue 1 in a compatibility-safe way.",
                    "Add or update proof bundle fixtures that exercise the new behavior.",
                    "Record unresolved compatibility gaps as explicit follow-up issues.",
                ),
                validation_commands=(
                    "sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'compat or conformance or verifier' -x",
                    "npm test --prefix sdk/typescript -- --runInBand",
                    "git diff --check",
                ),
                rollout_notes="Prefer incremental product work over broad rewrites or release-only cleanup.",
            ),
            PlanIssue(
                ordinal=3,
                title="[P1][test][conformance] Pin Python and TypeScript conformance vectors",
                priority="P1",
                modules=(
                    "Python SDK tests",
                    "TypeScript SDK tests",
                    "conformance vectors",
                ),
                acceptance_criteria=(
                    "Add cross-SDK vectors for the feature behavior implemented in issue 2.",
                    "Verify canonical serialization and verification results match across SDKs.",
                    "Document unsupported edge cases as planned follow-up issues.",
                ),
                validation_commands=(
                    "sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'conformance or canonical or roundtrip' -x",
                    "npm test --prefix sdk/typescript -- --runInBand",
                    "git diff --check",
                ),
                rollout_notes="Conformance evidence is required before treating the feature plan as complete.",
            ),
            PlanIssue(
                ordinal=4,
                title=f"[P2][docs][runbook] Document migration and SDK usage for {milestone_tag}",
                priority="P1",
                modules=("docs", "SDK API docs", "release notes", "runbooks"),
                acceptance_criteria=(
                    "Summarize the feature-level product delta and migration notes.",
                    "Link the documentation to the accepted plan and generated task issues.",
                    "Keep claim wording within documented evidence boundaries.",
                ),
                validation_commands=(
                    "git diff --check",
                    "markdown-link-check docs/**/*.md",
                ),
                rollout_notes="Documentation supports the product increment; it is not the primary medium task.",
            ),
        ]
    else:
        issue_specs = [
            PlanIssue(
                ordinal=1,
                title=f"[P0][architecture][product-contract] Define the {milestone_tag} Attestplane product contract",
                priority="P0",
                modules=(
                    "SDK public APIs",
                    "verifier behavior",
                    "proof bundle schema",
                    "canonicalization",
                    "CLI behavior",
                ),
                acceptance_criteria=(
                    f"Define the architecture-level product capability from {anchor_tag} to {milestone_tag}.",
                    "Document compatibility guarantees for SDK APIs, proof bundles, canonicalization, and verifier behavior.",
                    "List intentional breaking changes, migration steps, and unsupported historical behavior.",
                    "Link the contract to generated P0/P1/P2 planned-task issues before implementation starts.",
                ),
                validation_commands=("git diff --check",),
                rollout_notes="Architecture plans must start from Attestplane product behavior, not train/release maintenance.",
            ),
            PlanIssue(
                ordinal=2,
                title="[P0][sdk][schema] Implement compatibility-safe proof-bundle and SDK schema migration",
                priority="P0",
                modules=(
                    "Python SDK",
                    "TypeScript SDK",
                    "proof bundle schema",
                    "canonical serialization",
                ),
                acceptance_criteria=(
                    "Implement the schema or canonicalization migration described by issue 1.",
                    "Preserve verification of existing stable proof bundles unless issue 1 documents a migration path.",
                    "Add fixtures that cover the prior audited anchor and the new milestone behavior.",
                    "Record unresolved compatibility gaps as planned follow-up issues.",
                ),
                validation_commands=(
                    "sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'compat or proof_bundle or verifier or canonical' -x",
                    "npm test --prefix sdk/typescript -- --runInBand",
                    "git diff --check",
                ),
                rollout_notes="Do not break existing stable artifacts without a documented migration path.",
            ),
            PlanIssue(
                ordinal=3,
                title="[P0][security][verifier] Review product trust boundaries for verifier, signing, and anchoring",
                priority="P0",
                modules=(
                    "verifier trust roots",
                    "signing",
                    "anchoring",
                    "attestation evidence",
                    "SECURITY.md",
                ),
                acceptance_criteria=(
                    "Identify all product trust boundaries affected by the architecture milestone.",
                    "Update threat model claims, arguments, and evidence for new or changed boundaries.",
                    "Verify signing and anchoring behavior remains forward-only and does not expose secrets.",
                    "Record any deferred security boundary work as follow-up issues before close.",
                ),
                validation_commands=(
                    "sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'signing or anchoring or trust or provenance or verifier' -x",
                    "git diff --check",
                ),
                rollout_notes="No secrets in issue bodies, logs, PR descriptions, or commits.",
            ),
            PlanIssue(
                ordinal=4,
                title=f"[P1][test][conformance] Expand cross-SDK and verifier conformance for {milestone_tag}",
                priority="P1",
                modules=(
                    "Python SDK",
                    "TypeScript SDK",
                    "verifier conformance fixtures",
                    "cross-SDK roundtrip tests",
                ),
                acceptance_criteria=(
                    "Add conformance vectors that exercise new or changed architecture behavior.",
                    "Verify Python and TypeScript SDKs agree on canonical serialization and verification results.",
                    "Ensure failing vectors produce stable, documented error codes.",
                    "Record unsupported edge cases as planned follow-up issues.",
                ),
                validation_commands=(
                    "sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'conformance or canonical or roundtrip' -x",
                    "npm test --prefix sdk/typescript -- --runInBand",
                    "git diff --check",
                ),
                rollout_notes="Conformance expansion should precede release-train or docs-only architecture work.",
            ),
            PlanIssue(
                ordinal=5,
                title=f"[P2][docs][adr] Publish the {milestone_tag} product architecture ADR and migration docs",
                priority="P2",
                modules=(
                    "docs/adr",
                    "docs/architecture",
                    "docs/runbooks",
                    "SDK API docs",
                ),
                acceptance_criteria=(
                    "Add an architecture milestone overview that explains the product contract and migration path.",
                    "Link ADRs to generated P0/P1/P2 planned-task issues.",
                    "Mark unresolved architectural risks explicitly, with owner issue links.",
                    "Keep claim wording within alpha/stable evidence boundaries.",
                ),
                validation_commands=(
                    "markdown-link-check docs/**/*.md",
                    "git diff --check",
                ),
                rollout_notes="Documentation supports product architecture decisions and cannot replace product implementation tasks.",
            ),
        ]

    return {
        "schema": "attestplane.plan.v1",
        "schema_version": 1,
        "milestone_tag": milestone_tag,
        "anchor_tag": anchor_tag,
        "head_sha": str(manifest["head_sha"]),
        "plan_level": plan_level,
        "consultation_level": consultation_level_for(plan_level),
        "recent_real_commits": manifest.get("recent_real_commits", []),
        "open_issues": manifest.get("open_issues", []),
        "issues": [issue.as_dict() for issue in issue_specs],
    }


def render_issue_body(manifest: dict[str, object]) -> str:
    milestone_tag = str(manifest["milestone_tag"])
    anchor_tag = manifest.get("anchor_tag") or "repository start"
    plan_level = str(manifest.get("plan_level", "medium"))
    recent = manifest.get("recent_real_commits")
    open_issues_block = render_open_issues_block(manifest.get("open_issues"))
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
        'ask_opus.sh architect "$(cat reports/architecture-audits/'
        f'architecture-gap-audit-{milestone_tag}.md)"',
        "```",
        "",
        "The review should first produce a concise plan, then decompose the",
        "plan into issue-ready P0/P1/P2 sections. The workflow posts that plan",
        "back as a comment on this issue. Opus-authored plans are parsed",
        "directly from their issue-ready Markdown; deterministic fallback plans",
        "also include a structured `ATT_PLAN_SCHEMA_V1` block. The",
        "`plan-to-issues` workflow converts",
        f"those sections into GitHub issues with `{TASK_LABEL}` plus the",
        "appropriate priority/module labels. No planned task should be",
        "implemented directly from this planning issue, the Opus output, or",
        "chat. Daily small upgrades stay on a diff-level plan; `x.5.0`",
        "milestones should focus on medium product gaps; integer `x.0.0`",
        "milestones should focus on architecture-level redesign, compatibility,",
        "security boundaries, and migration risk. Return issue-ready P0/P1/P2",
        "tasks with owners, affected modules, acceptance criteria, and",
        "validation commands. Do not include secrets, do not move release tags,",
        "and do not block already published packages.",
        "",
        "Product increment is mandatory: every accepted daily, medium, or",
        "architecture plan must include at least one P0/P1 task that changes",
        "Attestplane SDK, verifier, proof-bundle, canonicalization, conformance,",
        "signing, anchoring, CLI, or API behavior. Release train, CI, runner,",
        "docs, observability, and package metadata tasks are support work only",
        "unless the request shows an active blocker.",
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
            "## Current Open GitHub Issues",
            "",
            "The plan must consider all currently open issues, not only tasks generated",
            "from this milestone. Avoid duplicating open work; extend or reference",
            "existing issues when the new plan overlaps.",
            "",
            open_issues_block,
            "",
            "## Issue-First Completion Contract",
            "",
            "1. Run the Opus consultation for the milestone-level plan.",
            "2. Post the generated issue-ready plan as a comment on this issue.",
            f"3. Let the `plan-to-issues` workflow create one GitHub issue per accepted P0/P1/P2 task with `{TASK_LABEL}`.",
            "4. Link every generated task issue back here before implementation starts.",
            "5. Keep the planning issue open as the source of truth until the task",
            "   set is created and the milestone owner accepts the plan.",
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


def render_auto_plan(manifest: dict[str, object]) -> str:
    milestone_tag = str(manifest["milestone_tag"])
    anchor_tag = manifest.get("anchor_tag") or "repository start"
    head_sha = str(manifest["head_sha"])
    plan_level = str(manifest.get("plan_level", "daily"))
    consultation_level = consultation_level_for(plan_level)
    recent = manifest.get("recent_real_commits")
    open_issues_block = render_open_issues_block(manifest.get("open_issues"), limit=20)
    recent_lines: list[str] = []
    if isinstance(recent, list):
        for item in recent[:10]:
            if isinstance(item, dict):
                recent_lines.append(
                    f"- `{str(item.get('sha', ''))[:12]}` {item.get('subject', '')}"
                )
    recent_block = "\n".join(recent_lines) if recent_lines else "- none"
    title_level = {
        "daily": "Daily",
        "medium": "Medium",
        "architecture": "Architecture",
    }.get(plan_level, "Daily")
    payload = build_plan_payload(manifest)
    lines = [
        f"## Auto-Generated {title_level} Plan",
        "",
        f"Milestone: `{milestone_tag}`",
        f"Anchor: `{anchor_tag}`",
        f"Head SHA: `{head_sha}`",
        "",
        f"This plan was generated after a {consultation_level}-level Opus consultation. It creates",
        "planning issues only; implementation still starts from the generated",
        "`planned-task` issues, one issue at a time.",
        "",
        "Product increment policy: at least one P0/P1 task must change Attestplane",
        "SDK, verifier, proof-bundle, canonicalization, conformance, signing,",
        "anchoring, CLI, or API behavior. Release/train/docs-only work is support",
        "work and cannot satisfy this plan by itself.",
        "",
        "Recent real commits considered:",
        "",
        recent_block,
        "",
        "Open GitHub issues considered:",
        "",
        open_issues_block,
        "",
    ]
    issues = payload.get("issues", [])
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        lines.append(f"**ISSUE {issue.get('ordinal')} · {issue.get('title', '')}**")
        lines.append(f"- Priority: {issue.get('priority', 'P2')}")
        modules = issue.get("modules", [])
        if isinstance(modules, list):
            lines.append(
                f"- Affected modules: {', '.join(str(module) for module in modules)}"
            )
        else:
            lines.append("- Affected modules:")
        lines.append("- Acceptance criteria:")
        for index, criterion in enumerate(
            issue.get("acceptance_criteria", []), start=1
        ):
            lines.append(f"  {index}. {criterion}")
        lines.append("- Validation commands:")
        for command in issue.get("validation_commands", []):
            lines.append(f"  - `{command}`")
        lines.append(f"- Rollout / migration notes: {issue.get('rollout_notes', '')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_auto_architecture_plan(manifest: dict[str, object]) -> str:
    return render_auto_plan(manifest)


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
    parser.add_argument("--open-issues-file", type=Path)
    parser.add_argument(
        "--opus-plan-command",
        help="Optional local command prefix used to generate the accepted plan. The prompt is appended as the final argument.",
    )
    parser.add_argument(
        "--opus-timeout-seconds",
        type=int,
        default=int(
            os.environ.get(
                OPUS_PLAN_TIMEOUT_ENV, str(DEFAULT_OPUS_PLAN_TIMEOUT_SECONDS)
            )
        ),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("reports/architecture-audits")
    )
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
    open_issues = load_open_issues(args.open_issues_file)
    manifest = build_manifest(
        decision=decision,
        commits=commits,
        head_sha=head_sha,
        previous_audit_issue=args.previous_audit_issue,
        open_issues=open_issues,
    )

    issue_body = ""
    auto_issue_plan = ""
    plan_payload: dict[str, object] = {}
    accepted_plan = AcceptedPlan(body="", source="", fallback_reason="")
    if decision.should_upload_artifact:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        stem = f"architecture-gap-audit-{milestone.tag}"
        manifest_path = args.output_dir / f"{stem}.json"
        report_path = args.output_dir / f"{stem}.md"
        auto_plan_path = args.output_dir / f"architecture-task-plan-{milestone.tag}.md"
        issue_body = render_issue_body(manifest)
        if decision.should_open_issue:
            plan_payload = with_plan_id(build_plan_payload(manifest))
            accepted_plan = consult_opus_for_plan(
                manifest,
                issue_body,
                command=args.opus_plan_command,
                timeout_seconds=args.opus_timeout_seconds,
            )
            if accepted_plan.source == "deterministic-template":
                auto_issue_plan = append_plan_block(accepted_plan.body, plan_payload)
            else:
                auto_issue_plan = accepted_plan.body
            auto_plan_path.write_text(auto_issue_plan, encoding="utf-8")
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8"
        )
        report_path.write_text(issue_body, encoding="utf-8")

    write_outputs(
        {
            "action": decision.action,
            "reason": decision.reason,
            "consultation_level": consultation_level_for(decision.plan_level),
            "should_open_issue": str(decision.should_open_issue).lower(),
            "should_upload_artifact": str(decision.should_upload_artifact).lower(),
            "issue_title": decision.issue_title,
            "issue_body": issue_body,
            "auto_issue_plan": auto_issue_plan,
            "plan_id": str(plan_payload.get("plan_id", "")),
            "plan_source": accepted_plan.source,
            "plan_fallback_reason": accepted_plan.fallback_reason,
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
