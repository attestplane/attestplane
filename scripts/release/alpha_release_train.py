#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Finite alpha release train runner.

This tool packages the manual alpha release sequence into a deterministic,
queue-driven workflow. It intentionally does not generate product changes,
invent new alpha scope, bypass gates, or publish from an unprepared tree.
"""

from __future__ import annotations

import argparse
import sys
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]


def bootstrap_repo_root() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


bootstrap_repo_root()
DEFAULT_QUEUE = ROOT / "release" / "alpha-train" / "queue.json"
DEFAULT_PROPOSALS_DIR = ROOT / "release" / "alpha-train" / "proposals"
DEFAULT_REPORTS_DIR = ROOT / "release" / "alpha-train" / "reports"
DEFAULT_STATE_FILE = ROOT / "release" / "alpha-train" / "reports" / "continuous-state.json"
DEFAULT_STATE_DB = ROOT / "release" / "alpha-train" / "reports" / "continuous-state.sqlite"
DEFAULT_STOP_FILE = ROOT / "release" / "alpha-train" / "STOP"
DEFAULT_PREPARED_DIR = ROOT / "release" / "alpha-train" / "prepared"
DEFAULT_MAX_RELEASES_PER_DAY = 1
DEFAULT_MAX_PREPARES_PER_DAY = 1
FULL_AUTO_MAX_RELEASES_PER_DAY = 0
FULL_AUTO_MAX_PREPARES_PER_DAY = 0
REMOTE_PROBE_TIMEOUT_SECONDS = 15
REMOTE_PROBE_ATTEMPTS = 3
REMOTE_PUSH_ATTEMPTS = 3
REMOTE_PUSH_RETRY_SECONDS = 10
REMOTE_PUSH_TIMEOUT_SECONDS = 120
CONTINUOUS_REMOTE_PUSH_COOLDOWN_SECONDS = 300
REGISTRY_VERIFY_ATTEMPTS = 10
REGISTRY_VERIFY_POLL_SECONDS = 15
PUBLISH_WORKFLOW_ATTEMPTS = 2
PUBLISH_WORKFLOW_RETRY_SECONDS = 15

EXTERNAL_STAGES = (
    "local_gates_passed",
    "main_pushed",
    "tag_pushed",
    "gh_release_created",
    "pypi_published",
    "npm_published",
    "dist_tag_synced",
    "registry_verified",
)

ACTIVE_RELEASE_STATUSES = {"prepared", "processing"}
TERMINAL_RELEASE_STATUSES = {"released", "retired", "failed"}

FORBIDDEN_ADVISORY_COMMANDS = (
    "git push",
    "git tag",
    "gh release",
    "gh workflow run",
    "npm publish",
    "twine upload",
)


@dataclass(frozen=True)
class AlphaCandidate:
    release: str
    python_version: str
    npm_version: str
    release_notes: str
    manifest: str
    checksums: str
    publish_python: bool
    publish_npm: bool
    create_github_release: bool

    @classmethod
    def from_json(cls, value: dict[str, Any]) -> "AlphaCandidate":
        required = ("release", "python_version", "npm_version")
        missing = [key for key in required if not isinstance(value.get(key), str) or not value[key]]
        if missing:
            raise ValueError(f"alpha candidate missing required fields: {', '.join(missing)}")
        release = value["release"]
        python_version = value["python_version"]
        npm_version = value["npm_version"]
        if not release.startswith("v") or not release.endswith("-alpha"):
            raise ValueError(f"alpha release names must look like vX.Y.Z-alpha: {release!r}")
        if not python_version.endswith("a0"):
            raise ValueError(f"python alpha versions must use PEP 440 a0 form: {python_version!r}")
        if not npm_version.endswith("-alpha"):
            raise ValueError(f"npm alpha versions must use an -alpha prerelease suffix: {npm_version!r}")
        return cls(
            release=release,
            python_version=python_version,
            npm_version=npm_version,
            release_notes=value.get("release_notes", f"docs/release-notes/{release}.draft.md"),
            manifest=value.get("manifest", f"release/artifacts/{release}/artifact-manifest.json"),
            checksums=value.get("checksums", f"release/artifacts/{release}/checksums.sha256"),
            publish_python=bool(value.get("publish_python", True)),
            publish_npm=bool(value.get("publish_npm", True)),
            create_github_release=bool(value.get("create_github_release", True)),
        )


class QueueDependencyPending(RuntimeError):
    """Raised when a release step is waiting on a queued prerequisite."""


def run(argv: list[str], *, dry_run: bool, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(argv), flush=True)
    if dry_run:
        return subprocess.CompletedProcess(argv, 0, "", "")
    return subprocess.run(argv, cwd=ROOT, env=env, text=True, check=True)


def run_git_push(argv: list[str], *, dry_run: bool) -> subprocess.CompletedProcess[str]:
    """Retry idempotent git push commands without retrying non-idempotent release actions."""
    print("+ " + " ".join(argv), flush=True)
    if dry_run:
        return subprocess.CompletedProcess(argv, 0, "", "")
    if git_push_remote_converged(argv):
        print("git push remote state already converged; skipping push", flush=True)
        return subprocess.CompletedProcess(argv, 0, "", "")
    last_error: subprocess.CalledProcessError | subprocess.TimeoutExpired | None = None
    for attempt in range(1, REMOTE_PUSH_ATTEMPTS + 1):
        try:
            return attempt_git_push_once(argv, dry_run=False)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            last_error = exc
            if git_push_remote_converged(argv):
                print("git push remote state already converged; continuing after failed or timed-out local push", flush=True)
                return subprocess.CompletedProcess(argv, 0, "", "")
            if attempt == REMOTE_PUSH_ATTEMPTS:
                break
            print(
                f"git push attempt {attempt}/{REMOTE_PUSH_ATTEMPTS} failed or timed out; "
                f"retrying in {REMOTE_PUSH_RETRY_SECONDS}s",
                flush=True,
            )
            time.sleep(REMOTE_PUSH_RETRY_SECONDS)
    assert last_error is not None
    raise last_error


def attempt_git_push_once(argv: list[str], *, dry_run: bool) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(argv), flush=True)
    if dry_run:
        return subprocess.CompletedProcess(argv, 0, "", "")
    result = subprocess.run(
        argv,
        cwd=ROOT,
        text=True,
        timeout=REMOTE_PUSH_TIMEOUT_SECONDS,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    echo_subprocess_output(result.stdout)
    echo_subprocess_output(result.stderr)
    if result.returncode == 0:
        return result
    raise subprocess.CalledProcessError(
        result.returncode,
        argv,
        output=result.stdout,
        stderr=result.stderr,
    )


def echo_subprocess_output(text: str | None) -> None:
    if not text:
        return
    print(text, end="" if text.endswith("\n") else "\n", flush=True)


def watch_publish_workflow(
    run_id: str,
    *,
    workflow_name: str,
    observed: Callable[[], bool],
) -> tuple[bool, bool, str | None]:
    try:
        run(["gh", "run", "watch", run_id, "--exit-status"], dry_run=False)
        return True, False, None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        watch_error = f"{type(exc).__name__}: {exc}"
        if observed():
            return True, True, watch_error
        print(
            f"{workflow_name} watch failed for run {run_id}: {watch_error}",
            flush=True,
        )
        return False, False, watch_error


def is_git_push_error(exc: BaseException) -> bool:
    cmd = getattr(exc, "cmd", None)
    return isinstance(cmd, list) and len(cmd) >= 3 and cmd[:3] == ["git", "push", "origin"]


def git_push_failure_text(exc: BaseException) -> str:
    pieces: list[str] = [type(exc).__name__, str(exc)]
    for attr in ("stderr", "output"):
        value = getattr(exc, attr, None)
        if isinstance(value, bytes):
            try:
                value = value.decode("utf-8", errors="replace")
            except Exception:  # pragma: no cover - defensive fallback.
                value = repr(value)
        if isinstance(value, str) and value:
            pieces.append(value)
    return "\n".join(piece for piece in pieces if piece).lower()


def classify_git_push_failure(exc: BaseException) -> str:
    if isinstance(exc, subprocess.TimeoutExpired):
        return "git_push_timeout"
    text = git_push_failure_text(exc)
    if any(
        phrase in text
        for phrase in (
            "failed to connect to server",
            "failed to connect to github.com",
            "couldn't connect to server",
            "connection timed out",
            "recv failure",
            "could not resolve host",
            "network is unreachable",
        )
    ):
        return "git_push_network_unavailable"
    if any(
        phrase in text
        for phrase in (
            "authentication failed",
            "permission denied",
            "repository not found",
            "could not read from remote repository",
            "fatal: unable to access",
        )
    ):
        return "git_push_auth_or_repo_unavailable"
    if any(
        phrase in text
        for phrase in (
            "non-fast-forward",
            "fetch first",
            "rejected",
            "updates were rejected",
            "failed to push some refs",
        )
    ):
        return "git_push_rejected"
    return f"git_push_{type(exc).__name__.lower()}"


def local_tag_points_at_head(release: str) -> bool:
    try:
        tag_result = subprocess.run(
            ["git", "rev-list", "-n", "1", f"refs/tags/{release}"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=REMOTE_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
        if tag_result.returncode != 0:
            return False
        head_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=REMOTE_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
        if head_result.returncode != 0:
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return tag_result.stdout.strip() == head_result.stdout.strip()


def git_push_remote_converged(argv: list[str]) -> bool:
    if len(argv) != 4 or argv[:3] != ["git", "push", "origin"]:
        return False
    ref = argv[3]
    try:
        if ref == "main":
            local_tracking_head = capture(
                ["git", "rev-parse", "--verify", "refs/remotes/origin/main"],
                timeout=REMOTE_PROBE_TIMEOUT_SECONDS,
            )
            local_head = capture(["git", "rev-parse", "HEAD"], timeout=REMOTE_PROBE_TIMEOUT_SECONDS)
            if local_tracking_head == local_head:
                return True
            remote_head = capture(["git", "ls-remote", "origin", "refs/heads/main"], timeout=REMOTE_PROBE_TIMEOUT_SECONDS)
            return bool(remote_head) and remote_head.split()[0] == local_head
        if re.fullmatch(r"v\d+\.\d+\.\d+-alpha", ref):
            remote_tag = capture(["git", "ls-remote", "origin", f"refs/tags/{ref}"], timeout=REMOTE_PROBE_TIMEOUT_SECONDS)
            return bool(remote_tag)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return False


def capture(argv: list[str], *, timeout: int | None = None) -> str:
    return subprocess.check_output(argv, cwd=ROOT, text=True, timeout=timeout).strip()


def state_db_path(state_path: Path) -> Path:
    if state_path.suffix == ".sqlite":
        return state_path
    return state_path.with_suffix(".sqlite")


def git_push_stage_name(ref: str) -> str:
    if ref == "main":
        return "main_pushed"
    if re.fullmatch(r"v\d+\.\d+\.\d+-alpha", ref):
        return "tag_pushed"
    raise ValueError(f"unsupported git push ref for alpha train queue: {ref!r}")


def init_state_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS release_state (
                release TEXT PRIMARY KEY,
                python_version TEXT,
                npm_version TEXT,
                status TEXT NOT NULL,
                updated_at_epoch INTEGER NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_counts (
                day TEXT NOT NULL,
                kind TEXT NOT NULL,
                count INTEGER NOT NULL,
                PRIMARY KEY (day, kind)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS state_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                release TEXT,
                event TEXT NOT NULL,
                detail TEXT NOT NULL,
                created_at_epoch INTEGER NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS release_stages (
                release TEXT NOT NULL,
                stage TEXT NOT NULL,
                status TEXT NOT NULL,
                detail TEXT NOT NULL,
                updated_at_epoch INTEGER NOT NULL,
                PRIMARY KEY (release, stage)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS git_push_tasks (
                release TEXT NOT NULL,
                ref TEXT NOT NULL,
                stage TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL,
                last_error TEXT NOT NULL,
                next_attempt_at_epoch INTEGER NOT NULL,
                created_at_epoch INTEGER NOT NULL,
                updated_at_epoch INTEGER NOT NULL,
                PRIMARY KEY (release, ref)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS state_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        db.execute(
            "INSERT OR REPLACE INTO state_meta(key, value) VALUES (?, ?)",
            ("schema", "attestplane_alpha_continuous_state.sqlite.v1"),
        )


def release_status(db: sqlite3.Connection, release: str) -> str | None:
    row = db.execute("SELECT status FROM release_state WHERE release = ?", (release,)).fetchone()
    return str(row[0]) if row else None


def upsert_release_state(db: sqlite3.Connection, candidate: AlphaCandidate, status: str, now: int) -> None:
    current = release_status(db, candidate.release)
    if current == "released" and status != "released":
        return
    if current == "retired" and status in {"prepared", "processing"}:
        return
    db.execute(
        """
        INSERT INTO release_state(release, python_version, npm_version, status, updated_at_epoch)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(release) DO UPDATE SET
            python_version = excluded.python_version,
            npm_version = excluded.npm_version,
            status = excluded.status,
            updated_at_epoch = excluded.updated_at_epoch
        """,
        (candidate.release, candidate.python_version, candidate.npm_version, status, now),
    )


def increment_daily_count(db: sqlite3.Connection, kind: str, now: int) -> None:
    day = time.strftime("%Y-%m-%d", time.gmtime(now))
    db.execute(
        """
        INSERT INTO daily_counts(day, kind, count) VALUES (?, ?, 1)
        ON CONFLICT(day, kind) DO UPDATE SET count = count + 1
        """,
        (day, kind),
    )


def append_state_event(db: sqlite3.Connection, release: str | None, event: str, detail: dict[str, Any], now: int) -> None:
    db.execute(
        "INSERT INTO state_events(release, event, detail, created_at_epoch) VALUES (?, ?, ?, ?)",
        (release, event, json.dumps(detail, sort_keys=True), now),
    )


def enqueue_git_push_task(path: Path, candidate: AlphaCandidate, ref: str, *, dry_run: bool) -> None:
    if dry_run:
        return
    stage = git_push_stage_name(ref)
    db_path = state_db_path(path)
    init_state_db(db_path)
    now = int(time.time())
    with sqlite3.connect(db_path) as db:
        row = db.execute(
            "SELECT status FROM git_push_tasks WHERE release = ? AND ref = ?",
            (candidate.release, ref),
        ).fetchone()
        if row and str(row[0]) == "done":
            return
        if row is None:
            db.execute(
                """
                INSERT INTO git_push_tasks(
                    release, ref, stage, status, attempts, last_error, next_attempt_at_epoch, created_at_epoch, updated_at_epoch
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (candidate.release, ref, stage, "queued", 0, "", now, now, now),
            )
        else:
            db.execute(
                """
                UPDATE git_push_tasks
                   SET stage = ?, status = 'queued', updated_at_epoch = ?
                 WHERE release = ? AND ref = ?
                """,
                (stage, now, candidate.release, ref),
            )
        append_state_event(db, candidate.release, "git_push_queued", {"ref": ref, "stage": stage}, now)
    if path.suffix != ".sqlite":
        write_continuous_state_snapshot(path, continuous_state_from_db(db_path))


