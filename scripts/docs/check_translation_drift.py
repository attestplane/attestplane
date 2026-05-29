#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Check translated docs for source drift.

The initial and currently enforced use case is SECURITY.md / SECURITY_zh.md.
The script is intentionally narrow so it does not flag unrelated translated
docs that do not yet use the same frontmatter convention:

  source_file: SECURITY.md
  source_commit: <git commit>
  drift_grace_days: 14

Behavior:
- if the source file head commit matches the recorded source commit, pass;
- if it differs, warn while the drift age is within the grace period;
- fail once the drift age exceeds the explicit grace period.
"""

from __future__ import annotations

import datetime as dt
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GRACE_DAYS = 14


@dataclass(frozen=True)
class TranslationCheck:
    translation_path: Path
    source_path: Path
    recorded_commit: str
    current_commit: str
    drift_days: float
    grace_days: int


def git_output(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        cmd = "git " + " ".join(args)
        raise RuntimeError(
            f"{cmd} failed: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout.strip()


def parse_front_matter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    meta: dict[str, str] = {}
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        if not stripped or stripped.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"')
    return meta


def extract_source_path(meta: dict[str, str]) -> str | None:
    source_file = meta.get("source_file")
    if source_file:
        return source_file

    source = meta.get("source", "")
    match = re.search(r"\(([^)]+)\)", source)
    if match:
        return match.group(1)
    return None


def normalize_repo_path(path_text: str) -> Path:
    cleaned = path_text.strip()
    if cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return (REPO_ROOT / cleaned).resolve()


def current_source_commit(source_path: Path) -> str:
    rel = source_path.relative_to(REPO_ROOT).as_posix()
    return git_output("log", "-1", "--format=%H", "--", rel)


def commit_timestamp(commit: str) -> dt.datetime:
    ts_raw = git_output("show", "-s", "--format=%ct", commit)
    return dt.datetime.fromtimestamp(int(ts_raw), tz=dt.timezone.utc)


def collect_checks() -> list[TranslationCheck]:
    checks: list[TranslationCheck] = []
    for file_name in ("SECURITY_zh.md",):
        if not (REPO_ROOT / file_name).exists():
            continue
        translation_path = REPO_ROOT / file_name
        meta = parse_front_matter(translation_path)
        source_ref = extract_source_path(meta)
        recorded_commit = (
            meta.get("source_commit") or meta.get("source_sha") or ""
        ).strip()
        grace_days_raw = meta.get("drift_grace_days", str(DEFAULT_GRACE_DAYS)).strip()

        if not source_ref or not recorded_commit:
            raise RuntimeError(
                f"{file_name}: missing source metadata; expected source_file/source_commit "
                "or source/source_sha frontmatter keys"
            )

        source_path = normalize_repo_path(source_ref)
        if not source_path.exists():
            raise RuntimeError(f"{file_name}: source file does not exist: {source_ref}")

        try:
            grace_days = int(grace_days_raw)
        except ValueError as exc:
            raise RuntimeError(
                f"{file_name}: drift_grace_days must be an integer"
            ) from exc
        if grace_days <= 0:
            raise RuntimeError(f"{file_name}: drift_grace_days must be positive")

        current_commit = current_source_commit(source_path)
        if current_commit == recorded_commit:
            continue

        drift_age = dt.datetime.now(tz=dt.timezone.utc) - commit_timestamp(
            current_commit
        )
        checks.append(
            TranslationCheck(
                translation_path=translation_path,
                source_path=source_path,
                recorded_commit=recorded_commit,
                current_commit=current_commit,
                drift_days=drift_age.total_seconds() / 86400.0,
                grace_days=grace_days,
            )
        )
    return checks


def main() -> int:
    try:
        checks = collect_checks()
    except RuntimeError as exc:
        print(f"::error::{exc}")
        return 1

    if not checks:
        print("Translation drift check passed: no stale translated docs found.")
        return 0

    failed = False
    for check in checks:
        short_current = check.current_commit[:8]
        short_recorded = check.recorded_commit[:8]
        message = (
            f"{check.translation_path.name} still points to {short_recorded}, "
            f"but {check.source_path.name} is now at {short_current}; "
            f"drift age is {check.drift_days:.1f} days (grace {check.grace_days} days). "
            "Update the translated file and refresh its source_commit metadata."
        )
        if check.drift_days >= check.grace_days:
            print(f"::error file={check.translation_path}::{message}")
            failed = True
        else:
            print(f"::warning file={check.translation_path}::{message}")

    if failed:
        return 1

    print("Translation drift check passed: all stale translations are within grace.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
