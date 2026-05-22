#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed safety review for Codex-generated diffs."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

SECRET_RE = re.compile(
    r"(ghp_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9]{12,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)",
    re.S,
)
CODEX_REVIEW_STATUS_RE = re.compile(r"^\s*Status:\s*\*\*(?P<status>PASS|WARN|FAIL)\*\*\s*$", re.M | re.I)


@dataclass(frozen=True)
class ReviewGuardReport:
    status: str
    blocking_reasons: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def run_review_guard(
    *,
    diff: str,
    codex_review_report: str,
    issue_labels: list[str],
    changed_files: list[str],
    evidence_dir: Path,
) -> ReviewGuardReport:
    blocking: list[str] = []
    warnings: list[str] = []
    labels = set(issue_labels)
    lowered_diff = diff.lower()

    if SECRET_RE.search(diff):
        blocking.append("Potential secret/private key/token material appears in diff")
    if re.search(r"[-].*release_blocking:\s*true[\s\S]{0,300}[+].*release_blocking:\s*false", lowered_diff):
        blocking.append("release_blocking appears to be weakened from true to false")
    if re.search(r"[-].*required:\s*true[\s\S]{0,300}[+].*required:\s*false", lowered_diff):
        blocking.append("required gate appears to be weakened from true to false")
    if re.search(r"[-].*severity:\s*p[01][\s\S]{0,300}[+].*severity:\s*p[2-9]", lowered_diff):
        blocking.append("P0/P1 severity appears to be downgraded")
    added_skip_lines = [
        line
        for line in diff.splitlines()
        if line.startswith("+") and re.search(r"(pytest\.mark\.)?(skip|xfail)\b", line)
    ]
    if added_skip_lines:
        warnings.append("New skip/xfail marker detected; verify it is not masking the issue")
    if len(added_skip_lines) >= 3:
        blocking.append("Multiple new skip/xfail markers detected")
    if has_test_deletion(diff):
        blocking.append("Test deletion detected")

    publish_files = [path for path in changed_files if path.startswith(".github/workflows/publish")]
    if publish_files and "publish-workflow-approved" not in labels:
        blocking.append(f"Publish workflow modified without publish-workflow-approved: {', '.join(publish_files)}")
    release_files = [
        path
        for path in changed_files
        if "release" in path.lower() and (path.startswith("scripts/") or path.startswith(".github/workflows/"))
    ]
    if release_files and "release-workflow-approved" not in labels:
        blocking.append(f"Release/tag script modified without release-workflow-approved: {', '.join(release_files)}")
    if (
        "claim-safety" in labels
        or "severity:P0" in labels
        or "P0" in labels
    ) and not has_test_or_evidence_change(changed_files):
        blocking.append("claim-safety/P0 issue lacks test or evidence changes")
    if codex_review_status(codex_review_report) == "FAIL":
        blocking.append("Codex self-review reported a blocking failure")

    report = ReviewGuardReport(
        status="FAIL" if blocking else ("WARN" if warnings else "PASS"),
        blocking_reasons=blocking,
        warnings=warnings,
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "review_guard_report.json").write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (evidence_dir / "review_guard_report.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def has_test_or_evidence_change(paths: list[str]) -> bool:
    return any(path.startswith("tests/") or path.startswith("docs/validation/") for path in paths)


def has_test_deletion(diff: str) -> bool:
    removed_tests = 0
    added_tests = 0
    for line in diff.splitlines():
        if line.startswith("diff --git ") or line.startswith("--- ") or line.startswith("+++ "):
            continue
        if not line.startswith(("-", "+")):
            continue
        body = line[1:].lstrip()
        if body.startswith(("#", "//", "/*", "*")):
            continue
        if re.search(r"^(def\s+test_|(?:it|test)\s*\()", body):
            if line.startswith("-"):
                removed_tests += 1
            else:
                added_tests += 1
    return removed_tests > added_tests


def codex_review_status(report: str) -> str | None:
    for line in report.splitlines():
        stripped = line.strip()
        if stripped in {"PASS", "WARN", "FAIL"}:
            return stripped
    match = CODEX_REVIEW_STATUS_RE.search(report)
    if match:
        return match.group("status").upper()
    return None


def render_markdown(report: ReviewGuardReport) -> str:
    lines = [f"# Review Guard: {report.status}", ""]
    lines.append("## Blocking Reasons")
    lines.append("")
    lines.extend(f"- {item}" for item in report.blocking_reasons) if report.blocking_reasons else lines.append("- None")
    lines.append("")
    lines.append("## Warnings")
    lines.append("")
    lines.extend(f"- {item}" for item in report.warnings) if report.warnings else lines.append("- None")
    return "\n".join(lines) + "\n"