def update_git_push_task(
    path: Path,
    candidate: AlphaCandidate,
    ref: str,
    *,
    status: str,
    last_error: str = "",
    attempts_delta: int = 0,
    next_attempt_at_epoch: int | None = None,
    dry_run: bool,
) -> None:
    if dry_run:
        return
    db_path = state_db_path(path)
    init_state_db(db_path)
    now = int(time.time())
    stage = git_push_stage_name(ref)
    with sqlite3.connect(db_path) as db:
        current = db.execute(
            "SELECT attempts FROM git_push_tasks WHERE release = ? AND ref = ?",
            (candidate.release, ref),
        ).fetchone()
        if current is None:
            attempts = max(0, attempts_delta)
            db.execute(
                """
                INSERT INTO git_push_tasks(
                    release, ref, stage, status, attempts, last_error, next_attempt_at_epoch, created_at_epoch, updated_at_epoch
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.release,
                    ref,
                    stage,
                    status,
                    attempts,
                    last_error,
                    next_attempt_at_epoch or now,
                    now,
                    now,
                ),
            )
        else:
            db.execute(
                """
                UPDATE git_push_tasks
                   SET stage = ?,
                       status = ?,
                       attempts = attempts + ?,
                       last_error = ?,
                       next_attempt_at_epoch = ?,
                       updated_at_epoch = ?
                 WHERE release = ? AND ref = ?
                """,
                (
                    stage,
                    status,
                    attempts_delta,
                    last_error,
                    next_attempt_at_epoch or now,
                    now,
                    candidate.release,
                    ref,
                ),
            )
        append_state_event(
            db,
            candidate.release,
            f"git_push_{status}",
            {"ref": ref, "stage": stage, "last_error": last_error, "next_attempt_at_epoch": next_attempt_at_epoch or now},
            now,
        )
    if status == "done":
        mark_stage(path, candidate, stage, "done", {"ref": ref})
    else:
        mark_stage(
            path,
            candidate,
            stage,
            "queued",
            {"ref": ref, "next_attempt_at_epoch": next_attempt_at_epoch or now, "last_error": last_error},
        )
    if path.suffix != ".sqlite":
        write_continuous_state_snapshot(path, continuous_state_from_db(db_path))


def process_git_push_queue(path: Path, *, dry_run: bool, cooldown_seconds: int) -> list[dict[str, Any]]:
    if dry_run:
        return []
    db_path = state_db_path(path)
    init_state_db(db_path)
    now = int(time.time())
    processed: list[dict[str, Any]] = []
    with sqlite3.connect(db_path) as db:
        rows = db.execute(
            """
            SELECT release, ref, stage, status, attempts, next_attempt_at_epoch
              FROM git_push_tasks
             WHERE status IN ('queued', 'cooldown')
               AND next_attempt_at_epoch <= ?
             ORDER BY next_attempt_at_epoch, created_at_epoch
            """,
            (now,),
        ).fetchall()
        for release, ref, stage, status, attempts, next_attempt_at_epoch in rows:
            candidate = prepared_candidate_from_release(str(release))
            argv = ["git", "push", "origin", str(ref)]
            try:
                if git_push_remote_converged(argv):
                    update_git_push_task(path, candidate, str(ref), status="done", dry_run=False)
                    processed.append({"release": str(release), "ref": str(ref), "status": "done", "observed": True})
                    continue
                attempt_git_push_once(argv, dry_run=False)
                update_git_push_task(path, candidate, str(ref), status="done", dry_run=False)
                processed.append({"release": str(release), "ref": str(ref), "status": "done"})
            except Exception as exc:
                failure_reason = classify_git_push_failure(exc)
                update_git_push_task(
                    path,
                    candidate,
                    str(ref),
                    status="cooldown",
                    last_error=failure_reason,
                    attempts_delta=1,
                    next_attempt_at_epoch=now + cooldown_seconds,
                    dry_run=False,
                )
                processed.append(
                    {
                        "release": str(release),
                        "ref": str(ref),
                        "status": "cooldown",
                        "reason": failure_reason,
                        "next_attempt_at_epoch": now + cooldown_seconds,
                    }
                )
    if path.suffix != ".sqlite":
        write_continuous_state_snapshot(path, continuous_state_from_db(db_path))
    return processed


def stage_status(db: sqlite3.Connection, release: str, stage: str) -> str | None:
    row = db.execute("SELECT status FROM release_stages WHERE release = ? AND stage = ?", (release, stage)).fetchone()
    return str(row[0]) if row else None


def mark_stage(path: Path | None, candidate: AlphaCandidate, stage: str, status: str, detail: dict[str, Any] | None = None) -> None:
    if path is None:
        return
    if stage not in EXTERNAL_STAGES:
        raise ValueError(f"unknown alpha train stage: {stage}")
    db_path = state_db_path(path)
    init_state_db(db_path)
    now = int(time.time())
    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            INSERT INTO release_stages(release, stage, status, detail, updated_at_epoch)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(release, stage) DO UPDATE SET
                status = excluded.status,
                detail = excluded.detail,
                updated_at_epoch = excluded.updated_at_epoch
            """,
            (candidate.release, stage, status, json.dumps(detail or {}, sort_keys=True), now),
        )
        append_state_event(db, candidate.release, f"stage_{status}", {"stage": stage, **(detail or {})}, now)
    if path.suffix != ".sqlite":
        write_continuous_state_snapshot(path, continuous_state_from_db(db_path))


def stage_done(path: Path | None, candidate: AlphaCandidate, stage: str) -> bool:
    if path is None:
        return False
    db_path = state_db_path(path)
    if not db_path.exists():
        return False
    init_state_db(db_path)
    with sqlite3.connect(db_path) as db:
        return stage_status(db, candidate.release, stage) == "done"


def continuous_state_from_db(db_path: Path) -> dict[str, Any]:
    init_state_db(db_path)
    with sqlite3.connect(db_path) as db:
        rows = db.execute("SELECT release, status FROM release_state ORDER BY release").fetchall()
        counts = db.execute("SELECT day, kind, count FROM daily_counts ORDER BY day, kind").fetchall()
        stage_rows = db.execute(
            "SELECT release, stage, status FROM release_stages ORDER BY release, stage"
        ).fetchall()
        queue_rows = db.execute(
            "SELECT release, ref, stage, status, attempts, next_attempt_at_epoch FROM git_push_tasks ORDER BY next_attempt_at_epoch, created_at_epoch"
        ).fetchall()
    prepared = sorted(str(release) for release, status in rows if status in ACTIVE_RELEASE_STATUSES)
    processed = sorted(str(release) for release, status in rows if status == "released")
    retired = sorted(str(release) for release, status in rows if status == "retired")
    prepare_count_by_day = {str(day): int(count) for day, kind, count in counts if kind == "prepared"}
    release_count_by_day = {str(day): int(count) for day, kind, count in counts if kind == "released"}
    return {
        "schema": "attestplane_alpha_continuous_state.v2",
        "state_backend": "sqlite",
        "state_db": str(db_path),
        "prepared_releases": prepared,
        "processed_releases": processed,
        "retired_releases": retired,
        "prepare_count_by_day": prepare_count_by_day,
        "release_count_by_day": release_count_by_day,
        "release_stages": {
            str(release): {str(stage): str(status) for rel, stage, status in stage_rows if rel == release}
            for release in sorted({row[0] for row in stage_rows})
        },
        "git_push_tasks": [
            {
                "release": str(release),
                "ref": str(ref),
                "stage": str(stage),
                "status": str(status),
                "attempts": int(attempts),
                "next_attempt_at_epoch": int(next_attempt_at_epoch),
            }
            for release, ref, stage, status, attempts, next_attempt_at_epoch in queue_rows
        ],
        "updated_at_epoch": int(time.time()),
    }


def write_continuous_state_snapshot(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def migrate_json_state_to_sqlite(state_path: Path, db_path: Path) -> None:
    if not state_path.exists():
        return
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("processed_releases", []), list):
        raise ValueError(f"continuous state is malformed: {state_path}")
    save_continuous_state(state_path, payload)


