#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Continuous RC release watch for autodev-train.

This watcher is deliberately post-release oriented. It validates the current
GitHub CD and registry state for an already-pushed RC, but it does not create
commits, tags, releases, or registry mutations.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def run(args: list[str], *, cwd: Path = ROOT) -> str:
    completed = subprocess.run(  # noqa: S603
        args,
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def pypi_version(version: str) -> str:
    with urllib.request.urlopen(  # noqa: S310
        f"https://pypi.org/pypi/attestplane/{version}/json",
        timeout=15,
    ) as handle:
        payload = json.load(handle)
    return str(payload["info"]["version"])


def latest_workflow_run(workflow: str) -> dict[str, Any]:
    raw = run(
        [
            "gh",
            "run",
            "list",
            "--workflow",
            workflow,
            "--limit",
            "1",
            "--json",
            "databaseId,status,conclusion,headSha,url,createdAt",
        ],
    )
    runs = json.loads(raw)
    return runs[0] if runs else {}


def collect_status(
    *,
    release_tag: str,
    python_version: str,
    npm_version: str,
    expected_latest: str,
) -> tuple[dict[str, Any], list[str]]:
    dist_tags = json.loads(
        run(["npm", "view", "@attestplane/attestplane", "dist-tags", "--json"])
    )
    npm_rc = run(["npm", "view", f"@attestplane/attestplane@{npm_version}", "version"])
    status_lines = run(["git", "status", "--short"]).splitlines()
    head = run(["git", "rev-parse", "--short", "HEAD"])
    pypi = pypi_version(python_version)
    release_cd = latest_workflow_run("release-cd.yml")

    status: dict[str, Any] = {
        "release_tag": release_tag,
        "git_head": head,
        "git_dirty_lines": len(status_lines),
        "release_cd": release_cd,
        "pypi": pypi,
        "npm_version": npm_rc,
        "npm_dist_tags": dist_tags,
    }

    problems: list[str] = []
    if status_lines:
        problems.append("git worktree is dirty")
    if release_cd.get("conclusion") != "success":
        problems.append("latest release-cd run is not successful")
    if pypi != python_version:
        problems.append(f"PyPI mismatch: expected {python_version}, got {pypi}")
    if npm_rc != npm_version:
        problems.append(f"npm package mismatch: expected {npm_version}, got {npm_rc}")
    if dist_tags.get("rc") != npm_version:
        problems.append(
            f"npm rc dist-tag mismatch: expected {npm_version}, got {dist_tags.get('rc')}"
        )
    if dist_tags.get("latest") != expected_latest:
        problems.append(
            f"npm latest dist-tag mismatch: expected {expected_latest}, got {dist_tags.get('latest')}",
        )

    return status, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-tag", default="v0.8.5-rc.1")
    parser.add_argument("--python-version", default="0.8.5rc1")
    parser.add_argument("--npm-version", default="0.8.5-rc.1")
    parser.add_argument("--expected-latest", default="0.8.0-beta.0")
    parser.add_argument("--poll-seconds", type=int, default=300)
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--stop-file",
        type=Path,
        default=ROOT / "release/alpha-train/STOP",
    )
    args = parser.parse_args(argv)

    while True:
        if args.stop_file.exists():
            print(f"STOP file exists: {args.stop_file}", flush=True)
            return 0

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        try:
            status, problems = collect_status(
                release_tag=args.release_tag,
                python_version=args.python_version,
                npm_version=args.npm_version,
                expected_latest=args.expected_latest,
            )
        except Exception as exc:  # pragma: no cover - operational guard
            status = {"error": f"{type(exc).__name__}: {exc}"}
            problems = ["status collection failed"]

        print(
            json.dumps(
                {"checked_at": now, "status": status, "problems": problems}, indent=2
            ),
            flush=True,
        )
        if problems:
            return 2
        if args.once:
            return 0
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
