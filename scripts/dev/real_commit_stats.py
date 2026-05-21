#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Real-commit velocity stats — filter autorelease-train noise from git log.

The autodev-train auto-generates a ``chore(release): prepare vX.Y.Z`` commit
per autorelease cycle. With ~150 commits in a typical 24h window and the bulk
of them being these auto-prepares, a raw ``git log --since`` count overstates
the actual cadence of feature/fix/docs/test work.

This script reads ``git log --since=<window> --pretty=tformat:'%H|%cI|%s'``,
classifies each commit's first-line subject by Conventional Commits type, and
reports per-day and per-class breakdowns. The ``release-prep`` and ``merge``
classes are subtracted from the "real" total so a maintainer can see the
underlying development velocity rather than the train signature.

Read-only inspection. No git mutation, no network, no signing material, no
release-side effects. Pure stdlib (Python 3.10+).

Usage::

    python3 scripts/dev/real_commit_stats.py                    # 7d, text
    python3 scripts/dev/real_commit_stats.py --window "30 days ago" --format json
    python3 scripts/dev/real_commit_stats.py --write reports/real-commit-stats.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Autodev-train signature. Matches the exact subject produced by the
# autorelease train when it cuts a new vX.Y.Z (or vX.Y.Z-<pre>) commit.
# Kept strict on purpose so a hand-authored ``chore(release): note ...``
# is NOT misclassified as auto-noise.
RE_RELEASE_PREP = re.compile(r"^chore\(release\): prepare v\d+\.\d+\.\d+(-\w+)?$")

# Conventional Commits prefixes. Optional ``(scope)``.
_TYPE_RES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("feat", re.compile(r"^feat\(?[^)]*\)?:")),
    ("fix", re.compile(r"^fix\(?[^)]*\)?:")),
    ("docs", re.compile(r"^docs\(?[^)]*\)?:")),
    ("test", re.compile(r"^test\(?[^)]*\)?:")),
    ("ci", re.compile(r"^ci\(?[^)]*\)?:")),
    ("refactor", re.compile(r"^refactor\(?[^)]*\)?:")),
    ("chore", re.compile(r"^chore\(?[^)]*\)?:")),
    ("revert", re.compile(r"^revert")),
    ("merge", re.compile(r"^Merge ")),
)

# Classes that don't count toward "real" development velocity.
_NOISE_CLASSES = ("release-prep", "merge")

# Stable ordering for ``by_class`` output and the text report.
_CLASS_ORDER = (
    "feat",
    "fix",
    "docs",
    "test",
    "ci",
    "refactor",
    "chore",
    "revert",
    "merge",
    "release-prep",
    "other",
)


def classify(subject: str) -> str:
    """Classify a commit subject into a single class string.

    ``release-prep`` is checked first so the autodev-train signature wins
    over the generic ``chore`` prefix. Everything that does not match a
    known Conventional Commits prefix falls into ``other``.
    """
    if RE_RELEASE_PREP.match(subject):
        return "release-prep"
    for name, pattern in _TYPE_RES:
        if pattern.match(subject):
            return name
    return "other"


def read_git_log(window: str) -> list[tuple[str, str, str]]:
    """Return ``[(sha, committer_iso_time, subject), ...]`` for the window.

    Uses ``--no-pager`` and ``tformat:`` so each commit is exactly one line.
    Subjects with embedded ``|`` are preserved by splitting on the first two
    separators only.
    """
    cmd = [
        "git",
        "--no-pager",
        "log",
        f"--since={window}",
        "--pretty=tformat:%H|%cI|%s",
    ]
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    out: list[tuple[str, str, str]] = []
    for line in proc.stdout.splitlines():
        if not line:
            continue
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        sha, ctime, subject = parts
        out.append((sha, ctime, subject))
    return out


def build_report(window: str, rows: list[tuple[str, str, str]]) -> dict:
    """Aggregate counts into the JSON-serializable report dict."""
    by_class: dict[str, int] = defaultdict(int)
    by_day: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    real_only: list[dict] = []

    for sha, ctime, subject in rows:
        cls = classify(subject)
        by_class[cls] += 1
        day = ctime[:10]  # YYYY-MM-DD from ISO-8601
        by_day[day][cls] += 1
        if cls not in _NOISE_CLASSES:
            real_only.append({"sha": sha[:12], "time": ctime[:16], "subject": subject})

    total = len(rows)
    noise = sum(by_class.get(c, 0) for c in _NOISE_CLASSES)
    real = total - noise

    # Materialize defaultdicts to plain dicts in stable order.
    by_class_out = {c: by_class.get(c, 0) for c in _CLASS_ORDER if by_class.get(c, 0)}
    by_day_out: dict[str, dict[str, int]] = {}
    for day in sorted(by_day.keys(), reverse=True):
        by_day_out[day] = {c: by_day[day][c] for c in _CLASS_ORDER if by_day[day].get(c, 0)}

    return {
        "window": window,
        "total_commits": total,
        "real_commits": real,
        "by_class": by_class_out,
        "by_day": by_day_out,
        "recent_real": real_only[:10],
    }


def _pct(n: int, d: int) -> str:
    return "0%" if d == 0 else f"{round(100 * n / d)}%"


def format_text(report: dict) -> str:
    """Render the report as a human-friendly text block."""
    sep = "─" * 40
    lines: list[str] = []
    window = report["window"]
    total = report["total_commits"]
    real = report["real_commits"]
    rp = report["by_class"].get("release-prep", 0)
    mg = report["by_class"].get("merge", 0)

    lines.append(f"real_commit_stats — window: {window}")
    lines.append(sep)
    lines.append(f"total commits:   {total:>4}")
    lines.append(f"real commits:    {real:>4}  ({_pct(real, total)})")
    lines.append(f"release-prep:    {rp:>4}")
    lines.append(f"merge:           {mg:>4}")
    lines.append(sep)

    lines.append("By class (real only, descending):")
    real_classes = {
        c: n for c, n in report["by_class"].items() if c not in _NOISE_CLASSES
    }
    for cls, count in sorted(real_classes.items(), key=lambda kv: -kv[1]):
        lines.append(f"  {cls:<9} {count:>3}")
    if not real_classes:
        lines.append("  (none)")
    lines.append(sep)

    lines.append("By day (real commits / total):")
    if not report["by_day"]:
        lines.append("  (no commits in window)")
    else:
        for day, counts in report["by_day"].items():
            day_total = sum(counts.values())
            day_noise = sum(counts.get(c, 0) for c in _NOISE_CLASSES)
            day_real = day_total - day_noise
            lines.append(
                f"  {day}:  {day_real:>3} / {day_total:>3}  ({_pct(day_real, day_total)})"
            )
    lines.append(sep)

    lines.append("Recent 10 real commits:")
    if not report["recent_real"]:
        lines.append("  (none)")
    else:
        for entry in report["recent_real"]:
            lines.append(
                f"  {entry['time']} {entry['sha'][:7]} {entry['subject']}"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Report real (non-release-prep) commit velocity from git log. "
            "Read-only; no git mutation, no network."
        ),
    )
    parser.add_argument(
        "--window",
        default="7 days ago",
        help='Value passed to git log --since (default: "7 days ago").',
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="text",
        help="Output format on stdout (default: text).",
    )
    parser.add_argument(
        "--write",
        type=Path,
        default=None,
        help="Optional path to also write the JSON report.",
    )
    args = parser.parse_args(argv)

    rows = read_git_log(args.window)
    report = build_report(args.window, rows)

    if args.write is not None:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(
            json.dumps(report, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )

    if args.format == "json":
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=False) + "\n")
    else:
        sys.stdout.write(format_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