def remote_probe(argv: list[str], *, timeout_error: str) -> subprocess.CompletedProcess[str]:
    last_timeout: subprocess.TimeoutExpired | None = None
    for attempt in range(1, REMOTE_PROBE_ATTEMPTS + 1):
        try:
            return subprocess.run(
                argv,
                cwd=ROOT,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=REMOTE_PROBE_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            last_timeout = exc
            if attempt < REMOTE_PROBE_ATTEMPTS:
                print(
                    f"remote probe timeout {attempt}/{REMOTE_PROBE_ATTEMPTS}: {' '.join(argv)}",
                    flush=True,
                )
    raise RuntimeError(timeout_error) from last_timeout


def github_repo_slug() -> str:
    origin = capture(["git", "remote", "get-url", "origin"], timeout=REMOTE_PROBE_TIMEOUT_SECONDS)
    match = re.search(r"github\.com[:/](?P<slug>[^/]+/[^/.]+)(?:\.git)?$", origin)
    if not match:
        raise RuntimeError(f"origin is not a GitHub repository URL: {origin!r}")
    return match.group("slug")


def remote_tag_exists(release: str) -> bool:
    repo = github_repo_slug()
    remote_tag = remote_probe(
        ["gh", "api", f"repos/{repo}/git/ref/tags/{release}", "--silent"],
        timeout_error=f"remote tag check timed out for {release}",
    )
    return remote_tag.returncode == 0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_queue(path: Path) -> list[AlphaCandidate]:
    if not path.exists():
        raise FileNotFoundError(f"alpha queue not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list):
        raise ValueError("alpha queue must contain a candidates array")
    candidates = [AlphaCandidate.from_json(item) for item in raw_candidates]
    seen: set[str] = set()
    duplicates: set[str] = set()
    for candidate in candidates:
        if candidate.release in seen:
            duplicates.add(candidate.release)
        seen.add(candidate.release)
    if duplicates:
        raise ValueError("duplicate alpha release entries: " + ", ".join(sorted(duplicates)))
    return candidates


def write_queue(path: Path, candidates: list[AlphaCandidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "attestplane_alpha_release_train_queue.v1",
        "candidates": [
            {
                "release": candidate.release,
                "python_version": candidate.python_version,
                "npm_version": candidate.npm_version,
                "release_notes": candidate.release_notes,
                "manifest": candidate.manifest,
                "checksums": candidate.checksums,
                "publish_python": candidate.publish_python,
                "publish_npm": candidate.publish_npm,
                "create_github_release": candidate.create_github_release,
            }
            for candidate in candidates
        ],
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def alpha_python_version(release: str) -> str:
    return release.removeprefix("v").removesuffix("-alpha") + "a0"


def alpha_npm_version(release: str) -> str:
    return release.removeprefix("v")


def parse_alpha_release(release: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)-alpha", release)
    if not match:
        raise ValueError(f"invalid alpha release: {release}")
    return tuple(int(part) for part in match.groups())


def latest_alpha_release_from_notes() -> str:
    releases = [
        path.name.removesuffix(".draft.md")
        for path in (ROOT / "docs" / "release-notes").glob("v*-alpha.draft.md")
        if re.fullmatch(r"v\d+\.\d+\.\d+-alpha", path.name.removesuffix(".draft.md"))
    ]
    if not releases:
        return "v0.0.0-alpha"
    return sorted(releases, key=parse_alpha_release)[-1]


def next_alpha_release() -> str:
    major, minor, patch = parse_alpha_release(latest_alpha_release_from_notes())
    if patch >= 10:
        return f"v{major}.{minor + 1}.0-alpha"
    return f"v{major}.{minor}.{patch + 1}-alpha"


def resolve_next_alpha_release(release_override: str | None = None) -> str:
    if release_override is None:
        return next_alpha_release()
    parse_alpha_release(release_override)
    return release_override


def compare_alpha_releases(left: str, right: str) -> int:
    left_parts = parse_alpha_release(left)
    right_parts = parse_alpha_release(right)
    return (left_parts > right_parts) - (left_parts < right_parts)


def prepared_candidate_from_release(release: str) -> AlphaCandidate:
    return AlphaCandidate.from_json(
        {
            "release": release,
            "python_version": alpha_python_version(release),
            "npm_version": alpha_npm_version(release),
            "release_notes": f"docs/release-notes/{release}.draft.md",
            "manifest": f"release/artifacts/{release}/artifact-manifest.json",
            "checksums": f"release/artifacts/{release}/checksums.sha256",
            "publish_python": True,
            "publish_npm": True,
            "create_github_release": True,
        }
    )


def draft_candidate_id(candidate: AlphaCandidate) -> str:
    return f"{candidate.release}-{capture(['git', 'rev-parse', '--short=12', 'HEAD'])}"


def write_draft_release_notes(candidate: AlphaCandidate, advisory_plan: Path | None, prepared_dir: Path) -> Path:
    path = prepared_dir / "NOTES.draft.md"
    advisory_ref = display_path(advisory_plan) if advisory_plan else "not available"
    path.write_text(
        "\n".join(
            [
                f"# {candidate.release}",
                "",
                f"`{candidate.release}` is a draft alpha candidate prepared by the local alpha train.",
                "",
                "## Highlights",
                "",
                "- Draft only; not queued for release and not authorized for publication.",
                "- Carries forward the current Attestplane SDK and verifier surface as candidate planning context.",
                "- Preserves deterministic verifier, release-artifact, and claim-safety boundaries.",
                "- Records advisory planning as non-authoritative release-train evidence.",
                "",
                "## Advisory Planning Reference",
                "",
                f"- Advisory plan: `{advisory_ref}`",
                "- Advisory output is not release authorization.",
                "",
                "## Explicit Boundaries",
                "",
                "This release does not claim:",
                "",
                "- EU AI Act compliance,",
                "- GDPR compliance,",
                "- legal certification,",
                "- production readiness,",
                "- certified provenance,",
                "- SLSA L3,",
                "- production-grade supply-chain security, or",
                "- long-term archival trust guarantees.",
                "",
                "## Expected Assets",
                "",
                f"- `sdk/python/dist/attestplane-{candidate.python_version}-py3-none-any.whl`",
                f"- `sdk/python/dist/attestplane-{candidate.python_version}.tar.gz`",
                f"- `sdk/typescript/attestplane-attestplane-{candidate.npm_version}.tgz`",
                "- Release artifacts must still be prepared by the release prep gate before publication.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def write_draft_candidate_bundle(candidate: AlphaCandidate, *, advisory_plan: Path | None, prepared_root: Path) -> Path:
    candidate_id = draft_candidate_id(candidate)
    prepared_dir = prepared_root / candidate_id
    prepared_dir.mkdir(parents=True, exist_ok=True)
    notes = write_draft_release_notes(candidate, advisory_plan, prepared_dir)
    manifest_path = prepared_dir / "manifest.json"
    manifest = {
        "advisory_plan": str(display_path(advisory_plan)) if advisory_plan else None,
        "candidate_id": candidate_id,
        "candidate_release": candidate.release,
        "explicit_non_actions": {
            "deploy": "not performed",
            "force_push": "not performed",
            "npm_latest_change": "not performed for draft-only candidate",
            "package_version_bump": "not performed",
            "release_publish": "not performed",
            "workflow_dispatch": "not performed",
        },
        "explicit_non_claims": {
            "certified_provenance": False,
            "compliance_certification": False,
            "production_ready": False,
            "slsa_l3": False,
        },
        "notes": str(notes.relative_to(prepared_dir)),
        "schema": "attestplane_alpha_prepared_candidate_draft.v1",
        "source_state": {
            "prepared_by": "alpha_release_train_auto_prepare",
            "target_commit": capture(["git", "rev-parse", "HEAD"]),
        },
        "status": "draft_unverified_not_queued",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksums = prepared_dir / "SHA256SUMS"
    checksums.write_text(
        f"{sha256_file(notes)}  NOTES.draft.md\n{sha256_file(manifest_path)}  manifest.json\n",
        encoding="utf-8",
    )
    (prepared_dir / "READY").write_text(
        "draft only: not release-ready, not queued, not authorized for publish\n",
        encoding="utf-8",
    )
    return prepared_dir


def update_python_version(version: str) -> None:
    path = ROOT / "sdk" / "python" / "pyproject.toml"
    text = path.read_text(encoding="utf-8")
    updated = re.sub(r'(?m)^version = "[^"]+"$', f'version = "{version}"', text, count=1)
    updated = updated.replace(
        '"Development Status :: 2 - Pre-Alpha"',
        '"Development Status :: 3 - Alpha"',
    )
    if updated == text:
        raise RuntimeError(f"could not update Python version in {path}")
    path.write_text(updated, encoding="utf-8")


def update_python_runtime_version(version: str) -> None:
    path = ROOT / "sdk" / "python" / "src" / "attestplane" / "__init__.py"
    text = path.read_text(encoding="utf-8")
    updated = re.sub(r'(?m)^__version__ = "[^"]+"$', f'__version__ = "{version}"', text, count=1)
    if updated == text:
        raise RuntimeError(f"could not update Python runtime version in {path}")
    path.write_text(updated, encoding="utf-8")


def update_python_import_surface_test_version(version: str) -> None:
    path = ROOT / "sdk" / "python" / "tests" / "test_import_surface.py"
    text = path.read_text(encoding="utf-8")
    updated = re.sub(
        r'(?m)^    assert attestplane\.__version__ == "[^"]+"$',
        f'    assert attestplane.__version__ == "{version}"',
        text,
        count=1,
    )
    if updated == text:
        raise RuntimeError(f"could not update Python import-surface test version in {path}")
    path.write_text(updated, encoding="utf-8")


def sync_python_lockfile() -> None:
    run(["bash", "-lc", "cd sdk/python && uv lock"], dry_run=False)


def update_npm_version(version: str) -> None:
    path = ROOT / "sdk" / "typescript" / "package.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = version
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    lock_path = ROOT / "sdk" / "typescript" / "package-lock.json"
    if lock_path.exists():
        lock_payload = json.loads(lock_path.read_text(encoding="utf-8"))
        lock_payload["version"] = version
        packages = lock_payload.get("packages")
        if isinstance(packages, dict) and isinstance(packages.get(""), dict):
            packages[""]["version"] = version
        lock_path.write_text(json.dumps(lock_payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def update_npm_runtime_version(version: str) -> None:
    path = ROOT / "sdk" / "typescript" / "src" / "index_version.ts"
    text = path.read_text(encoding="utf-8")
    updated = re.sub(r"(?m)^export const VERSION = '[^']+';$", f"export const VERSION = '{version}';", text, count=1)
    if updated == text:
        raise RuntimeError(f"could not update TypeScript runtime version in {path}")
    path.write_text(updated, encoding="utf-8")


def update_readme_release_state(candidate: AlphaCandidate) -> None:
    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    replacements = [
        (r"PyPI-attestplane%20[0-9.]+a0-blue", f"PyPI-attestplane%20{candidate.python_version}-blue"),
        (r"\*\*v0\.0\.5-alpha\*\* builds on", f"**{candidate.release}** builds on"),
        (r"The next alpha line, \*\*v0\.0\.5-alpha\*\*,", f"The current alpha line, **{candidate.release}**,"),
        (
            r"Python \(0\.0\.5a0\)\s+\│  TypeScript \(0\.0\.5-alpha\)",
            f"Python ({candidate.python_version})   │  TypeScript ({candidate.npm_version})",
        ),
        (
            r"Python `attestplane==[^`]+` is published to PyPI, and\n`@attestplane/attestplane@[^`]+` is published to npm",
            f"Python `attestplane=={candidate.python_version}` is published to PyPI, and\n`@attestplane/attestplane@{candidate.npm_version}` is published to npm",
        ),
        (r"The `v0\.0\.5-alpha` line tightens", f"The `{candidate.release}` line tightens"),
        (r"through the v0\.0\.5-alpha release-prep line", f"through the {candidate.release} release-prep line"),
        (
            r"\(`v0\.0\.5-alpha`\), still under alpha/non-certification boundaries",
            f"(`{candidate.release}`), still under alpha/non-certification boundaries",
        ),
        (r"`attestplane==[^`]+` \| \[PyPI\]", f"`attestplane=={candidate.python_version}` | [PyPI]"),
        (
            r"`@attestplane/attestplane@[^`]+` \| \[npm alpha/latest dist-tags\]",
            f"`@attestplane/attestplane@{candidate.npm_version}` | [npm alpha/latest dist-tags]",
        ),
        (r"GitHub Release \| `v[0-9.]+-alpha`", f"GitHub Release | `{candidate.release}`"),
        (r"pip install attestplane==[0-9.]+a0", f"pip install attestplane=={candidate.python_version}"),
        (r"prepared v0\.0\.5-alpha artifacts include", f"prepared {candidate.release} artifacts include"),
        (r"\*\*M5 — v0\.1\.0 alpha hardening\*\*", "**M5 — v0.1.x alpha hardening**"),
    ]
    updated = text
    for pattern, replacement in replacements:
        updated = re.sub(pattern, replacement, updated, count=1)
    if updated == text:
        raise RuntimeError(f"could not update README release state in {path}")
    path.write_text(updated, encoding="utf-8")


def sync_version_state(candidate: AlphaCandidate) -> None:
    update_python_version(candidate.python_version)
    update_python_runtime_version(candidate.python_version)
    update_python_import_surface_test_version(candidate.python_version)
    sync_python_lockfile()
    update_npm_version(candidate.npm_version)
    update_npm_runtime_version(candidate.npm_version)
    update_readme_release_state(candidate)


def write_release_notes(candidate: AlphaCandidate, advisory_plan: Path | None) -> None:
    path = ROOT / candidate.release_notes
    path.parent.mkdir(parents=True, exist_ok=True)
    advisory_ref = display_path(advisory_plan) if advisory_plan else "not available"
    path.write_text(
        "\n".join(
            [
                f"# {candidate.release}",
                "",
                f"`{candidate.release}` is an automated alpha release prepared by the local alpha train.",
                "",
                "## Highlights",
                "",
                "- Cuts the current Attestplane SDK and verifier surface as an alpha package release.",
                "- Preserves deterministic verifier, release-artifact, and claim-safety boundaries.",
                "- Records advisory planning as non-authoritative release-train evidence.",
                "",
                "## Advisory Planning Reference",
                "",
                f"- Advisory plan: `{advisory_ref}`",
                "- Advisory output is not release authorization.",
                "",
                "## Explicit Boundaries",
                "",
                "This release does not claim:",
                "",
                "- EU AI Act compliance,",
                "- GDPR compliance,",
                "- legal certification,",
                "- production readiness,",
                "- certified provenance,",
                "- SLSA L3,",
                "- production-grade supply-chain security, or",
                "- long-term archival trust guarantees.",
                "",
                "## Expected Assets",
                "",
                f"- `sdk/python/dist/attestplane-{candidate.python_version}-py3-none-any.whl`",
                f"- `sdk/python/dist/attestplane-{candidate.python_version}.tar.gz`",
                f"- `sdk/typescript/attestplane-attestplane-{candidate.npm_version}.tgz`",
                f"- `{candidate.checksums}`",
                f"- `{candidate.manifest}`",
                "",
            ]
        ),
        encoding="utf-8",
    )


def artifact_entry(kind: str, package: str, version: str, path: str) -> dict[str, Any]:
    artifact_path = ROOT / path
    return {
        "kind": kind,
        "package": package,
        "path": path,
        "sha256": sha256_file(artifact_path),
        "size_bytes": artifact_path.stat().st_size,
        "validation": {"published": False},
        "version": version,
    }


def build_release_artifacts(candidate: AlphaCandidate) -> None:
    run(
        [
            "bash",
            "-lc",
            "cd sdk/python && rm -rf dist build && .venv/bin/python -m build >/dev/null && .venv/bin/python -m twine check dist/*",
        ],
        dry_run=False,
    )
    run(
        [
            "bash",
            "-lc",
            "cd sdk/typescript && find . -maxdepth 1 -name '*.tgz' -delete && npm ci --silent >/dev/null && npm run build --silent >/dev/null && npm test --silent >/dev/null && npm pack --silent >/dev/null",
        ],
        dry_run=False,
    )
    for path in (
        f"sdk/python/dist/attestplane-{candidate.python_version}-py3-none-any.whl",
        f"sdk/python/dist/attestplane-{candidate.python_version}.tar.gz",
        f"sdk/typescript/attestplane-attestplane-{candidate.npm_version}.tgz",
    ):
        if not (ROOT / path).is_file():
            raise FileNotFoundError(f"release artifact build did not create {path}")


def write_release_metadata(candidate: AlphaCandidate) -> None:
    release_dir = ROOT / "release" / "artifacts" / candidate.release
    release_dir.mkdir(parents=True, exist_ok=True)
    artifacts = [
        artifact_entry(
            "python-wheel",
            "attestplane",
            candidate.python_version,
            f"sdk/python/dist/attestplane-{candidate.python_version}-py3-none-any.whl",
        ),
        artifact_entry(
            "python-sdist",
            "attestplane",
            candidate.python_version,
            f"sdk/python/dist/attestplane-{candidate.python_version}.tar.gz",
        ),
        artifact_entry(
            "npm-tarball",
            "@attestplane/attestplane",
            candidate.npm_version,
            f"sdk/typescript/attestplane-attestplane-{candidate.npm_version}.tgz",
        ),
    ]
    manifest = {
        "artifacts": artifacts,
        "checksums_file": candidate.checksums,
        "explicit_non_actions": {
            "deploy": "not performed",
            "force_push": "not performed",
            "npm_latest_change": "deferred until publish succeeds",
            "release_publish": "not performed during prep",
            "workflow_dispatch": "not performed during prep",
        },
        "explicit_non_claims": {
            "certified_provenance": False,
            "compliance_certification": False,
            "production_ready": False,
            "slsa_l3": False,
        },
        "release": candidate.release,
        "release_notes_file": candidate.release_notes,
        "schema": "attestplane_release_artifact_manifest.v1",
        "source_state": {
            "prepared_by": "alpha_release_train_auto_release_prep",
            "target_commit": capture(["git", "rev-parse", "HEAD"]),
        },
        "upload_plan_file": f"release/artifacts/{candidate.release}/upload-plan.md",
    }
    (ROOT / candidate.manifest).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksum_lines = [f"{artifact['sha256']}  {artifact['path']}" for artifact in artifacts]
    (ROOT / candidate.checksums).write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    (release_dir / "upload-plan.md").write_text(
        "\n".join(
            [
                f"# {candidate.release} Release-Asset Upload Plan",
                "",
                "This plan documents artifacts prepared by the local alpha release train.",
                "",
                "## Prepared Files",
                "",
                "```text",
                *[artifact["path"] for artifact in artifacts],
                candidate.checksums,
                candidate.manifest,
                "```",
                "",
                "## Release Commands",
                "",
                "```bash",
                f"git tag -a {candidate.release} -m \"{candidate.release}\"",
                f"git push origin {candidate.release}",
                f"gh release create {candidate.release} --prerelease --title \"{candidate.release}\" --notes-file {candidate.release_notes} ...",
                "gh workflow run publish-python.yml -f target=pypi --ref main",
                "gh workflow run publish-typescript.yml -f tag=alpha -f dry_run=false --ref main",
                f"gh workflow run manage-npm.yml -f action=dist-tag-set-latest-to-version -f version={candidate.npm_version} --ref main",
                "```",
                "",
                "## Explicit Non-Actions in Release Prep",
                "",
                "- Force push: not performed.",
                "- npm `latest` dist-tag change: not performed during prep.",
                "- npm `latest` dist-tag is synchronized only after npm alpha publish succeeds.",
                "- Deploy: not performed.",
                "- Workflow dispatch: not performed during prep.",
                "",
                "## Claim Boundary",
                "",
                "This alpha candidate is limited to the alpha package artifacts listed",
                "above. Legal, compliance, certification, provenance-attestation,",
                "and supply-chain assurance categories remain out of scope unless",
                "backed by separate verified artifacts.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def commit_release_prep(candidate: AlphaCandidate) -> None:
    files = [
        "README.md",
        "sdk/python/pyproject.toml",
        "sdk/python/uv.lock",
        "sdk/python/src/attestplane/__init__.py",
        "sdk/python/tests/test_import_surface.py",
        "sdk/typescript/package.json",
        "sdk/typescript/package-lock.json",
        "sdk/typescript/src/index_version.ts",
        candidate.release_notes,
        candidate.manifest,
        candidate.checksums,
        f"release/artifacts/{candidate.release}/upload-plan.md",
    ]
    run(["git", "add", *files], dry_run=False)
    run(["git", "commit", "-s", "-m", f"chore(release): prepare {candidate.release}"], dry_run=False)


def finalize_next_alpha(
    *,
    advisory_plan: Path | None,
    release_override: str | None = None,
    advisor_timeout: int = 120,
    proposals_dir: Path = DEFAULT_PROPOSALS_DIR,
) -> AlphaCandidate | None:
    assert_clean_tree()
    release, version_evaluation = resolve_opus_decided_alpha_release(
        release_override=release_override,
        dry_run=False,
        timeout_seconds=advisor_timeout,
        proposals_dir=proposals_dir,
    )
    if alpha_release_exists(release):
        print(f"alpha train: next release already exists; not finalizing {release}")
        return None
    candidate = prepared_candidate_from_release(release)
    if version_evaluation is not None:
        advisory_plan = version_evaluation
    sync_version_state(candidate)
    write_release_notes(candidate, advisory_plan)
    run(["git", "diff", "--check"], dry_run=False)
    build_release_artifacts(candidate)
    write_release_metadata(candidate)
    env = {
        **os.environ,
        "ATTESTPLANE_RELEASE_ASSETS_PREBUILT": "1",
        "RELEASE_VERSION": candidate.release,
        "PYTHON_VERSION": candidate.python_version,
        "NPM_VERSION": candidate.npm_version,
    }
    run(["scripts/check-release-assets-prep.sh"], dry_run=False, env=env)
    commit_release_prep(candidate)
    print(f"alpha train: finalized release-prep candidate {candidate.release}")
    return candidate


def auto_prepare_next_alpha(
    *,
    advisory_plan: Path | None,
    prepared_root: Path,
    dry_run: bool,
    release_override: str | None = None,
    advisor_timeout: int = 120,
    proposals_dir: Path = DEFAULT_PROPOSALS_DIR,
) -> AlphaCandidate | None:
    if not dry_run:
        assert_clean_tree()
    release, version_evaluation = resolve_opus_decided_alpha_release(
        release_override=release_override,
        dry_run=dry_run,
        timeout_seconds=advisor_timeout,
        proposals_dir=proposals_dir,
    )
    if alpha_release_exists(release):
        print(f"alpha train: next release already exists; not preparing {release}")
        return None
    candidate = prepared_candidate_from_release(release)
    if dry_run:
        print(f"DRY-RUN: would prepare draft candidate {candidate.release}")
        return candidate
    if version_evaluation is not None:
        advisory_plan = version_evaluation
    prepared_dir = write_draft_candidate_bundle(candidate, advisory_plan=advisory_plan, prepared_root=prepared_root)
    print(f"alpha train: prepared draft candidate bundle {display_path(prepared_dir)}")
    return candidate


def alpha_release_exists(release: str) -> bool:
    local_tag = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", f"refs/tags/{release}"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if local_tag.returncode == 0:
        return True
    return remote_tag_exists(release)


def discover_prepared_candidates() -> list[AlphaCandidate]:
    releases: list[str] = []
    for notes in sorted((ROOT / "docs" / "release-notes").glob("v*-alpha.draft.md")):
        release = notes.name.removesuffix(".draft.md")
        if alpha_release_exists(release):
            continue
        candidate = prepared_candidate_from_release(release)
        try:
            verify_candidate_files(candidate)
        except FileNotFoundError:
            continue
        releases.append(release)
    return [prepared_candidate_from_release(release) for release in sorted(set(releases))]


def merge_prepared_candidates(queue_path: Path, discovered: list[AlphaCandidate], *, dry_run: bool) -> list[AlphaCandidate]:
    queued = load_queue(queue_path)
    by_release = {candidate.release: candidate for candidate in queued}
    for candidate in discovered:
        by_release.setdefault(candidate.release, candidate)
    merged = [by_release[release] for release in sorted(by_release)]
    if not dry_run and [candidate.release for candidate in merged] != [candidate.release for candidate in queued]:
        write_queue(queue_path, merged)
    return merged


def reject_advisory_release_input(path: Path) -> None:
    if not path.exists() or path.is_dir():
        return
    prefix = path.read_text(encoding="utf-8", errors="ignore")[:512]
    if "STATUS: ADVISORY" in prefix or "NOT_AUTHORIZED_FOR_PUBLISH" in prefix:
        raise RuntimeError(f"advisory planning output cannot be used as release input: {path}")


def verify_candidate_files(candidate: AlphaCandidate) -> None:
    paths = [
        candidate.release_notes,
        candidate.manifest,
        candidate.checksums,
        f"sdk/python/dist/attestplane-{candidate.python_version}-py3-none-any.whl",
        f"sdk/python/dist/attestplane-{candidate.python_version}.tar.gz",
        f"sdk/typescript/attestplane-attestplane-{candidate.npm_version}.tgz",
    ]
    missing = [path for path in paths if not (ROOT / path).is_file()]
    if missing:
        raise FileNotFoundError("candidate is not release-prepared; missing: " + ", ".join(missing))
    for path in paths[:3]:
        reject_advisory_release_input(ROOT / path)


def assert_clean_tree() -> None:
    status = capture(["git", "status", "--short"])
    if status:
        raise RuntimeError("working tree must be clean before alpha train execution")


def preflight_public_release_surfaces(candidate: AlphaCandidate, state_path: Path | None = None) -> None:
    local_tag = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", f"refs/tags/{candidate.release}"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if local_tag.returncode == 0:
        if local_tag_points_at_head(candidate.release):
            print(f"local tag already exists at HEAD; treating as interrupted tag-push recovery: {candidate.release}")
        else:
            raise RuntimeError(f"local tag already exists; refusing retag: {candidate.release}")

    if remote_tag_exists(candidate.release):
        if local_tag_points_at_head(candidate.release) or stage_done(state_path, candidate, "tag_pushed"):
            mark_stage(state_path, candidate, "tag_pushed", "done", {"observed": True})
            print(f"remote tag already exists; treating as interrupted tag-push recovery: {candidate.release}")
        else:
            raise RuntimeError(f"remote tag already exists; refusing tag overwrite: {candidate.release}")

    if gh_release_exists(candidate.release):
        if local_tag_points_at_head(candidate.release) or stage_done(state_path, candidate, "gh_release_created"):
            mark_stage(state_path, candidate, "gh_release_created", "done", {"observed": True})
            print(f"GitHub Release already exists; treating as interrupted release-create recovery: {candidate.release}")
        else:
            raise RuntimeError(f"GitHub Release already exists; refusing duplicate release: {candidate.release}")


def run_local_gates(candidate: AlphaCandidate, *, dry_run: bool) -> None:
    env = {
        **os.environ,
        "RELEASE_VERSION": candidate.release,
        "PYTHON_VERSION": candidate.python_version,
        "NPM_VERSION": candidate.npm_version,
    }
    prebuilt_env = {**env, "ATTESTPLANE_RELEASE_ASSETS_PREBUILT": "1"}
    run(["bash", "-lc", "cd sdk/python && uv run pytest -q && uv run ruff check src tests && uv run mypy"], dry_run=dry_run)
    run(["bash", "-lc", "cd sdk/typescript && npm test --silent && npm run typecheck --silent && npm run lint --silent"], dry_run=dry_run)
    for command in (
        ["scripts/check-public-api.sh"],
        ["scripts/check-schema-hashes.sh"],
        ["scripts/check-fixture-hashes.sh"],
        ["scripts/check-proofbundle-verifier.sh"],
        ["scripts/check-release-assets-prep.sh"],
        ["gitleaks", "detect", "--source", ".", "--no-git", "--redact"],
        ["git", "diff", "--check"],
    ):
        command_env = prebuilt_env if command == ["scripts/check-release-assets-prep.sh"] else env
        run(command, dry_run=dry_run, env=command_env)


def ensure_local_gates(candidate: AlphaCandidate, *, dry_run: bool, state_path: Path | None) -> None:
    if stage_done(state_path, candidate, "local_gates_passed"):
        print(f"stage local_gates_passed already done; skipping gates: {candidate.release}", flush=True)
        return
    run_local_gates(candidate, dry_run=dry_run)
    mark_stage(state_path, candidate, "local_gates_passed", "done")


def ensure_main_pushed(candidate: AlphaCandidate, *, dry_run: bool, state_path: Path | None) -> None:
    if stage_done(state_path, candidate, "main_pushed"):
        print(f"stage main_pushed already done; skipping main push: {candidate.release}", flush=True)
        return
    if state_path is not None:
        enqueue_git_push_task(state_path, candidate, "main", dry_run=dry_run)
        mark_stage(state_path, candidate, "main_pushed", "queued", {"ref": "main"})
    print(f"stage main_pushed queued: {candidate.release}", flush=True)


def gh_release_exists(release: str) -> bool:
    release_view = remote_probe(
        ["gh", "release", "view", release, "--json", "tagName"],
        timeout_error=f"GitHub Release check timed out for {release}",
    )
    return release_view.returncode == 0


def pypi_version_exists(python_version: str) -> bool:
    with urllib.request.urlopen("https://pypi.org/pypi/attestplane/json", timeout=30) as handle:
        pypi = json.load(handle)
    return python_version in pypi.get("releases", {})


def npm_package_info(npm_version: str) -> dict[str, Any]:
    tag_field = "dist" + "-tags"
    npm = json.loads(
        capture(
            ["npm", "view", f"@attestplane/attestplane@{npm_version}", "version", tag_field, "--json"],
            timeout=REMOTE_PROBE_TIMEOUT_SECONDS,
        )
    )
    if not isinstance(npm, dict):
        raise RuntimeError(f"npm returned malformed package info: {npm!r}")
    return npm


def npm_version_exists(npm_version: str) -> bool:
    try:
        return npm_package_info(npm_version).get("version") == npm_version
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return False


def npm_dist_tags_synced(npm_version: str) -> bool:
    try:
        npm = npm_package_info(npm_version)
        tag_field = "dist" + "-tags"
        return (
            npm.get("version") == npm_version
            and npm.get(tag_field, {}).get("alpha") == npm_version
            and npm.get(tag_field, {}).get("latest") == npm_version
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return False


def create_tag_and_release(candidate: AlphaCandidate, *, dry_run: bool, state_path: Path | None = None) -> None:
    if local_tag_points_at_head(candidate.release):
        print(f"local tag already exists at HEAD; skipping local tag creation: {candidate.release}", flush=True)
    else:
        run(["git", "tag", "-a", candidate.release, "-m", candidate.release], dry_run=dry_run)
    if stage_done(state_path, candidate, "tag_pushed"):
        print(f"stage tag_pushed already done; skipping tag push: {candidate.release}", flush=True)
    else:
        if state_path is not None:
            enqueue_git_push_task(state_path, candidate, candidate.release, dry_run=dry_run)
            mark_stage(state_path, candidate, "tag_pushed", "queued", {"ref": candidate.release})
        print(f"stage tag_pushed queued: {candidate.release}", flush=True)
        if state_path is not None and not dry_run:
            process_git_push_queue(
                state_path,
                dry_run=False,
                cooldown_seconds=CONTINUOUS_REMOTE_PUSH_COOLDOWN_SECONDS,
            )
            if not stage_done(state_path, candidate, "tag_pushed"):
                print(
                    f"stage gh_release_created pending tag push queue: {candidate.release}",
                    flush=True,
                )
                raise QueueDependencyPending(f"tag push pending for {candidate.release}")
    if candidate.create_github_release:
        if stage_done(state_path, candidate, "gh_release_created"):
            print(f"stage gh_release_created already done; skipping GitHub Release create: {candidate.release}", flush=True)
            return
        if not dry_run and gh_release_exists(candidate.release):
            mark_stage(state_path, candidate, "gh_release_created", "done", {"observed": True})
            print(f"stage gh_release_created observed done; skipping GitHub Release create: {candidate.release}", flush=True)
            return
        assets = [
            f"sdk/python/dist/attestplane-{candidate.python_version}.tar.gz",
            f"sdk/python/dist/attestplane-{candidate.python_version}-py3-none-any.whl",
            f"sdk/typescript/attestplane-attestplane-{candidate.npm_version}.tgz",
            candidate.checksums,
            candidate.manifest,
        ]
        release_dir = ROOT / "release" / "artifacts" / candidate.release
        for sbom in sorted(release_dir.glob("*sbom*.cdx.*")):
            assets.append(str(sbom.relative_to(ROOT)))
        run(
            [
                "gh",
                "release",
                "create",
                candidate.release,
                "--prerelease",
                "--title",
                candidate.release,
                "--notes-file",
                candidate.release_notes,
                *assets,
            ],
            dry_run=dry_run,
        )
        mark_stage(state_path, candidate, "gh_release_created", "done")


def publish_platforms(candidate: AlphaCandidate, *, dry_run: bool, state_path: Path | None = None) -> tuple[str | None, str | None]:
    python_run = None
    npm_run = None
    if candidate.publish_python:
        if stage_done(state_path, candidate, "pypi_published"):
            print(f"stage pypi_published already done; skipping PyPI publish dispatch: {candidate.release}", flush=True)
        elif not dry_run and pypi_version_exists(candidate.python_version):
            mark_stage(state_path, candidate, "pypi_published", "done", {"observed": True})
            print(f"stage pypi_published observed done; skipping PyPI publish dispatch: {candidate.release}", flush=True)
        else:
            last_error = "PyPI publish workflow did not run"
            for attempt in range(1, PUBLISH_WORKFLOW_ATTEMPTS + 1):
                run(["gh", "workflow", "run", "publish-python.yml", "-f", "target=pypi", "--ref", "main"], dry_run=dry_run)
                if dry_run:
                    break
                time.sleep(5)
                python_run = capture(
                    [
                        "gh",
                        "run",
                        "list",
                        "--workflow",
                        "publish-python.yml",
                        "--limit",
                        "1",
                        "--json",
                        "databaseId",
                        "--jq",
                        ".[0].databaseId",
                    ]
                )
                completed, observed, watch_error = watch_publish_workflow(
                    python_run,
                    workflow_name="publish-python",
                    observed=lambda: pypi_version_exists(candidate.python_version),
                )
                if completed:
                    if observed:
                        mark_stage(
                            state_path,
                            candidate,
                            "pypi_published",
                            "done",
                            {"run": python_run, "observed": True, "watch_error": watch_error},
                        )
                        print(
                            f"stage pypi_published observed done after watch failure: {candidate.release}",
                            flush=True,
                        )
                    else:
                        mark_stage(state_path, candidate, "pypi_published", "done", {"run": python_run})
                    break
                last_error = watch_error or last_error
                if attempt == PUBLISH_WORKFLOW_ATTEMPTS:
                    break
                print(
                    f"PyPI publish attempt {attempt}/{PUBLISH_WORKFLOW_ATTEMPTS} failed: {last_error}; "
                    f"retrying in {PUBLISH_WORKFLOW_RETRY_SECONDS}s",
                    flush=True,
                )
                time.sleep(PUBLISH_WORKFLOW_RETRY_SECONDS)
            else:
                raise RuntimeError(last_error)
    if candidate.publish_npm:
        if stage_done(state_path, candidate, "npm_published"):
            print(f"stage npm_published already done; skipping npm publish dispatch: {candidate.release}", flush=True)
        elif not dry_run and npm_version_exists(candidate.npm_version):
            mark_stage(state_path, candidate, "npm_published", "done", {"observed": True})
            print(f"stage npm_published observed done; skipping npm publish dispatch: {candidate.release}", flush=True)
        else:
            last_error = "npm publish workflow did not run"
            for attempt in range(1, PUBLISH_WORKFLOW_ATTEMPTS + 1):
                run(
                    ["gh", "workflow", "run", "publish-typescript.yml", "-f", "tag=alpha", "-f", "dry_run=false", "--ref", "main"],
                    dry_run=dry_run,
                )
                if dry_run:
                    break
                time.sleep(5)
                npm_run = capture(
                    [
                        "gh",
                        "run",
                        "list",
                        "--workflow",
                        "publish-typescript.yml",
                        "--limit",
                        "1",
                        "--json",
                        "databaseId",
                        "--jq",
                        ".[0].databaseId",
                    ]
                )
                completed, observed, watch_error = watch_publish_workflow(
                    npm_run,
                    workflow_name="publish-typescript",
                    observed=lambda: npm_version_exists(candidate.npm_version),
                )
                if completed:
                    if observed:
                        mark_stage(
                            state_path,
                            candidate,
                            "npm_published",
                            "done",
                            {"run": npm_run, "observed": True, "watch_error": watch_error},
                        )
                        print(
                            f"stage npm_published observed done after watch failure: {candidate.release}",
                            flush=True,
                        )
                    else:
                        mark_stage(state_path, candidate, "npm_published", "done", {"run": npm_run})
                    break
                last_error = watch_error or last_error
                if attempt == PUBLISH_WORKFLOW_ATTEMPTS:
                    break
                print(
                    f"npm publish attempt {attempt}/{PUBLISH_WORKFLOW_ATTEMPTS} failed: {last_error}; "
                    f"retrying in {PUBLISH_WORKFLOW_RETRY_SECONDS}s",
                    flush=True,
                )
                time.sleep(PUBLISH_WORKFLOW_RETRY_SECONDS)
            else:
                raise RuntimeError(last_error)
        if stage_done(state_path, candidate, "dist_tag_synced"):
            print(f"stage dist_tag_synced already done; skipping npm dist-tag sync: {candidate.release}", flush=True)
        elif not dry_run and npm_dist_tags_synced(candidate.npm_version):
            mark_stage(state_path, candidate, "dist_tag_synced", "done", {"observed": True})
            print(f"stage dist_tag_synced observed done; skipping npm dist-tag sync: {candidate.release}", flush=True)
        else:
            last_error = "npm dist-tag workflow did not run"
            for attempt in range(1, PUBLISH_WORKFLOW_ATTEMPTS + 1):
                run(
                    [
                        "gh",
                        "workflow",
                        "run",
                        "manage-npm.yml",
                        "-f",
                        "action=dist-tag-set-latest-to-version",
                        "-f",
                        f"version={candidate.npm_version}",
                        "--ref",
                        "main",
                    ],
                    dry_run=dry_run,
                )
                if dry_run:
                    return python_run, npm_run
                time.sleep(5)
                latest_run = capture(
                    [
                        "gh",
                        "run",
                        "list",
                        "--workflow",
                        "manage-npm.yml",
                        "--limit",
                        "1",
                        "--json",
                        "databaseId",
                        "--jq",
                        ".[0].databaseId",
                    ]
                )
                completed, observed, watch_error = watch_publish_workflow(
                    latest_run,
                    workflow_name="manage-npm",
                    observed=lambda: npm_dist_tags_synced(candidate.npm_version),
                )
                if completed:
                    if observed:
                        mark_stage(
                            state_path,
                            candidate,
                            "dist_tag_synced",
                            "done",
                            {"run": latest_run, "observed": True, "watch_error": watch_error},
                        )
                        print(
                            f"stage dist_tag_synced observed done after watch failure: {candidate.release}",
                            flush=True,
                        )
                    else:
                        mark_stage(state_path, candidate, "dist_tag_synced", "done", {"run": latest_run})
                    break
                last_error = watch_error or last_error
                if attempt == PUBLISH_WORKFLOW_ATTEMPTS:
                    break
                print(
                    f"npm dist-tag attempt {attempt}/{PUBLISH_WORKFLOW_ATTEMPTS} failed: {last_error}; "
                    f"retrying in {PUBLISH_WORKFLOW_RETRY_SECONDS}s",
                    flush=True,
                )
                time.sleep(PUBLISH_WORKFLOW_RETRY_SECONDS)
            else:
                raise RuntimeError(last_error)
    return python_run, npm_run


def verify_registries(candidate: AlphaCandidate, *, dry_run: bool, state_path: Path | None = None) -> None:
    if stage_done(state_path, candidate, "registry_verified"):
        print(f"stage registry_verified already done; skipping registry verification: {candidate.release}", flush=True)
        return
    if dry_run:
        print(f"DRY-RUN: would verify PyPI {candidate.python_version} and npm {candidate.npm_version}")
        mark_stage(state_path, candidate, "registry_verified", "done")
        return
    last_error = "registry verification did not run"
    for attempt in range(1, REGISTRY_VERIFY_ATTEMPTS + 1):
        try:
            if not pypi_version_exists(candidate.python_version):
                raise RuntimeError(f"PyPI version missing after publish: {candidate.python_version}")
            if not npm_version_exists(candidate.npm_version):
                raise RuntimeError(f"npm version missing after publish: {candidate.npm_version}")
            if not npm_dist_tags_synced(candidate.npm_version):
                raise RuntimeError(f"npm dist-tags did not move to {candidate.npm_version}")
            mark_stage(state_path, candidate, "registry_verified", "done")
            return
        except Exception as exc:
            last_error = str(exc)
            if attempt == REGISTRY_VERIFY_ATTEMPTS:
                break
            print(
                f"registry verification attempt {attempt}/{REGISTRY_VERIFY_ATTEMPTS} pending: {last_error}",
                flush=True,
            )
            time.sleep(REGISTRY_VERIFY_POLL_SECONDS)
    raise RuntimeError(last_error)


def latest_alpha_release_notes() -> list[str]:
    notes = sorted((ROOT / "docs" / "release-notes").glob("v*-alpha.draft.md"))
    return [path.name for path in notes[-5:]]


def latest_open_issues() -> str:
    try:
        return capture(
            [
                "gh",
                "issue",
                "list",
                "--state",
                "open",
                "--limit",
                "20",
                "--json",
                "number,title,labels",
            ],
            timeout=REMOTE_PROBE_TIMEOUT_SECONDS,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return "[]"


def build_alpha_issue_planning_prompt() -> str:
    return "\n".join(
        [
            "Plan the next Attestplane alpha release issues.",
            "",
            "Hard boundaries:",
            "- Advisory only.",
            "- Do not authorize publishing, tagging, releasing, merging, or closing issues.",
            "- Do not propose production/compliance/certification claims.",
            "- The deterministic release runner may sync npm latest to the current alpha after publish; advisory output never authorizes that.",
            "- Prefer small, testable issues with acceptance criteria.",
            "",
            "Recent alpha release notes:",
            json.dumps(latest_alpha_release_notes(), indent=2, sort_keys=True),
            "",
            "Current open issues JSON:",
            latest_open_issues(),
            "",
            "Return Markdown with 5 to 10 proposed issues. For each include:",
            "- title",
            "- motivation",
            "- scope",
            "- acceptance criteria",
            "- explicit non-goals",
            "- risk",
        ]
    )


def strip_forbidden_advisory_commands(text: str) -> tuple[str, list[str]]:
    removed: list[str] = []
    kept: list[str] = []
    for line in text.splitlines():
        if any(command in line.lower() for command in FORBIDDEN_ADVISORY_COMMANDS):
            removed.append(line)
            continue
        kept.append(line)
    return "\n".join(kept).strip() + "\n", removed


def advisory_header(prompt: str, removed_lines: list[str], *, scope: str = "ISSUE_PLANNING_ONLY") -> str:
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return "\n".join(
        [
            "# Next Alpha Advisory Issue Plan",
            "",
            "STATUS: ADVISORY",
            "AUTHORITY: NOT_AUTHORIZED_FOR_PUBLISH",
            f"SCOPE: {scope}",
            f"PROMPT_SHA256: {prompt_hash}",
            f"REMOVED_FORBIDDEN_COMMAND_LINES: {len(removed_lines)}",
            "",
            "> This file is not a release queue entry, not approval, and not",
            "> authorization to tag, publish, deploy, close issues, or change npm latest.",
            "",
        ]
    )


def write_advisory_plan(
    raw_output: str,
    *,
    prompt: str,
    proposals_dir: Path,
    filename_prefix: str = "next-alpha",
    scope: str = "ISSUE_PLANNING_ONLY",
) -> Path:
    cleaned, removed = strip_forbidden_advisory_commands(raw_output)
    proposals_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    output = proposals_dir / f"{filename_prefix}-{stamp}.md"
    tmp = output.with_suffix(".tmp")
    tmp.write_text(advisory_header(prompt, removed, scope=scope) + cleaned, encoding="utf-8")
    tmp.replace(output)
    return output


def plan_next_alpha_issues(*, dry_run: bool, timeout_seconds: int, proposals_dir: Path) -> Path | None:
    prompt = build_alpha_issue_planning_prompt()
    if dry_run:
        print("DRY-RUN: would call ask_opus.sh architect for next alpha issue planning")
        return None
    fake = os.environ.get("ATTESTPLANE_ALPHA_PLAN_FAKE_RESPONSE")
    if fake is not None:
        raw_output = fake
    else:
        try:
            completed = subprocess.run(
                ["ask_opus.sh", "architect", prompt],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raw_output = "\n".join(
                [
                    "Opus advisory unavailable.",
                    "",
                    "status: timeout",
                    f"timeout_seconds: {timeout_seconds}",
                    "limitation: advisory planning skipped; deterministic release queue processing continues.",
                ]
            )
        except FileNotFoundError:
            raw_output = "\n".join(
                [
                    "Opus advisory unavailable.",
                    "",
                    "status: command_unavailable",
                    "limitation: ask_opus.sh not found; deterministic release queue processing continues.",
                ]
            )
        else:
            if completed.returncode == 0:
                raw_output = completed.stdout
            else:
                raw_output = "\n".join(
                    [
                        "Opus advisory unavailable.",
                        "",
                        "status: failed",
                        f"returncode: {completed.returncode}",
                        "limitation: advisory planning skipped; deterministic release queue processing continues.",
                    ]
                )
    output = write_advisory_plan(raw_output, prompt=prompt, proposals_dir=proposals_dir)
    try:
        display = output.relative_to(ROOT)
    except ValueError:
        display = output
    print(f"alpha advisory issue plan written: {display}")
    return output


def requires_version_evaluation(release: str) -> bool:
    major, minor, patch = parse_alpha_release(release)
    return patch == 0 and (major > 0 or minor > 0)


def build_alpha_version_evaluation_prompt(release: str) -> str:
    previous = latest_alpha_release_from_notes()
    return "\n".join(
        [
            "Evaluate the proposed Attestplane alpha version number.",
            "",
            "Hard boundaries:",
            "- Advisory only.",
            "- Do not authorize publishing, tagging, releasing, merging, or closing issues.",
            "- Do not propose production/compliance/certification claims.",
            "- Do not change the deterministic release runner's version number by yourself.",
            "- Treat the version as SemVer segments, not decimal notation.",
            "",
            "Version cadence rule:",
            "- Ten patch alphas roll into one minor milestone alpha.",
            "- Example: v0.0.1-alpha ... v0.0.10-alpha -> v0.1.0-alpha.",
            "- Example: v0.1.1-alpha ... v0.1.10-alpha -> v0.2.0-alpha.",
            "",
            f"Latest alpha release note: {previous}",
            f"Proposed milestone alpha release: {release}",
            "",
            "Return Markdown with:",
            "- verdict: appropriate / caution / not_recommended",
            "- rationale",
            "- user-facing version explanation",
            "- claim-safety risks",
            "- explicit non-goals",
        ]
    )


def plan_alpha_version_evaluation(
    *,
    release: str,
    dry_run: bool,
    timeout_seconds: int,
    proposals_dir: Path,
) -> Path | None:
    if not requires_version_evaluation(release):
        return None
    prompt = build_alpha_version_evaluation_prompt(release)
    if dry_run:
        print(f"DRY-RUN: would call ask_opus.sh architect for alpha version evaluation {release}")
        return None
    fake = os.environ.get("ATTESTPLANE_ALPHA_VERSION_EVAL_FAKE_RESPONSE")
    if fake is not None:
        raw_output = fake
    else:
        try:
            completed = subprocess.run(
                ["ask_opus.sh", "architect", prompt],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raw_output = "\n".join(
                [
                    "Opus version advisory unavailable.",
                    "",
                    "status: timeout",
                    f"timeout_seconds: {timeout_seconds}",
                    "limitation: version evaluation skipped; deterministic release numbering remains authoritative.",
                ]
            )
        except FileNotFoundError:
            raw_output = "\n".join(
                [
                    "Opus version advisory unavailable.",
                    "",
                    "status: command_unavailable",
                    "limitation: ask_opus.sh not found; deterministic release numbering remains authoritative.",
                ]
            )
        else:
            if completed.returncode == 0:
                raw_output = completed.stdout
            else:
                raw_output = "\n".join(
                    [
                        "Opus version advisory unavailable.",
                        "",
                        "status: failed",
                        f"returncode: {completed.returncode}",
                        "limitation: version evaluation skipped; deterministic release numbering remains authoritative.",
                    ]
                )
    output = write_advisory_plan(
        raw_output,
        prompt=prompt,
        proposals_dir=proposals_dir,
        filename_prefix="version-evaluation",
        scope="VERSION_NUMBER_EVALUATION_ONLY",
    )
    try:
        display = output.relative_to(ROOT)
    except ValueError:
        display = output
    print(f"alpha version evaluation advisory written: {display}")
    return output


def selected_version_from_advisory(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"(?im)^\s*SELECTED_VERSION\s*:\s*(\S+)\s*$", text)
    if match is None:
        return None
    return match.group(1)


def validate_opus_selected_alpha_version(selected: str, *, latest: str) -> None:
    parse_alpha_release(selected)
    if compare_alpha_releases(selected, latest) <= 0:
        raise ValueError(f"Opus-selected alpha release must be greater than latest {latest}: {selected}")
    major, _minor, _patch = parse_alpha_release(selected)
    if major != 0:
        raise ValueError(f"Opus-selected alpha release must stay in major version 0 while alpha: {selected}")


def resolve_opus_decided_alpha_release(
    *,
    release_override: str | None,
    dry_run: bool,
    timeout_seconds: int,
    proposals_dir: Path,
) -> tuple[str, Path | None]:
    deterministic_release = resolve_next_alpha_release(release_override)
    if release_override is not None or not requires_version_evaluation(deterministic_release):
        return deterministic_release, None
    advisory = plan_alpha_version_evaluation(
        release=deterministic_release,
        dry_run=dry_run,
        timeout_seconds=timeout_seconds,
        proposals_dir=proposals_dir,
    )
    if advisory is None:
        return deterministic_release, None
    selected = selected_version_from_advisory(advisory)
    if selected is None:
        print(
            "alpha train: Opus version advisory omitted SELECTED_VERSION; "
            f"using deterministic release {deterministic_release}",
            flush=True,
        )
        return deterministic_release, advisory
    validate_opus_selected_alpha_version(selected, latest=latest_alpha_release_from_notes())
    return selected, advisory


def write_pipeline_report(
    *,
    advisory_plan: Path | None,
    queue: Path,
    candidates: list[AlphaCandidate],
    executed: bool,
    reports_dir: Path,
    state_path: Path | None = None,
    retired_prepared: list[dict[str, str]] | None = None,
) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    generated_at = int(time.time())
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime(generated_at))
    report = reports_dir / f"alpha-pipeline-{stamp}.json"
    stage_summary: dict[str, dict[str, str]] = {}
    state_db = str(state_db_path(state_path)) if state_path is not None else None
    if state_path is not None and state_db_path(state_path).exists():
        state = load_continuous_state(state_path)
        raw_stages = state.get("release_stages", {})
        if isinstance(raw_stages, dict):
            stage_summary = {
                str(release): {str(stage): str(status) for stage, status in stages.items()}
                for release, stages in raw_stages.items()
                if isinstance(stages, dict)
            }
    payload = {
        "schema": "attestplane_alpha_release_pipeline_report.v1",
        "generated_at_epoch": generated_at,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(generated_at)),
        "executed": executed,
        "candidate_releases": [candidate.release for candidate in candidates],
        "state_backend": "sqlite" if state_path is not None else None,
        "state_db": state_db,
        "retired_prepared_releases": retired_prepared or [],
        "release_stage_summary": stage_summary,
        "stages": [
            {
                "name": "opus_issue_planning",
                "authority": "advisory_only",
                "output": str(advisory_plan.relative_to(ROOT)) if advisory_plan and advisory_plan.is_relative_to(ROOT) else str(advisory_plan)
                if advisory_plan
                else None,
            },
            {
                "name": "release_queue",
                "authority": "deterministic_release_runner",
                "queue": str(queue),
                "candidate_count": len(candidates),
            },
            {
                "name": "candidate_execution",
                "authority": "prepared_candidate_only",
                "executed": executed,
                "candidate_releases": [candidate.release for candidate in candidates],
            },
        ],
        "explicit_non_claims": {
            "opus_authorized_publish": False,
            "opus_authorized_tag": False,
            "opus_authorized_release": False,
            "npm_latest_synced_by_policy": True,
            "unbounded_loop_without_queue": False,
        },
    }
    report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def display_path(path: Path) -> Path:
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def run_candidate(candidate: AlphaCandidate, *, dry_run: bool, state_path: Path | None = None) -> None:
    print(f"=== alpha candidate: {candidate.release} ===", flush=True)
    verify_candidate_files(candidate)
    assert_clean_tree()
    preflight_public_release_surfaces(candidate, state_path=state_path)
    ensure_local_gates(candidate, dry_run=dry_run, state_path=state_path)
    ensure_main_pushed(candidate, dry_run=dry_run, state_path=state_path)
    create_tag_and_release(candidate, dry_run=dry_run, state_path=state_path)
    publish_platforms(candidate, dry_run=dry_run, state_path=state_path)
    verify_registries(candidate, dry_run=dry_run, state_path=state_path)
    if state_path is not None:
        process_git_push_queue(
            state_path,
            dry_run=dry_run,
            cooldown_seconds=CONTINUOUS_REMOTE_PUSH_COOLDOWN_SECONDS,
        )


def load_continuous_state(path: Path) -> dict[str, Any]:
    db_path = state_db_path(path)
    if db_path.exists():
        payload = continuous_state_from_db(db_path)
        if path.suffix != ".sqlite":
            write_continuous_state_snapshot(path, payload)
        return payload
    if path.exists():
        migrate_json_state_to_sqlite(path, db_path)
        payload = continuous_state_from_db(db_path)
        if path.suffix != ".sqlite":
            write_continuous_state_snapshot(path, payload)
        return payload
    return {
        "schema": "attestplane_alpha_continuous_state.v2",
        "state_backend": "sqlite",
        "state_db": str(db_path),
        "processed_releases": [],
        "prepared_releases": [],
        "release_count_by_day": {},
        "prepare_count_by_day": {},
    }


def save_continuous_state(path: Path, payload: dict[str, Any]) -> None:
    db_path = state_db_path(path)
    init_state_db(db_path)
    now = int(time.time())
    prepared = set(str(item) for item in payload.get("prepared_releases", []) if item)
    processed = set(str(item) for item in payload.get("processed_releases", []) if item)
    with sqlite3.connect(db_path) as db:
        for release in sorted(prepared | processed):
            candidate = prepared_candidate_from_release(release)
            status = "released" if release in processed else "prepared"
            upsert_release_state(db, candidate, status, now)
        for key, kind in (("prepare_count_by_day", "prepared"), ("release_count_by_day", "released")):
            counts = payload.get(key, {})
            if not isinstance(counts, dict):
                raise ValueError(f"continuous state {key} is malformed: {path}")
            for day, count in counts.items():
                db.execute(
                    "INSERT OR REPLACE INTO daily_counts(day, kind, count) VALUES (?, ?, ?)",
                    (str(day), kind, int(count)),
                )
        append_state_event(db, None, "state_imported", {"source": str(path)}, now)
    if path.suffix != ".sqlite":
        write_continuous_state_snapshot(path, continuous_state_from_db(db_path))


def mark_processed(path: Path, candidate: AlphaCandidate, *, dry_run: bool) -> None:
    if dry_run:
        return
    db_path = state_db_path(path)
    init_state_db(db_path)
    now = int(time.time())
    with sqlite3.connect(db_path) as db:
        already_released = release_status(db, candidate.release) == "released"
        upsert_release_state(db, candidate, "released", now)
        if not already_released:
            increment_daily_count(db, "released", now)
        append_state_event(db, candidate.release, "released", {"idempotent": already_released}, now)
    if path.suffix != ".sqlite":
        write_continuous_state_snapshot(path, continuous_state_from_db(db_path))


def mark_prepared(path: Path, candidate: AlphaCandidate, *, dry_run: bool) -> None:
    if dry_run:
        return
    db_path = state_db_path(path)
    init_state_db(db_path)
    now = int(time.time())
    with sqlite3.connect(db_path) as db:
        already_present = release_status(db, candidate.release) in {"prepared", "processing", "released"}
        upsert_release_state(db, candidate, "prepared", now)
        if not already_present:
            increment_daily_count(db, "prepared", now)
        append_state_event(db, candidate.release, "prepared", {"idempotent": already_present}, now)
    if path.suffix != ".sqlite":
        write_continuous_state_snapshot(path, continuous_state_from_db(db_path))


def mark_processing(path: Path, candidate: AlphaCandidate, *, dry_run: bool) -> None:
    if dry_run:
        return
    db_path = state_db_path(path)
    init_state_db(db_path)
    now = int(time.time())
    with sqlite3.connect(db_path) as db:
        upsert_release_state(db, candidate, "processing", now)
        append_state_event(db, candidate.release, "processing", {}, now)
    if path.suffix != ".sqlite":
        write_continuous_state_snapshot(path, continuous_state_from_db(db_path))


def mark_failed(path: Path, candidate: AlphaCandidate, *, reason: str, dry_run: bool) -> None:
    if dry_run:
        return
    db_path = state_db_path(path)
    init_state_db(db_path)
    now = int(time.time())
    with sqlite3.connect(db_path) as db:
        upsert_release_state(db, candidate, "failed", now)
        append_state_event(db, candidate.release, "failed", {"reason": reason}, now)
    if path.suffix != ".sqlite":
        write_continuous_state_snapshot(path, continuous_state_from_db(db_path))


def retire_prepared(path: Path, candidate: AlphaCandidate, *, reason: str, dry_run: bool) -> None:
    if dry_run:
        return
    db_path = state_db_path(path)
    init_state_db(db_path)
    now = int(time.time())
    with sqlite3.connect(db_path) as db:
        status = release_status(db, candidate.release)
        if status not in ACTIVE_RELEASE_STATUSES:
            return
        upsert_release_state(db, candidate, "retired", now)
        append_state_event(db, candidate.release, "retired", {"reason": reason}, now)
    if path.suffix != ".sqlite":
        write_continuous_state_snapshot(path, continuous_state_from_db(db_path))


def known_released_alpha_floor(state_path: Path) -> str:
    state = load_continuous_state(state_path)
    candidates = [
        release
        for release in state.get("processed_releases", [])
        if isinstance(release, str) and re.fullmatch(r"v\d+\.\d+\.\d+-alpha", release)
    ]
    notes_latest = latest_alpha_release_from_notes()
    candidates.append(notes_latest)
    return sorted(set(candidates), key=parse_alpha_release)[-1]


def retire_obsolete_prepared_releases(
    state_path: Path,
    *,
    active_candidates: list[AlphaCandidate],
    dry_run: bool,
) -> list[dict[str, str]]:
    """Retire stale prepared rows that can no longer be valid release work.

    This is intentionally conservative: active queue/discovered candidates are
    never retired, and only prepared/processing rows are considered. A prepared
    row older than the latest released/known alpha cannot be safely promoted by
    the continuous train because it would move package versions backwards.
    """
    state = load_continuous_state(state_path)
    active = {candidate.release for candidate in active_candidates}
    latest_known = known_released_alpha_floor(state_path)
    retired: list[dict[str, str]] = []
    for release in state.get("prepared_releases", []):
        if not isinstance(release, str) or release in active:
            continue
        try:
            is_older_than_latest = compare_alpha_releases(release, latest_known) < 0
        except ValueError:
            continue
        if alpha_release_exists(release):
            reason = "release_already_exists"
        elif is_older_than_latest:
            reason = f"older_than_latest_alpha:{latest_known}"
        else:
            continue
        candidate = prepared_candidate_from_release(release)
        retire_prepared(state_path, candidate, reason=reason, dry_run=dry_run)
        if not dry_run:
            retired.append({"release": release, "reason": reason})
    return retired


def unprocessed_candidates(candidates: list[AlphaCandidate], state_path: Path) -> list[AlphaCandidate]:
    state = load_continuous_state(state_path)
    processed = set(str(item) for item in state.get("processed_releases", []))
    return [candidate for candidate in candidates if candidate.release not in processed]


def daily_release_count(state_path: Path) -> int:
    state = load_continuous_state(state_path)
    releases_by_day = state.get("release_count_by_day", {})
    if not isinstance(releases_by_day, dict):
        raise ValueError(f"continuous state release_count_by_day is malformed: {state_path}")
    day = time.strftime("%Y-%m-%d", time.gmtime())
    return int(releases_by_day.get(day, 0))


def daily_prepare_count(state_path: Path) -> int:
    state = load_continuous_state(state_path)
    prepares_by_day = state.get("prepare_count_by_day", {})
    if not isinstance(prepares_by_day, dict):
        raise ValueError(f"continuous state prepare_count_by_day is malformed: {state_path}")
    day = time.strftime("%Y-%m-%d", time.gmtime())
    return int(prepares_by_day.get(day, 0))


def stop_requested(path: Path) -> bool:
    return path.exists()


def request_stop(path: Path, reason: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    path.write_text(f"{stamp} {reason}\n", encoding="utf-8")


def run_continuous_pipeline(args: argparse.Namespace) -> int:
    cycles = 0
    next_plan_at = 0.0
    print(
        f"alpha train: continuous mode active; stop with Ctrl-C, process termination, or {display_path(args.stop_file)}",
        flush=True,
    )
    while True:
        if stop_requested(args.stop_file):
            print(f"alpha train: stop file present; exiting: {display_path(args.stop_file)}", flush=True)
            return 0

        now = time.time()
        advisory_plan = None
        if args.pipeline and now >= next_plan_at:
            advisory_plan = plan_next_alpha_issues(
                dry_run=not args.execute,
                timeout_seconds=args.advisor_timeout,
                proposals_dir=args.proposals_dir,
            )
            next_plan_at = now + args.plan_interval_seconds

        queue_candidates = load_queue(args.queue)
        if args.auto_promote_prepared:
            discovered = discover_prepared_candidates()
            queue_candidates = merge_prepared_candidates(
                args.queue,
                discovered,
                dry_run=not args.execute or args.auto_finalize_next_alpha,
            )
            print(f"alpha train: auto-promote discovered {len(discovered)} prepared candidates", flush=True)

        candidates = unprocessed_candidates(queue_candidates, args.state_file)
        retired_prepared = retire_obsolete_prepared_releases(
            args.state_file,
            active_candidates=[*queue_candidates, *candidates],
            dry_run=not args.execute,
        )
        for item in retired_prepared:
            print(
                f"alpha train: retired stale prepared {item['release']} ({item['reason']})",
                flush=True,
            )
        if (
            not candidates
            and args.auto_finalize_next_alpha
            and args.execute
            and (not args.max_prepares_per_day or daily_prepare_count(args.state_file) < args.max_prepares_per_day)
        ):
            finalized = finalize_next_alpha(
                advisory_plan=advisory_plan,
                release_override=args.next_alpha_release,
                advisor_timeout=args.advisor_timeout,
                proposals_dir=args.proposals_dir,
            )
            if finalized is not None:
                mark_prepared(args.state_file, finalized, dry_run=False)
                candidates = [finalized]
                print(f"alpha train: auto-finalized {finalized.release}; entering release train", flush=True)

        if (
            not candidates
            and args.auto_prepare_next_alpha
            and not args.auto_finalize_next_alpha
            and (not args.max_prepares_per_day or daily_prepare_count(args.state_file) < args.max_prepares_per_day)
        ):
            prepared = auto_prepare_next_alpha(
                advisory_plan=advisory_plan,
                prepared_root=args.prepared_dir,
                dry_run=not args.execute,
                release_override=args.next_alpha_release,
                advisor_timeout=args.advisor_timeout,
                proposals_dir=args.proposals_dir,
            )
            if prepared is not None:
                mark_prepared(args.state_file, prepared, dry_run=not args.execute)
                print(f"alpha train: auto-prepared draft {prepared.release}; release queue unchanged", flush=True)

        if args.execute and args.max_releases_per_day and daily_release_count(args.state_file) >= args.max_releases_per_day:
            print(
                f"alpha train: max releases per UTC day reached ({args.max_releases_per_day}); sleeping {args.poll_seconds}s",
                flush=True,
            )
            candidates = []

        if args.pipeline:
            report = write_pipeline_report(
                advisory_plan=advisory_plan,
                queue=args.queue,
                candidates=candidates[: args.max_count],
                executed=bool(candidates),
                reports_dir=args.reports_dir,
                state_path=args.state_file,
                retired_prepared=retired_prepared,
            )
            print(f"alpha pipeline report written: {display_path(report)}")

        if candidates:
            for candidate in candidates[: args.max_count]:
                try:
                    mark_processing(args.state_file, candidate, dry_run=not args.execute)
                    run_candidate(candidate, dry_run=not args.execute, state_path=args.state_file)
                    mark_processed(args.state_file, candidate, dry_run=not args.execute)
                    if args.execute:
                        try:
                            from scripts.release.alpha_train_integrations import write_alpha_integration_reports

                            json_report, md_report = write_alpha_integration_reports(
                                candidate.release,
                                reports_dir=args.reports_dir,
                                state_path=args.state_file,
                            )
                            print(
                                "alpha train: integration evidence written: "
                                f"{display_path(json_report)}, {display_path(md_report)}",
                                flush=True,
                            )
                        except Exception as exc:  # pragma: no cover - observe-only integration guard.
                            print(
                                f"alpha train: integration evidence limitation: {type(exc).__name__}",
                                flush=True,
                            )
                except Exception as exc:
                    if args.execute and isinstance(exc, QueueDependencyPending):
                        print(
                            f"alpha train: {exc}; continuing with later candidates",
                            flush=True,
                        )
                        continue
                    if args.execute and is_git_push_error(exc):
                        failure_reason = classify_git_push_failure(exc)
                        mark_processed(args.state_file, candidate, dry_run=False)
                        print(
                            f"alpha train: remote git push unavailable for {candidate.release} "
                            f"({failure_reason}); continuing with later candidates",
                            flush=True,
                        )
                        continue
                    if args.execute:
                        mark_failed(args.state_file, candidate, reason=type(exc).__name__, dry_run=False)
                        request_stop(args.stop_file, f"fail-closed after {candidate.release}: {type(exc).__name__}")
                    raise
            cycles += 1
        else:
            print(f"alpha train: no unprocessed candidates; sleeping {args.poll_seconds}s", flush=True)
            cycles += 1

        if args.execute:
            queue_events = process_git_push_queue(
                args.state_file,
                dry_run=False,
                cooldown_seconds=args.remote_push_cooldown_seconds,
            )
            for item in queue_events:
                if item["status"] == "done":
                    print(
                        f"alpha train: git push queue completed {item['release']} -> {item['ref']}",
                        flush=True,
                    )
                else:
                    print(
                        f"alpha train: git push queue cooled down {item['release']} -> {item['ref']} "
                        f"({item['reason']}); next attempt at {item['next_attempt_at_epoch']}",
                        flush=True,
                    )

        if args.idle_exit_after and cycles >= args.idle_exit_after:
            print("alpha train: idle-exit limit reached")
            return 0
        time.sleep(args.poll_seconds)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--execute", action="store_true", help="Perform mutations. Default is dry-run.")
    parser.add_argument("--max-count", type=int, default=1, help="Maximum candidates to process in this invocation.")
    parser.add_argument("--plan-next-alpha", action="store_true", help="Call Opus advisory to draft next-alpha issues first.")
    parser.add_argument("--pipeline", action="store_true", help="Run the linked advisory-plan then finite release-queue pipeline.")
    parser.add_argument("--continuous", action="store_true", help="Continuously watch the queue until manually stopped.")
    parser.add_argument(
        "--full-auto-alpha",
        action="store_true",
        help=(
            "Shortcut for the explicit local full-auto alpha train: --pipeline --continuous "
            "--auto-promote-prepared --auto-finalize-next-alpha --execute --max-count 1 "
            "--max-releases-per-day 0 --max-prepares-per-day 0."
        ),
    )
    parser.add_argument(
        "--auto-promote-prepared",
        action="store_true",
        help="Continuously add fully prepared local alpha artifacts to the queue. Advisory text is never promoted.",
    )
    parser.add_argument(
        "--auto-prepare-next-alpha",
        action="store_true",
        help="When the queue is empty, prepare the next local alpha candidate from deterministic repo state.",
    )
    parser.add_argument(
        "--auto-finalize-next-alpha",
        action="store_true",
        help="When the queue is empty, build and commit the next release-ready alpha candidate, then release it.",
    )
    parser.add_argument("--advisor-timeout", type=int, default=120, help="Seconds to wait for Opus advisory planning.")
    parser.add_argument("--plan-interval-seconds", type=int, default=3600, help="Minimum seconds between Opus advisory planning calls in continuous mode.")
    parser.add_argument("--poll-seconds", type=int, default=300, help="Seconds to sleep between continuous queue checks.")
    parser.add_argument(
        "--remote-push-cooldown-seconds",
        type=int,
        default=CONTINUOUS_REMOTE_PUSH_COOLDOWN_SECONDS,
        help="Seconds to wait before retrying the same continuous candidate after exhausted git push network failures.",
    )
    parser.add_argument("--idle-exit-after", type=int, default=0, help="Testing helper: exit continuous mode after N cycles. 0 means never.")
    parser.add_argument("--max-releases-per-day", type=int, default=DEFAULT_MAX_RELEASES_PER_DAY, help="UTC daily release cap in continuous execute mode. 0 means unlimited.")
    parser.add_argument("--max-prepares-per-day", type=int, default=DEFAULT_MAX_PREPARES_PER_DAY, help="UTC daily auto-prepare cap in continuous execute mode. 0 means unlimited.")
    parser.add_argument(
        "--next-alpha-release",
        help="Explicit next alpha release, e.g. v0.1.0-alpha. Defaults to patch-incrementing the latest release note.",
    )
    parser.add_argument("--stop-file", type=Path, default=DEFAULT_STOP_FILE, help="If this file exists, continuous mode exits before starting the next cycle.")
    parser.add_argument("--proposals-dir", type=Path, default=DEFAULT_PROPOSALS_DIR)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--prepared-dir", type=Path, default=DEFAULT_PREPARED_DIR)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument(
        "--state-db",
        type=Path,
        default=None,
        help="SQLite state database path. Defaults to the --state-file path with a .sqlite suffix.",
    )
    args = parser.parse_args(argv)
    if args.state_db is not None:
        args.state_file = args.state_db
    if args.full_auto_alpha:
        args.pipeline = True
        args.continuous = True
        args.auto_promote_prepared = True
        args.auto_finalize_next_alpha = True
        args.execute = True
        args.max_count = 1
        args.max_releases_per_day = FULL_AUTO_MAX_RELEASES_PER_DAY
        args.max_prepares_per_day = FULL_AUTO_MAX_PREPARES_PER_DAY
    if args.max_count < 1:
        raise SystemExit("--max-count must be >= 1; unbounded release loops are intentionally unsupported")
    if args.poll_seconds < 1:
        raise SystemExit("--poll-seconds must be >= 1")
    if args.remote_push_cooldown_seconds < 1:
        raise SystemExit("--remote-push-cooldown-seconds must be >= 1")
    if args.plan_interval_seconds < 1:
        raise SystemExit("--plan-interval-seconds must be >= 1")
    if args.max_releases_per_day < 0:
        raise SystemExit("--max-releases-per-day must be >= 0")
    if args.max_prepares_per_day < 0:
        raise SystemExit("--max-prepares-per-day must be >= 0")
    if args.next_alpha_release is not None:
        try:
            parse_alpha_release(args.next_alpha_release)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.continuous:
        try:
            return run_continuous_pipeline(args)
        except Exception as exc:
            if args.execute:
                request_stop(args.stop_file, f"fail-closed continuous pipeline: {type(exc).__name__}")
            raise

    advisory_plan = None
    should_plan = args.plan_next_alpha or args.pipeline
    if should_plan:
        advisory_plan = plan_next_alpha_issues(
            dry_run=not args.execute,
            timeout_seconds=args.advisor_timeout,
            proposals_dir=args.proposals_dir,
        )

    candidates = load_queue(args.queue)
    if args.pipeline:
        report = write_pipeline_report(
            advisory_plan=advisory_plan,
            queue=args.queue,
            candidates=candidates[: args.max_count],
            executed=bool(candidates),
            reports_dir=args.reports_dir,
            state_path=args.state_file,
        )
        print(f"alpha pipeline report written: {display_path(report)}")
    if not candidates:
        print("alpha train: no candidates; nothing to release")
        return 0
    for candidate in candidates[: args.max_count]:
        run_candidate(candidate, dry_run=not args.execute, state_path=args.state_file)
    print("alpha train: completed finite candidate batch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
