#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Autodev suffix-free stable release train.

This train advances an explicit seed queue of stable versions such as v0.8.6,
v0.8.7, and v0.9.0, then continues with the same sequence rule:
patch releases advance through .10, the next minor starts at .0, and 0.9.10
promotes to 1.0.0. It
prepares local package artifacts, commits the version bump, creates an
immutable annotated tag, pushes main plus that tag, and delegates publication
to GitHub release-cd.

The stable release pipeline is treated as a deterministic state machine with
the externally observable phases idle -> probe -> sign-wait -> tag -> publish.
The implementation enters probe while it fetches, syncs, and reconciles local
state; enters sign-wait only after the tag has been published and the release-cd
sidecar dispatch is being watched; and then returns to the normal tag/publish
loop on the next cycle.

The train does not force-push, delete tags, publish directly from the local
machine, or move npm ca. Suffix-free stable packages publish through
release-cd with channel=latest, which also means PyPI default installs advance
because PyPI has no dist-tag concept.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import os
import re
import signal
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.observability.events import (
    AUTODEV_TRAIN,
    emit_event as emit_observability_event,
)


ROOT = Path(__file__).resolve().parents[2]
RELEASE_GATE_PATH = ROOT / "scripts" / "release" / "release_gate.py"
STABLE_TAG_RE = re.compile(r"^v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")
DEFAULT_STOP_FILE = ROOT / "release" / "alpha-train" / "STOP"
DEFAULT_TARGET_QUEUE = ROOT / "release" / "autodev-train-targets.json"
DEFAULT_ABANDONED_STABLE_TAGS = ROOT / "release" / "abandoned-stable-tags.json"
DEFAULT_POLL_SECONDS = 300
GIT_HTTP_VERSION = "HTTP/1.1"
# Low-speed cut-off so a stalled curl tunnel (proxy/GFW flake during long
# HTTPS push) bails in ~20s instead of waiting the default 75s before
# `curl 28` fires. Pairs with REMOTE_PUSH_RETRY_SECONDS so a 3-attempt
# cycle finishes in ~70s under a flaky tunnel instead of ~240s.
GIT_HTTP_LOW_SPEED_LIMIT = 1000
GIT_HTTP_LOW_SPEED_TIME = 20
# 500 MB post buffer — fewer chunked-transfer round-trips, less surface
# for the MITM tunnel to drop a chunk mid-push.
GIT_HTTP_POST_BUFFER = 524_288_000
GIT_HTTP_CONFIG_ARGS: tuple[str, ...] = (
    "-c",
    f"http.version={GIT_HTTP_VERSION}",
    "-c",
    f"http.lowSpeedLimit={GIT_HTTP_LOW_SPEED_LIMIT}",
    "-c",
    f"http.lowSpeedTime={GIT_HTTP_LOW_SPEED_TIME}",
    "-c",
    f"http.postBuffer={GIT_HTTP_POST_BUFFER}",
)
REMOTE_PROBE_TIMEOUT_SECONDS = 30
REMOTE_PUSH_ATTEMPTS = 3
REMOTE_PUSH_RETRY_SECONDS = 10
REMOTE_PUSH_TIMEOUT_SECONDS = 120
REMOTE_PROBE_ATTEMPTS = 3
REMOTE_PROBE_BASE_RETRY_SECONDS = 5
GIT_PROXY_MODE_ENV = "ATTESTPLANE_GIT_PROXY_MODE"
GIT_PROXY_URL_ENV = "ATTESTPLANE_GIT_PROXY_URL"
GIT_PROXY_ENV_KEYS = (
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
)
PATCH_ROLLOVER = 10
PUSH_CI_WORKFLOWS = (
    "ci",
    "sdk-python",
    "sdk-typescript",
    "cross-sdk-roundtrip",
    "verifier-conformance",
    "invariants",
    "sbom",
    "reproducible-build",
    "osv-scanner",
    "codeql",
)
PUSH_CI_WORKFLOW_FILES = {
    "ci": "ci.yml",
    "sdk-python": "sdk-python.yml",
    "sdk-typescript": "sdk-typescript.yml",
    "cross-sdk-roundtrip": "cross-sdk-roundtrip.yml",
    "verifier-conformance": "verifier-conformance.yml",
    "invariants": "invariants.yml",
    "sbom": "sbom.yml",
    "reproducible-build": "reproducible-build.yml",
    "osv-scanner": "osv-scanner.yml",
    "codeql": "codeql.yml",
}
PUSH_CI_FAILURE_CONCLUSIONS = {
    "action_required",
    "cancelled",
    "failure",
    "startup_failure",
    "timed_out",
}
# Sigstore keyless cosign + SLSA Build L3 provenance workflows. The train
# auto-triggers both with execute=true after registry visibility is
# confirmed, so every autodev-train release ships with .cosign.bundle and
# .intoto.jsonl assets attached to the GitHub Release. Failure-tolerant:
# signing failures do not block the release cycle (forward-only per ADR-0018).
SIGN_RELEASE_WORKFLOW = "sign-release.yml"
SLSA_PROVENANCE_WORKFLOW = "slsa-provenance.yml"
SIGN_WAIT_TIMEOUT_SECONDS = 300
SLSA_WAIT_TIMEOUT_SECONDS = 600
# Cadence limiter — skip cycles whose only commits since the previous
# stable tag are the train's own release-prep commits. The train was
# cutting ~150 patches/day with ~33% of commits being its own
# chore(release): prepare vX.Y.Z noise. The limiter is a velocity gate:
# the train keeps polling, but does not manufacture a new tag without
# real human work in the range.
RELEASE_PREP_SUBJECT_REGEX = re.compile(
    r"^chore\(release\): prepare v\d+\.\d+\.\d+(-\S+)?$"
)
# Operator override: cut the next tag even when the only commits in
# range are release-prep commits. Documented in
# docs/runbooks/autodev-train.md ("Cadence limiter").
FORCE_CADENCE_ENV = "ATTESTPLANE_AUTODEV_TRAIN_FORCE_CADENCE"
ABANDONED_STABLE_TAG_REQUIRED_FIELDS = frozenset(
    {"commit", "reason", "abandoned_at", "evidence"}
)
ABANDONED_STABLE_TAG_ALLOWED_FIELDS = ABANDONED_STABLE_TAG_REQUIRED_FIELDS | frozenset(
    {"successor_candidate"}
)


@dataclass(frozen=True, order=True)
class StableVersion:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "StableVersion":
        normalized = value.removeprefix("v")
        match = re.fullmatch(
            r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)",
            normalized,
        )
        if match is None:
            raise ValueError(f"invalid stable version: {value}")
        return cls(*(int(match.group(name)) for name in ("major", "minor", "patch")))

    @classmethod
    def parse_tag(cls, tag: str) -> "StableVersion":
        match = STABLE_TAG_RE.fullmatch(tag)
        if match is None:
            raise ValueError(f"invalid stable tag: {tag}")
        return cls(*(int(match.group(name)) for name in ("major", "minor", "patch")))

    @property
    def tag(self) -> str:
        return f"v{self.major}.{self.minor}.{self.patch}"

    @property
    def python_version(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @property
    def npm_version(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class ReleaseTarget:
    version: StableVersion
    channel: str
    min_soak_hours: int


@dataclass(frozen=True)
class PublicationStatus:
    python_visible: bool | None
    npm_visible: bool | None
    npm_latest: bool | None
    github_release: bool | None
    # signed / slsa are populated by the auto-trigger of sign-release.yml and
    # slsa-provenance.yml after registry visibility is confirmed. They are
    # tracked separately from registry visibility because signing failures
    # are not allowed to block the release cycle (forward-only per ADR-0018).
    # None means "not queried this cycle" and is treated as ignored, not as
    # failure, so pre-this-PR PublicationStatus call sites stay backwards
    # compatible.
    signed: bool | None = None
    slsa: bool | None = None

    @property
    def complete(self) -> bool:
        registries_ok = bool(
            self.python_visible
            and self.npm_visible
            and self.npm_latest
            and self.github_release
        )
        if not registries_ok:
            return False
        if self.signed is False:
            return False
        if self.slsa is False:
            return False
        return True

    @property
    def unknown(self) -> bool:
        return (
            self.python_visible is None
            or self.npm_visible is None
            or self.npm_latest is None
            or self.github_release is None
        )


def run(
    argv: list[str], *, env: dict[str, str] | None = None, timeout: int | None = None
) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(argv), flush=True)
    return run_process(
        argv,
        env=env,
        check=True,
        timeout=timeout,
    )


def capture(argv: list[str], *, timeout: int | None = None) -> str:
    result = run_process(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        timeout=timeout,
    )
    return result.stdout.strip()


def run_git_remote_probe(argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a GitHub-facing git probe with classified retries."""
    last_error: subprocess.CalledProcessError | subprocess.TimeoutExpired | None = None
    for attempt in range(1, REMOTE_PROBE_ATTEMPTS + 1):
        try:
            return run_process(
                argv,
                env=git_remote_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=REMOTE_PROBE_TIMEOUT_SECONDS,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            last_error = exc
            reason = classify_git_push_failure(exc)
            if attempt == REMOTE_PROBE_ATTEMPTS:
                break
            delay = REMOTE_PROBE_BASE_RETRY_SECONDS * (2 ** (attempt - 1))
            print(
                "autodev-train stable: warning: git remote probe "
                f"attempt {attempt}/{REMOTE_PROBE_ATTEMPTS} failed "
                f"({reason}, proxy_mode={git_remote_proxy_label()}); retrying in {delay}s",
                flush=True,
            )
            time.sleep(delay)
    assert last_error is not None
    raise last_error


def capture_git_remote(argv: list[str]) -> str:
    result = run_git_remote_probe(argv)
    return result.stdout.strip()


def run_process(
    argv: list[str],
    *,
    env: dict[str, str] | None = None,
    stdout: int | None = None,
    stderr: int | None = None,
    check: bool,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(  # noqa: S603 - argv is a fixed internal command vector.
        argv,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=stdout,
        stderr=stderr,
        start_new_session=True,
    )
    try:
        out, err = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        terminate_process_group(process)
        out, err = process.communicate()
        raise subprocess.TimeoutExpired(argv, timeout, output=out, stderr=err) from exc

    result = subprocess.CompletedProcess(argv, process.returncode, out, err)
    if check and result.returncode:
        raise subprocess.CalledProcessError(
            result.returncode, argv, output=out, stderr=err
        )
    return result


def git_remote_env() -> dict[str, str] | None:
    """Return the environment for GitHub-facing git commands.

    The train defaults to inheriting the operator's proxy setup. Operators can
    make the release train deterministic under flaky local proxy/TUN setups with
    ``ATTESTPLANE_GIT_PROXY_MODE=bypass`` or force a specific HTTP(S) proxy with
    ``ATTESTPLANE_GIT_PROXY_MODE=force`` plus ``ATTESTPLANE_GIT_PROXY_URL``.
    """
    mode = os.environ.get(GIT_PROXY_MODE_ENV, "inherit").strip().lower()
    if mode in {"", "inherit"}:
        return None
    env = os.environ.copy()
    if mode == "bypass":
        for key in GIT_PROXY_ENV_KEYS:
            env.pop(key, None)
        return env
    if mode == "force":
        proxy_url = os.environ.get(GIT_PROXY_URL_ENV, "").strip()
        if not proxy_url:
            raise RuntimeError(
                f"{GIT_PROXY_URL_ENV} must be set when {GIT_PROXY_MODE_ENV}=force"
            )
        for key in GIT_PROXY_ENV_KEYS:
            env[key] = proxy_url
        return env
    raise RuntimeError(
        f"unsupported {GIT_PROXY_MODE_ENV}={mode!r}; expected inherit, bypass, or force"
    )


def git_remote_proxy_label() -> str:
    mode = os.environ.get(GIT_PROXY_MODE_ENV, "inherit").strip().lower()
    return mode or "inherit"


def terminate_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        process.wait(timeout=5)


def normalize_git_push_argv(argv: list[str]) -> list[str]:
    """Inject the canonical ``http.*`` ``-c`` overrides ahead of ``push origin <ref>``."""
    canonical_prefix = ["git", *GIT_HTTP_CONFIG_ARGS, "push"]
    if argv[: len(canonical_prefix)] == canonical_prefix:
        return argv
    if len(argv) >= 4 and argv[:3] == ["git", "push", "origin"]:
        return ["git", *GIT_HTTP_CONFIG_ARGS, "push", *argv[2:]]
    return argv


def run_git_push(argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Push an idempotent ref with timeout/retry and remote convergence checks."""
    argv = normalize_git_push_argv(argv)
    print("+ " + " ".join(argv), flush=True)
    converged, preflight_reason = git_push_remote_status(argv)
    if converged:
        print("git push remote state already converged; skipping push", flush=True)
        return subprocess.CompletedProcess(argv, 0, "", "")
    if preflight_reason is not None:
        print(
            "git push preflight remote probe failed "
            f"({preflight_reason}, proxy_mode={git_remote_proxy_label()}); attempting push anyway",
            flush=True,
        )

    last_error: subprocess.CalledProcessError | subprocess.TimeoutExpired | None = None
    for attempt in range(1, REMOTE_PUSH_ATTEMPTS + 1):
        try:
            return attempt_git_push_once(argv)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            last_error = exc
            if git_push_remote_converged(argv):
                print(
                    "git push remote state already converged; continuing after failed or timed-out local push",
                    flush=True,
                )
                return subprocess.CompletedProcess(argv, 0, "", "")
            if attempt == REMOTE_PUSH_ATTEMPTS:
                break
            reason = classify_git_push_failure(exc)
            delay = REMOTE_PUSH_RETRY_SECONDS * (2 ** (attempt - 1))
            print(
                f"git push attempt {attempt}/{REMOTE_PUSH_ATTEMPTS} failed or timed out; "
                f"reason={reason}, proxy_mode={git_remote_proxy_label()}; retrying in {delay}s",
                flush=True,
            )
            time.sleep(delay)
    assert last_error is not None
    raise last_error


def attempt_git_push_once(argv: list[str]) -> subprocess.CompletedProcess[str]:
    argv = normalize_git_push_argv(argv)
    result = run_process(
        argv,
        env=git_remote_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=REMOTE_PUSH_TIMEOUT_SECONDS,
    )
    echo_subprocess_output(result.stdout)
    echo_subprocess_output(result.stderr)
    if result.returncode == 0:
        return result
    raise subprocess.CalledProcessError(
        result.returncode, argv, output=result.stdout, stderr=result.stderr
    )


def echo_subprocess_output(text: str | None) -> None:
    if not text:
        return
    print(text, end="" if text.endswith("\n") else "\n", flush=True)


def git_push_remote_converged(argv: list[str]) -> bool:
    return git_push_remote_status(argv)[0]


def git_push_remote_status(argv: list[str]) -> tuple[bool, str | None]:
    argv = normalize_git_push_argv(argv)
    canonical_prefix = ["git", *GIT_HTTP_CONFIG_ARGS, "push"]
    expected_len = len(canonical_prefix) + 2  # "origin" + ref
    if len(argv) != expected_len:
        return False, None
    if argv[: len(canonical_prefix)] != canonical_prefix:
        return False, None
    if argv[len(canonical_prefix)] != "origin":
        return False, None
    ref = argv[len(canonical_prefix) + 1]
    try:
        if ref == "main":
            local_head = capture(
                ["git", "rev-parse", "HEAD"], timeout=REMOTE_PROBE_TIMEOUT_SECONDS
            )
            remote_head = capture_git_remote(
                ["git", "ls-remote", "origin", "refs/heads/main"]
            )
            return bool(remote_head) and remote_head.split()[0] == local_head, None
        if STABLE_TAG_RE.fullmatch(ref):
            remote_tag = capture_git_remote(
                ["git", "ls-remote", "origin", f"refs/tags/{ref}"]
            )
            return bool(remote_tag), None
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ) as exc:
        return False, classify_git_push_failure(exc)
    return False, None


def classify_git_push_failure(exc: BaseException) -> str:
    if isinstance(exc, subprocess.TimeoutExpired):
        return "git_push_timeout"
    text_parts = [str(exc)]
    for attr in ("stderr", "output"):
        value = getattr(exc, attr, None)
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        if isinstance(value, str):
            text_parts.append(value)
    text = "\n".join(text_parts).lower()
    if any(
        phrase in text
        for phrase in (
            "failed to connect",
            "couldn't connect",
            "connection timed out",
            "operation timed out",
            "operation too slow",
            "less than 1000 bytes/sec",
            "curl 28",
            "could not resolve host",
            "network is unreachable",
            "empty reply from server",
            "expected flush after ref listing",
            "remote end hung up unexpectedly",
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
            "failed to push some refs",
        )
    ):
        return "git_push_rejected"
    return f"git_push_{type(exc).__name__.lower()}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_clean_tree() -> None:
    status = capture(["git", "status", "--short"])
    if status:
        raise RuntimeError(
            "working tree must be clean before stable autodev train execution"
        )


def assert_on_main() -> None:
    branch = capture(["git", "branch", "--show-current"])
    if branch != "main":
        raise RuntimeError(
            f"stable autodev train must run on main, currently on {branch!r}"
        )


def git_ref_exists(ref: str) -> bool:
    result = run_process(
        ["git", "rev-parse", "-q", "--verify", ref],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def remote_tag_exists(tag: str) -> bool:
    argv = ["git", "ls-remote", "--exit-code", "--tags", "origin", tag]
    for attempt in range(1, REMOTE_PROBE_ATTEMPTS + 1):
        try:
            result = run_process(
                argv,
                env=git_remote_env(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=False,
                timeout=REMOTE_PROBE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            if attempt == REMOTE_PROBE_ATTEMPTS:
                print(
                    "autodev-train stable: warning: remote tag probe timed out "
                    f"for {tag} after {attempt} attempts "
                    f"(proxy_mode={git_remote_proxy_label()}): {exc}",
                    flush=True,
                )
                return False
            delay = REMOTE_PROBE_BASE_RETRY_SECONDS * (2 ** (attempt - 1))
            print(
                "autodev-train stable: warning: remote tag probe "
                f"attempt {attempt}/{REMOTE_PROBE_ATTEMPTS} timed out for {tag} "
                f"(proxy_mode={git_remote_proxy_label()}); retrying in {delay}s",
                flush=True,
            )
            time.sleep(delay)
            continue
        if result.returncode == 0:
            return True
        if result.returncode == 2:
            return False
        if attempt == REMOTE_PROBE_ATTEMPTS:
            reason = classify_git_push_failure(
                subprocess.CalledProcessError(
                    result.returncode, argv, stderr=result.stderr
                )
            )
            print(
                "autodev-train stable: warning: remote tag probe failed "
                f"for {tag} after {attempt} attempts "
                f"({reason}, proxy_mode={git_remote_proxy_label()})",
                flush=True,
            )
            return False
        delay = REMOTE_PROBE_BASE_RETRY_SECONDS * (2 ** (attempt - 1))
        reason = classify_git_push_failure(
            subprocess.CalledProcessError(result.returncode, argv, stderr=result.stderr)
        )
        print(
            "autodev-train stable: warning: remote tag probe "
            f"attempt {attempt}/{REMOTE_PROBE_ATTEMPTS} failed for {tag} "
            f"({reason}, proxy_mode={git_remote_proxy_label()}); retrying in {delay}s",
            flush=True,
        )
        time.sleep(delay)
    return False


def local_tag_points_to_head(tag: str) -> bool:
    try:
        tag_commit = capture(["git", "rev-parse", f"{tag}^{{commit}}"])
        head_commit = capture(["git", "rev-parse", "HEAD"])
    except subprocess.CalledProcessError:
        return False
    return tag_commit == head_commit


def reconcile_unpublished_local_stable_tag() -> None:
    """Drop a local-only stable tag if a later main commit superseded it.

    A release-prep commit can be pushed, then followed by a fix-forward commit
    before all push CI finishes. GitHub cancels some CI runs for the older
    commit, and the train must not publish that old commit. If the tag was only
    created locally, has not reached the remote, and registries/GitHub Release
    are incomplete, deleting the local tag lets the next cycle prepare the same
    version again on current main. Remote tags are never deleted or moved here.
    """
    try:
        version = latest_stable()
    except RuntimeError:
        return
    tag = version.tag
    if not git_ref_exists(f"refs/tags/{tag}"):
        return
    if remote_tag_exists(tag):
        return
    if local_tag_points_to_head(tag):
        return
    status = publication_status(version)
    if status.unknown or status.complete:
        return
    if not git_ref_is_ancestor(tag, "HEAD"):
        return
    print(
        f"autodev-train stable: deleting unpublished local tag {tag} after main advanced; "
        "will re-prepare on current HEAD",
        flush=True,
    )
    run(["git", "tag", "-d", tag])


def best_effort_fetch_tags() -> None:
    try:
        argv = [
            "git",
            *GIT_HTTP_CONFIG_ARGS,
            "fetch",
            "origin",
            "refs/heads/main:refs/remotes/origin/main",
            "--tags",
        ]
        print("+ " + " ".join(argv), flush=True)
        result = run_git_remote_probe(argv)
        echo_subprocess_output(result.stdout)
        echo_subprocess_output(result.stderr)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        reason = classify_git_push_failure(exc)
        print(
            "autodev-train stable: warning: best-effort origin fetch failed "
            f"or timed out ({reason}, proxy_mode={git_remote_proxy_label()}): {exc}",
            flush=True,
        )


def git_ref_is_ancestor(ancestor: str, descendant: str) -> bool:
    result = run_process(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=REMOTE_PROBE_TIMEOUT_SECONDS,
    )
    return result.returncode == 0


def sync_main_with_origin() -> None:
    """Fast-forward local main to origin/main before preparing a release."""
    try:
        local_head = capture(["git", "rev-parse", "HEAD"])
        origin_main = capture(["git", "rev-parse", "origin/main"])
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "cannot inspect origin/main before stable release train cycle"
        ) from exc

    if local_head == origin_main:
        return
    if git_ref_is_ancestor("HEAD", "origin/main"):
        run(["git", "merge", "--ff-only", "origin/main"])
        return
    if git_ref_is_ancestor("origin/main", "HEAD"):
        return
    raise RuntimeError(
        "local main and origin/main have diverged; rebase required before stable autodev train"
    )


def list_stable_tags() -> list[StableVersion]:
    raw = capture(["git", "tag", "--list", "v*.*.*"])
    versions: list[StableVersion] = []
    for line in raw.splitlines():
        try:
            versions.append(StableVersion.parse_tag(line.strip()))
        except ValueError:
            continue
    return sorted(versions)


def abandoned_stable_tags(path: Path = DEFAULT_ABANDONED_STABLE_TAGS) -> set[str]:
    """Return stable tags that are immutable but intentionally not publishable.

    ``successor_candidate`` is advisory only: it documents the next version the
    train should try after a failed, unpublished tag. It is not a claim that the
    successor has already been published.
    """
    if not path.is_file():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "attestplane_abandoned_stable_tags.v1":
        raise RuntimeError(f"unsupported abandoned stable tags schema in {path}")
    raw_tags = payload.get("tags", {})
    if not isinstance(raw_tags, dict):
        raise RuntimeError(f"abandoned stable tags must be an object in {path}")
    tags: set[str] = set()
    for tag, details in raw_tags.items():
        StableVersion.parse_tag(str(tag))
        if not isinstance(details, dict):
            raise RuntimeError(f"abandoned stable tag entry must be an object: {tag}")
        missing = ABANDONED_STABLE_TAG_REQUIRED_FIELDS - set(details)
        if missing:
            raise RuntimeError(
                f"abandoned stable tag {tag} missing required fields: {sorted(missing)}"
            )
        unknown = set(details) - ABANDONED_STABLE_TAG_ALLOWED_FIELDS
        if unknown:
            raise RuntimeError(
                f"abandoned stable tag {tag} contains unknown fields: {sorted(unknown)}"
            )
        successor = details.get("successor_candidate")
        if successor is not None:
            StableVersion.parse_tag(str(successor))
            if str(successor) == str(tag):
                raise RuntimeError(
                    f"abandoned stable tag {tag} successor_candidate must not reference itself"
                )
        if not isinstance(details["commit"], str) or not details["commit"]:
            raise RuntimeError(
                f"abandoned stable tag {tag} commit must be a non-empty string"
            )
        if not isinstance(details["reason"], str) or not details["reason"]:
            raise RuntimeError(
                f"abandoned stable tag {tag} reason must be a non-empty string"
            )
        if not isinstance(details["abandoned_at"], str) or not details["abandoned_at"]:
            raise RuntimeError(
                f"abandoned stable tag {tag} abandoned_at must be a non-empty string"
            )
        if not details["abandoned_at"].endswith("Z"):
            raise RuntimeError(
                f"abandoned stable tag {tag} abandoned_at must be a UTC timestamp ending in Z"
            )
        try:
            datetime.fromisoformat(details["abandoned_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise RuntimeError(
                f"abandoned stable tag {tag} abandoned_at must be ISO 8601"
            ) from exc
        if not isinstance(details["evidence"], dict):
            raise RuntimeError(f"abandoned stable tag {tag} evidence must be an object")
        tags.add(str(tag))
    return tags


def is_abandoned_stable_tag(tag: str) -> bool:
    return tag in abandoned_stable_tags()


def latest_stable_before(target: StableVersion) -> StableVersion:
    abandoned = abandoned_stable_tags()
    candidates = [
        version
        for version in list_stable_tags()
        if version < target and version.tag not in abandoned
    ]
    if not candidates:
        raise RuntimeError(f"no stable release tag found before {target.tag}")
    return max(candidates)


def latest_stable() -> StableVersion:
    versions = list_stable_tags()
    if not versions:
        raise RuntimeError("no stable release tag found")
    return max(versions)


def next_stable_after(version: StableVersion) -> StableVersion:
    if version.major == 0 and version.minor >= 9 and version.patch >= PATCH_ROLLOVER:
        return StableVersion(1, 0, 0)
    if version.patch >= PATCH_ROLLOVER:
        return StableVersion(version.major, version.minor + 1, 0)
    return StableVersion(version.major, version.minor, version.patch + 1)


def next_unabandoned_stable_after(version: StableVersion) -> StableVersion:
    abandoned = abandoned_stable_tags()
    candidate = next_stable_after(version)
    while candidate.tag in abandoned or git_ref_exists(f"refs/tags/{candidate.tag}"):
        if candidate.tag in abandoned:
            print(
                f"autodev-train stable: generated target {candidate.tag} is abandoned; skipping",
                flush=True,
            )
        else:
            print(
                f"autodev-train stable: generated target {candidate.tag} already has stable tag; skipping",
                flush=True,
            )
        candidate = next_stable_after(candidate)
    return candidate


def commits_since_tag_have_real_work(tag: str) -> bool:
    """Return True if the range ``tag..HEAD`` contains any non-release-prep commit.

    Velocity gate for the autodev-train: if every commit subject in the
    range matches ``RELEASE_PREP_SUBJECT_REGEX`` (or the range is empty),
    the next cadence cycle has no human work to ship and the caller
    should skip cutting a new tag. ``--no-merges`` excludes merge commits
    so a PR-merge into main does not by itself count as real work.

    Returns ``True`` (proceed) when:
      - at least one commit subject does NOT match the release-prep regex; or
      - the git log probe fails (e.g. missing tag) — conservative fall-through
        to the normal cycle, which has its own guards.

    Returns ``False`` (skip) when:
      - every subject in the range matches the release-prep regex; or
      - the range is empty (no commits since tag — nothing new to cut).
    """
    try:
        raw = capture(
            ["git", "log", "--pretty=tformat:%s", f"{tag}..HEAD", "--no-merges"],
            timeout=REMOTE_PROBE_TIMEOUT_SECONDS,
        )
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ) as exc:
        print(
            f"autodev-train stable: warning: cadence probe failed for {tag}: {exc}; "
            "falling through to normal cycle",
            flush=True,
        )
        return True
    subjects = [line for line in raw.splitlines() if line.strip()]
    if not subjects:
        return False
    return any(
        RELEASE_PREP_SUBJECT_REGEX.fullmatch(subject) is None for subject in subjects
    )


def load_target_queue(path: Path) -> list[ReleaseTarget]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "attestplane_autodev_train_targets.v2":
        raise RuntimeError(f"unsupported autodev target queue schema in {path}")
    raw_targets = payload.get("targets")
    if not isinstance(raw_targets, list) or not raw_targets:
        raise RuntimeError(f"autodev target queue has no targets: {path}")

    targets: list[ReleaseTarget] = []
    previous: StableVersion | None = None
    for raw in raw_targets:
        if not isinstance(raw, dict):
            raise RuntimeError("autodev target queue entries must be objects")
        status = str(raw.get("status", "queued"))
        if status not in {"queued", "complete", "paused"}:
            raise RuntimeError(f"unsupported target status {status!r}")
        version = StableVersion.parse(str(raw["version"]))
        if previous is not None and version <= previous:
            raise RuntimeError("autodev target queue must be strictly increasing")
        previous = version
        channel = str(raw.get("channel", "latest"))
        if channel != "latest":
            raise RuntimeError(
                f"target {version.tag} channel {channel!r} is unsupported by stable autodev train; "
                "use GitHub release-cd channel=latest for suffix-free packages"
            )
        min_soak_hours = int(raw.get("min_soak_hours", 0))
        if min_soak_hours < 0:
            raise RuntimeError(
                f"target {version.tag} min_soak_hours must be non-negative"
            )
        if status == "queued":
            targets.append(
                ReleaseTarget(
                    version=version, channel=channel, min_soak_hours=min_soak_hours
                )
            )
    return targets


def select_target(path: Path) -> ReleaseTarget:
    try:
        base = latest_stable()
    except RuntimeError:
        base = None
    if base is not None and is_abandoned_stable_tag(base.tag):
        print(
            f"autodev-train stable: latest tag {base.tag} is abandoned; skipping recovery",
            flush=True,
        )
        base = latest_stable_before(base)
    if base is not None and not publication_status(base).complete:
        print(
            f"autodev-train stable: latest tag {base.tag} is not fully published; recovering before advancing",
            flush=True,
        )
        return ReleaseTarget(version=base, channel="latest", min_soak_hours=0)

    for target in load_target_queue(path):
        if is_abandoned_stable_tag(target.version.tag):
            print(
                f"autodev-train stable: target {target.version.tag} is abandoned; skipping",
                flush=True,
            )
            continue
        if git_ref_exists(f"refs/tags/{target.version.tag}") or remote_tag_exists(
            target.version.tag
        ):
            print(
                f"autodev-train stable: target {target.version.tag} already has stable tag; skipping",
                flush=True,
            )
            continue
        return target
    if base is None:
        base = latest_stable()
    generated = next_unabandoned_stable_after(base)
    print(
        f"autodev-train stable: target queue exhausted; generated next target {generated.tag} after {base.tag}",
        flush=True,
    )
    return ReleaseTarget(version=generated, channel="latest", min_soak_hours=0)


def load_release_gate_module() -> Any:
    spec = importlib.util.spec_from_file_location("release_gate", RELEASE_GATE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load release gate module from {RELEASE_GATE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def assert_release_gate_allows_target(target: ReleaseTarget) -> None:
    release_gate = load_release_gate_module()
    decision = release_gate.decide_release_gate(
        release_tag=target.version.tag,
        channel=target.channel,
        labels=[],
        release_audit=False,
        milestone=None,
        dependency_major_bump=False,
        env=os.environ,
    )
    verification = release_gate.validate_audit_verification(
        decision,
        audit_verified=release_gate.truthy(
            os.environ.get("ATTESTPLANE_RELEASE_AUDIT_VERIFIED", "")
        ),
        audit_plan_url=os.environ.get("ATTESTPLANE_RELEASE_AUDIT_PLAN_URL", ""),
    )
    if not verification.allowed:
        raise RuntimeError(
            "release gate blocked stable autodev target "
            f"{target.version.tag}: {verification.reason}; reasons={','.join(decision.reasons)}"
        )


def product_delta_for_target(target: ReleaseTarget, previous: StableVersion) -> Any:
    release_gate = load_release_gate_module()
    return release_gate.classify_product_delta(
        release_gate.changed_files_between(previous.tag, "HEAD"),
        labels=[],
        env=os.environ,
    )


def assert_product_delta_allows_target(
    target: ReleaseTarget, previous: StableVersion
) -> None:
    product_delta = product_delta_for_target(target, previous)
    if not product_delta.allowed:
        raise RuntimeError(
            "release product delta gate blocked stable autodev target "
            f"{target.version.tag}: {product_delta.reason}; previous_tag={previous.tag}"
        )


def read_python_version() -> str:
    with (ROOT / "sdk/python/pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    return str(data["project"]["version"])


def read_npm_version() -> str:
    return str(
        json.loads((ROOT / "sdk/typescript/package.json").read_text(encoding="utf-8"))[
            "version"
        ]
    )


def replace_one(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"expected exactly one replacement in {path}")
    path.write_text(updated, encoding="utf-8")


def update_json_version(path: Path, version: str) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = version
    if path.name == "package-lock.json":
        packages = payload.get("packages")
        if isinstance(packages, dict) and isinstance(packages.get(""), dict):
            packages[""]["version"] = version
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )


def update_versions(version: StableVersion) -> None:
    replace_one(
        ROOT / "sdk/python/pyproject.toml",
        r'^version = "[^"]+"$',
        f'version = "{version.python_version}"',
    )
    replace_one(
        ROOT / "sdk/python/src/attestplane/__init__.py",
        r'^__version__ = "[^"]+"$',
        f'__version__ = "{version.python_version}"',
    )
    replace_one(
        ROOT / "sdk/python/tests/test_import_surface.py",
        r'^    assert attestplane\.__version__ == "[^"]+"$',
        f'    assert attestplane.__version__ == "{version.python_version}"',
    )
    run(["bash", "-lc", "cd sdk/python && uv lock"])
    update_json_version(ROOT / "sdk/typescript/package.json", version.npm_version)
    update_json_version(ROOT / "sdk/typescript/package-lock.json", version.npm_version)
    replace_one(
        ROOT / "sdk/typescript/src/index_version.ts",
        r"^export const VERSION = '[^']+';$",
        f"export const VERSION = '{version.npm_version}';",
    )


def markdown_escape_release_subject(subject: str) -> str:
    """Escape commit subjects before embedding them as markdown list text."""
    return subject.replace("[", r"\[").replace("]", r"\]")


def write_release_notes(previous: StableVersion, version: StableVersion) -> None:
    path = ROOT / "docs" / "release-notes" / f"{version.tag}.draft.md"
    commits = capture(["git", "log", "--format=%s", f"{previous.tag}..HEAD"])
    changes = [
        f"- {markdown_escape_release_subject(line)}"
        for line in commits.splitlines()[:20]
    ]
    if not changes:
        changes = [f"- Queue advancement from `{previous.tag}` to `{version.tag}`."]
    path.write_text(
        "\n".join(
            [
                f"# {version.tag}",
                "",
                f"`{version.tag}` is an automated suffix-free stable package cut from autodev-train.",
                "",
                "## Changes Since Previous Stable",
                "",
                *changes,
                "",
                "## Highlights",
                "",
                "- Publishes suffix-free Python and npm package versions through GitHub `release-cd`.",
                "- Advances PyPI default installs because PyPI has no dist-tag concept.",
                "- Advances npm `latest` through the stable release workflow.",
                "- Does not move npm `ca`; CA remains a separate manual dist-tag decision.",
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
                f"- `sdk/python/dist/attestplane-{version.python_version}-py3-none-any.whl`",
                f"- `sdk/python/dist/attestplane-{version.python_version}.tar.gz`",
                f"- `sdk/typescript/attestplane-attestplane-{version.npm_version}.tgz`",
                f"- `release/artifacts/{version.tag}/checksums.sha256`",
                f"- `release/artifacts/{version.tag}/artifact-manifest.json`",
                "",
            ]
        ),
        encoding="utf-8",
    )


def artifact_paths(version: StableVersion) -> list[str]:
    return [
        f"sdk/python/dist/attestplane-{version.python_version}-py3-none-any.whl",
        f"sdk/python/dist/attestplane-{version.python_version}.tar.gz",
        f"sdk/typescript/attestplane-attestplane-{version.npm_version}.tgz",
    ]


def build_artifacts(version: StableVersion) -> None:
    run(
        [
            "bash",
            "-lc",
            "cd sdk/python && rm -rf dist build && .venv/bin/python -m build >/dev/null && .venv/bin/python -m twine check dist/*",
        ]
    )
    run(
        [
            "bash",
            "-lc",
            "cd sdk/typescript && find . -maxdepth 1 -name '*.tgz' -delete && npm ci --silent >/dev/null && npm run build --silent >/dev/null && npm test --silent >/dev/null && npm pack --silent >/dev/null",
        ]
    )
    for artifact in artifact_paths(version):
        if not (ROOT / artifact).is_file():
            raise FileNotFoundError(f"expected release artifact missing: {artifact}")


def artifact_entry(
    kind: str, name: str, package_version: str, path: str
) -> dict[str, Any]:
    artifact = ROOT / path
    return {
        "kind": kind,
        "name": name,
        "path": path,
        "version": package_version,
        "sha256": sha256_file(artifact),
        "size_bytes": artifact.stat().st_size,
    }


def write_release_metadata(version: StableVersion) -> None:
    release_dir = ROOT / "release" / "artifacts" / version.tag
    release_dir.mkdir(parents=True, exist_ok=True)
    artifacts = [
        artifact_entry(
            "python-wheel",
            "attestplane",
            version.python_version,
            artifact_paths(version)[0],
        ),
        artifact_entry(
            "python-sdist",
            "attestplane",
            version.python_version,
            artifact_paths(version)[1],
        ),
        artifact_entry(
            "npm-tarball",
            "@attestplane/attestplane",
            version.npm_version,
            artifact_paths(version)[2],
        ),
    ]
    manifest = {
        "artifacts": artifacts,
        "checksums_file": f"release/artifacts/{version.tag}/checksums.sha256",
        "explicit_non_actions": {
            "deploy": "not performed",
            "force_push": "not performed",
            "npm_ca_change": "not performed by stable autodev train",
            "release_publish": "not performed during local prep",
            "workflow_dispatch": "not performed during prep",
        },
        "explicit_non_claims": {
            "certified_provenance": False,
            "compliance_certification": False,
            "production_ready": False,
            "slsa_l3": False,
        },
        "release": version.tag,
        "release_notes_file": f"docs/release-notes/{version.tag}.draft.md",
        "schema": "attestplane_release_artifact_manifest.v1",
        "source_state": {
            "prepared_by": "autodev_train_stable_release_prep",
            "target_commit": capture(["git", "rev-parse", "HEAD"]),
        },
        "upload_plan_file": f"release/artifacts/{version.tag}/upload-plan.md",
    }
    manifest_path = release_dir / "artifact-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    checksums_path = release_dir / "checksums.sha256"
    checksums_path.write_text(
        "\n".join(f"{artifact['sha256']}  {artifact['path']}" for artifact in artifacts)
        + "\n",
        encoding="utf-8",
    )
    (release_dir / "upload-plan.md").write_text(
        "\n".join(
            [
                f"# {version.tag} Release-Asset Upload Plan",
                "",
                "This plan documents artifacts prepared for the suffix-free stable release path.",
                "",
                "## Prepared Files",
                "",
                "```text",
                *artifact_paths(version),
                f"release/artifacts/{version.tag}/checksums.sha256",
                f"release/artifacts/{version.tag}/artifact-manifest.json",
                "```",
                "",
                "## Release Commands",
                "",
                "```bash",
                f'git tag -a {version.tag} -m "{version.tag}"',
                "git push origin main",
                f"git push origin {version.tag}",
                f"gh workflow run release-cd.yml -f release_tag={version.tag} -f channel=latest -f dry_run=false --ref main",
                "```",
                "",
                "## Explicit Non-Actions in Release Prep",
                "",
                "- Force push: not performed.",
                "- npm `ca` dist-tag change: not performed by stable autodev train.",
                "- Deploy: not performed.",
                "- Workflow dispatch: not performed during local prep.",
                "- Registry publication: not performed during local prep.",
                "",
                "## Claim Boundary",
                "",
                "This stable package cut is limited to the package artifacts listed above.",
                "Legal, compliance, certification, provenance-attestation, and supply-chain",
                "assurance categories remain out of scope unless backed by separate verified",
                "artifacts.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def run_local_validation(version: StableVersion) -> None:
    env = {
        **os.environ,
        "ATTESTPLANE_RELEASE_ASSETS_PREBUILT": "1",
        "RELEASE_VERSION": version.tag,
        "PYTHON_VERSION": version.python_version,
        "NPM_VERSION": version.npm_version,
    }
    run(["git", "diff", "--check"])
    run(["scripts/check-release-assets-prep.sh"], env=env)
    run(
        [
            "sdk/python/.venv/bin/python",
            "-m",
            "pytest",
            "sdk/python/tests/test_import_surface.py",
            "sdk/python/tests/test_release_cd_policy.py",
            "-q",
        ]
    )
    run(
        [
            "sdk/python/.venv/bin/python",
            "scripts/release/validate_release_cd.py",
            "--release-tag",
            version.tag,
            "--channel",
            "latest",
            "--repo-root",
            str(ROOT),
        ]
    )


def commit_and_tag(version: StableVersion) -> None:
    files = [
        "sdk/python/pyproject.toml",
        "sdk/python/uv.lock",
        "sdk/python/src/attestplane/__init__.py",
        "sdk/python/tests/test_import_surface.py",
        "sdk/typescript/package.json",
        "sdk/typescript/package-lock.json",
        "sdk/typescript/src/index_version.ts",
        f"docs/release-notes/{version.tag}.draft.md",
        f"release/artifacts/{version.tag}/artifact-manifest.json",
        f"release/artifacts/{version.tag}/checksums.sha256",
        f"release/artifacts/{version.tag}/upload-plan.md",
    ]
    run(["git", "add", *files])
    run(["git", "commit", "-s", "-m", f"chore(release): prepare {version.tag}"])
    run(["git", "tag", "-a", version.tag, "-m", version.tag])


def push_and_dispatch(version: StableVersion, *, wait: bool) -> None:
    run_git_push(["git", "push", "origin", "main"])
    head_sha = capture(["git", "rev-parse", "HEAD"])
    wait_for_push_ci(head_sha)
    run_git_push(["git", "push", "origin", version.tag])
    run(release_cd_dispatch_args(version))
    if wait:
        wait_for_release_cd(version)
        # Trigger Sigstore keyless cosign + SLSA Build L3 provenance per
        # ADR-0018. Failure-tolerant: a signing or provenance failure is
        # logged but does not block the cycle; signed/slsa state is
        # tracked separately on PublicationStatus so a follow-up cycle
        # can re-trigger without re-publishing the registry artifacts.
        signed = trigger_sign_release(version.tag)
        slsa = trigger_slsa_provenance(version.tag)
        if not signed:
            print(
                f"autodev-train stable: WARNING: {version.tag} published but cosign signing did not complete; "
                "supply-chain evidence is incomplete and requires manual re-trigger",
                file=sys.stderr,
                flush=True,
            )
        if not slsa:
            print(
                f"autodev-train stable: WARNING: {version.tag} published but SLSA provenance did not complete; "
                "supply-chain evidence is incomplete and requires manual re-trigger",
                file=sys.stderr,
                flush=True,
            )


def resume_tagged_release_publish(version: StableVersion, *, wait: bool) -> None:
    if not git_ref_exists(f"refs/tags/{version.tag}"):
        raise RuntimeError(f"cannot resume {version.tag}: local tag is missing")
    if not local_tag_points_to_head(version.tag):
        raise RuntimeError(
            f"cannot resume {version.tag}: local tag does not point to HEAD"
        )
    print(
        f"autodev-train stable: resuming publish for locally tagged {version.tag}",
        flush=True,
    )
    push_and_dispatch(version, wait=wait)


def release_cd_dispatch_args(version: StableVersion) -> list[str]:
    argv = [
        "gh",
        "workflow",
        "run",
        "release-cd.yml",
        "-f",
        f"release_tag={version.tag}",
        "-f",
        "channel=latest",
        "-f",
        "dry_run=false",
    ]
    audit_verified = os.environ.get("ATTESTPLANE_RELEASE_AUDIT_VERIFIED", "")
    audit_plan_url = os.environ.get("ATTESTPLANE_RELEASE_AUDIT_PLAN_URL", "").strip()
    if audit_plan_url:
        argv.extend(["-f", f"audit_verified={str(truthy_env(audit_verified)).lower()}"])
        argv.extend(["-f", f"audit_plan_url={audit_plan_url}"])
    argv.extend(["--ref", "main"])
    return argv


def truthy_env(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def pypi_version_visible(version: StableVersion) -> bool | None:
    try:
        with urllib.request.urlopen(
            f"https://pypi.org/pypi/attestplane/{version.python_version}/json",
            timeout=20,
        ) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise
    except (OSError, TimeoutError) as exc:
        print(
            f"autodev-train stable: warning: PyPI probe failed for {version.tag}: {exc}",
            flush=True,
        )
        return None
    return payload.get("info", {}).get("version") == version.python_version


def npm_version_visible(version: StableVersion) -> bool | None:
    try:
        result = run_process(
            [
                "npm",
                "view",
                f"@attestplane/attestplane@{version.npm_version}",
                "version",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        print(
            f"autodev-train stable: warning: npm version probe timed out for {version.tag}: {exc}",
            flush=True,
        )
        return None
    return (
        result.returncode == 0 and (result.stdout or "").strip() == version.npm_version
    )


def npm_latest_points_to(version: StableVersion) -> bool | None:
    try:
        result = run_process(
            ["npm", "view", "@attestplane/attestplane", "dist-tags.latest"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        print(
            f"autodev-train stable: warning: npm dist-tag probe timed out for {version.tag}: {exc}",
            flush=True,
        )
        return None
    return (
        result.returncode == 0 and (result.stdout or "").strip() == version.npm_version
    )


def github_release_exists(version: StableVersion) -> bool | None:
    try:
        result = run_process(
            ["gh", "release", "view", version.tag, "--json", "tagName"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        print(
            f"autodev-train stable: warning: GitHub Release probe timed out for {version.tag}: {exc}",
            flush=True,
        )
        return None
    return result.returncode == 0


def publication_status(version: StableVersion) -> PublicationStatus:
    status = PublicationStatus(
        python_visible=pypi_version_visible(version),
        npm_visible=npm_version_visible(version),
        npm_latest=npm_latest_points_to(version),
        github_release=github_release_exists(version),
    )
    emit_train_event(
        "publication_status",
        tag=version.tag,
        python_visible=bool(status.python_visible),
        npm_visible=bool(status.npm_visible),
        npm_latest=bool(status.npm_latest),
        github_release=status.github_release,
        complete=status.complete,
    )
    print(
        "autodev-train stable: publication status "
        f"{version.tag}: pypi={status.python_visible} npm={status.npm_visible} "
        f"npm_latest={status.npm_latest} github_release={status.github_release}",
        flush=True,
    )
    return status


def wait_for_pypi(version: StableVersion) -> None:
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        if pypi_version_visible(version):
            print(f"PyPI visible for {version.tag}", flush=True)
            return
        time.sleep(20)
    raise TimeoutError(f"timed out waiting for PyPI version {version.python_version}")


def dispatch_publish_python(version: StableVersion) -> None:
    caller = f"stable-auto-recovery-{version.tag}-{int(time.time())}"
    run(
        [
            "gh",
            "workflow",
            "run",
            "publish-python.yml",
            "--ref",
            "main",
            "-f",
            "target=pypi",
            "-f",
            f"release_ref={version.tag}",
            "-f",
            "dry_run=false",
            "-f",
            f"caller_run_id={caller}",
        ]
    )
    wait_for_publish_python(version, caller)


def wait_for_publish_python(version: StableVersion, caller: str) -> None:
    print(
        f"waiting for delegated publish-python workflow for {version.tag}", flush=True
    )
    expected_title = f"publish-python {version.tag} pypi caller-{caller}"
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        try:
            run_id = capture(
                [
                    "gh",
                    "run",
                    "list",
                    "--workflow",
                    "publish-python.yml",
                    "--event",
                    "workflow_dispatch",
                    "--limit",
                    "50",
                    "--json",
                    "databaseId,displayTitle,status",
                    "--jq",
                    f'.[] | select(.displayTitle == "{expected_title}") | .databaseId',
                ]
            ).splitlines()[0]
        except (subprocess.CalledProcessError, IndexError):
            time.sleep(5)
            continue
        run(["gh", "run", "watch", run_id, "--exit-status"])
        return
    raise TimeoutError(
        f"timed out waiting for delegated publish-python workflow for {version.tag}"
    )


def ensure_github_release(version: StableVersion) -> None:
    notes_file = ROOT / "docs" / "release-notes" / f"{version.tag}.draft.md"
    asset_paths = [
        ROOT / "release" / "artifacts" / version.tag / "artifact-manifest.json",
        ROOT / "release" / "artifacts" / version.tag / "checksums.sha256",
        ROOT / "release" / "artifacts" / version.tag / "upload-plan.md",
    ]
    if not notes_file.is_file():
        raise FileNotFoundError(f"release notes missing for recovery: {notes_file}")
    for asset in asset_paths:
        if not asset.is_file():
            raise FileNotFoundError(f"release asset missing for recovery: {asset}")

    release_flags = ["--title", version.tag, "--notes-file", str(notes_file)]
    assets = [str(asset) for asset in asset_paths]
    if github_release_exists(version):
        run(["gh", "release", "edit", version.tag, *release_flags])
        run(["gh", "release", "upload", version.tag, "--clobber", *assets])
    else:
        run(
            [
                "gh",
                "release",
                "create",
                version.tag,
                "--verify-tag",
                *release_flags,
                *assets,
            ]
        )


def recover_existing_release(version: StableVersion) -> None:
    status = publication_status(version)
    if status.unknown:
        raise RuntimeError(
            f"cannot auto-recover {version.tag}: publication status probe is incomplete; retry later"
        )
    if status.complete:
        print(
            f"autodev-train stable: existing release {version.tag} is complete",
            flush=True,
        )
        return
    if not status.npm_visible or not status.npm_latest:
        raise RuntimeError(
            f"cannot auto-recover {version.tag}: npm state is incomplete "
            f"(visible={status.npm_visible}, latest={status.npm_latest})"
        )
    if not status.python_visible:
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                print(
                    f"autodev-train stable: recovering PyPI publish for {version.tag} (attempt {attempt}/3)",
                    flush=True,
                )
                dispatch_publish_python(version)
                wait_for_pypi(version)
                break
            except Exception as exc:  # noqa: BLE001 - keep continuous train recoverable after transient publisher failures.
                last_error = exc
                print(
                    f"autodev-train stable: PyPI recovery attempt failed for {version.tag}: {exc}",
                    flush=True,
                )
                time.sleep(30)
        else:
            raise RuntimeError(
                f"cannot auto-recover PyPI publication for {version.tag}: {last_error}"
            ) from last_error
    ensure_github_release(version)
    final = publication_status(version)
    if final.unknown:
        raise RuntimeError(
            f"release recovery status is incomplete for {version.tag}: {final}"
        )
    if not final.complete:
        raise RuntimeError(
            f"release recovery did not complete for {version.tag}: {final}"
        )


def wait_for_push_ci(head_sha: str) -> None:
    print(f"waiting for push CI workflows for {head_sha}", flush=True)
    emit_train_event("push_ci_wait_start", head_sha=head_sha)
    deadline = time.monotonic() + 1800
    expected = set(PUSH_CI_WORKFLOWS)
    last_summary = ""
    dispatched_missing: set[str] = set()
    first_missing_at: float | None = None

    while time.monotonic() < deadline:
        try:
            raw = capture(
                [
                    "gh",
                    "run",
                    "list",
                    "--limit",
                    "200",
                    "--json",
                    "conclusion,databaseId,event,headSha,name,status,url",
                ]
            )
        except subprocess.CalledProcessError as exc:
            print(f"push CI probe failed: {exc}; retrying", flush=True)
            emit_train_event("push_ci_probe_retry", head_sha=head_sha, error=str(exc))
            time.sleep(20)
            continue

        runs = json.loads(raw or "[]")
        matched = {
            run["name"]: run
            for run in runs
            if run.get("headSha") == head_sha and run.get("name") in expected
        }
        failed = [
            run
            for run in matched.values()
            if (run.get("conclusion") or "") in PUSH_CI_FAILURE_CONCLUSIONS
        ]
        if failed:
            details = "; ".join(
                f"{run.get('name')}={run.get('conclusion')} ({run.get('url')})"
                for run in sorted(failed, key=lambda item: item.get("name") or "")
            )
            emit_train_event("push_ci_failed", head_sha=head_sha, details=details)
            raise RuntimeError(f"push CI failed for {head_sha}: {details}")

        missing = sorted(expected - set(matched))
        pending = sorted(
            name
            for name, run in matched.items()
            if run.get("status") != "completed" or run.get("conclusion") != "success"
        )
        if not missing and not pending:
            print(f"push CI workflows passed for {head_sha}", flush=True)
            emit_train_event("push_ci_passed", head_sha=head_sha)
            return

        now = time.monotonic()
        if missing and first_missing_at is None:
            first_missing_at = now
        if missing and first_missing_at is not None and now - first_missing_at >= 60:
            for name in missing:
                if name in dispatched_missing:
                    continue
                workflow_file = PUSH_CI_WORKFLOW_FILES[name]
                print(
                    f"push CI workflow {name} is missing for {head_sha}; dispatching {workflow_file}",
                    flush=True,
                )
                run(["gh", "workflow", "run", workflow_file, "--ref", "main"])
                dispatched_missing.add(name)

        summary = (
            f"missing={','.join(missing) or '-'} pending={','.join(pending) or '-'}"
        )
        if summary != last_summary:
            print(f"push CI waiting for {head_sha}: {summary}", flush=True)
            emit_train_event("push_ci_waiting", head_sha=head_sha, summary=summary)
            last_summary = summary
        time.sleep(20)

    raise TimeoutError(f"timed out waiting for push CI workflows for {head_sha}")


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def emit_train_event(event: str, **fields: Any) -> None:
    emit_observability_event(
        {
            "event": event,
            "ts": utc_now_iso(),
            "train": AUTODEV_TRAIN,
            **fields,
        }
    )


def parse_utc_timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def select_new_signing_run_id(
    raw_runs: list[dict[str, Any]], dispatch_started_at: str
) -> str | None:
    """Choose the newest visible signing workflow run after dispatch started."""
    started_at = parse_utc_timestamp(dispatch_started_at)
    if started_at is None:
        return None

    candidates: list[tuple[datetime, int, str]] = []
    for run in raw_runs:
        if run.get("headBranch") != "main":
            continue
        created_at = parse_utc_timestamp(str(run.get("createdAt", "")))
        if created_at is None or created_at < started_at:
            continue
        run_id = run.get("databaseId")
        try:
            database_id = int(run_id)
        except (TypeError, ValueError):
            continue
        candidates.append((created_at, database_id, str(run_id)))

    if not candidates:
        return None
    return max(candidates)[2]


def _dispatch_signing_workflow(workflow: str, tag: str, timeout_seconds: int) -> bool:
    """Dispatch a signing-class workflow with execute=true and wait for completion.

    Returns True on success. On any failure (dispatch error, run-id resolution
    timeout, workflow run failure, watch timeout), logs to stderr and returns
    False. Signing failures are not allowed to block the autodev-train release
    cycle (forward-only per ADR-0018); the caller records signed/slsa state on
    PublicationStatus so a follow-up cycle can re-trigger without re-publishing.
    """
    dispatch_started_at = utc_now_iso()
    try:
        run(
            [
                "gh",
                "workflow",
                "run",
                workflow,
                "--ref",
                "main",
                "-f",
                f"tag={tag}",
                "-f",
                "execute=true",
            ]
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(
            f"autodev-train stable: failed to dispatch {workflow} for {tag}: {exc}",
            file=sys.stderr,
            flush=True,
        )
        return False

    print(f"waiting for {workflow} run for {tag}", flush=True)
    deadline = time.monotonic() + timeout_seconds
    run_id = ""
    while time.monotonic() < deadline:
        try:
            raw_runs = capture(
                [
                    "gh",
                    "run",
                    "list",
                    "--workflow",
                    workflow,
                    "--event",
                    "workflow_dispatch",
                    "--limit",
                    "20",
                    "--json",
                    "createdAt,databaseId,headBranch,status",
                ]
            )
            runs = json.loads(raw_runs or "[]")
            run_id = select_new_signing_run_id(runs, dispatch_started_at)
            if run_id is None:
                raise IndexError("new signing workflow run not visible yet")
        except (subprocess.CalledProcessError, IndexError, json.JSONDecodeError):
            time.sleep(5)
            continue
        if run_id:
            try:
                run(
                    ["gh", "run", "watch", run_id, "--exit-status"],
                    timeout=timeout_seconds,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                print(
                    f"autodev-train stable: {workflow} run {run_id} failed for {tag}: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
                return False
            return True
    print(
        f"autodev-train stable: timed out waiting for {workflow} dispatch for {tag}",
        file=sys.stderr,
        flush=True,
    )
    return False


def trigger_sign_release(tag: str) -> bool:
    return _dispatch_signing_workflow(
        SIGN_RELEASE_WORKFLOW, tag, SIGN_WAIT_TIMEOUT_SECONDS
    )


def trigger_slsa_provenance(tag: str) -> bool:
    return _dispatch_signing_workflow(
        SLSA_PROVENANCE_WORKFLOW, tag, SLSA_WAIT_TIMEOUT_SECONDS
    )


def wait_for_release_cd(version: StableVersion) -> None:
    print(f"waiting for release-cd workflow for {version.tag}", flush=True)
    emit_train_event("release_cd_wait_start", target_tag=version.tag)
    deadline = time.monotonic() + 1800
    head_sha = capture(["git", "rev-parse", "HEAD"])
    run_id = ""
    while time.monotonic() < deadline:
        try:
            run_id = capture(
                [
                    "gh",
                    "run",
                    "list",
                    "--workflow",
                    "release-cd.yml",
                    "--event",
                    "workflow_dispatch",
                    "--limit",
                    "20",
                    "--json",
                    "databaseId,headBranch,headSha,status",
                    "--jq",
                    f'.[] | select(.headBranch == "main") | select(.headSha == "{head_sha}") | .databaseId',
                ]
            ).splitlines()[0]
        except (subprocess.CalledProcessError, IndexError):
            time.sleep(10)
            continue
        if run_id:
            try:
                run(["gh", "run", "watch", run_id, "--exit-status"])
            except subprocess.CalledProcessError:
                if publication_status(version).complete:
                    print(
                        f"release-cd reported failure but registries and GitHub Release are complete for {version.tag}",
                        flush=True,
                    )
                    emit_train_event(
                        "release_cd_failed_but_complete", target_tag=version.tag
                    )
                    return
                raise
            return
    raise TimeoutError(f"timed out waiting for release-cd workflow for {version.tag}")


def run_once(*, publish: bool, wait: bool, target_queue: Path, dry_run: bool) -> str:
    assert_clean_tree()
    assert_on_main()
    best_effort_fetch_tags()
    sync_main_with_origin()
    reconcile_unpublished_local_stable_tag()
    target = select_target(target_queue)
    assert_release_gate_allows_target(target)
    previous = latest_stable_before(target.version)
    version = target.version
    local_target_tag_exists = git_ref_exists(f"refs/tags/{version.tag}")
    if (
        not local_target_tag_exists
        and not truthy_env(os.environ.get(FORCE_CADENCE_ENV, ""))
        and not commits_since_tag_have_real_work(previous.tag)
    ):
        emit_train_event(
            "cadence_skipped",
            previous_tag=previous.tag,
            target_tag=version.tag,
            force_cadence=truthy_env(os.environ.get(FORCE_CADENCE_ENV, "")),
            reason="no_real_work_since_previous_tag",
        )
        print(
            f"autodev-train stable: no real work since {previous.tag}; skipping cadence cycle",
            flush=True,
        )
        return previous.tag
    if not local_target_tag_exists:
        product_delta = product_delta_for_target(target, previous)
        if not product_delta.allowed:
            emit_train_event(
                "product_delta_skipped",
                previous_tag=previous.tag,
                target_tag=version.tag,
                reason=product_delta.reason,
                product_files=product_delta.product_files,
                product_support_files=product_delta.product_support_files,
                support_only_files=product_delta.support_only_files,
                ignored_files=product_delta.ignored_files,
            )
            print(
                "autodev-train stable: no product implementation delta since "
                f"{previous.tag}; skipping {version.tag} ({product_delta.reason})",
                flush=True,
            )
            return previous.tag

    if local_target_tag_exists or remote_tag_exists(version.tag):
        if publish:
            status = publication_status(version)
            if status.unknown:
                raise RuntimeError(
                    f"cannot auto-recover {version.tag}: publication status probe is incomplete; retry later"
                )
            if not status.complete and local_tag_points_to_head(version.tag):
                resume_tagged_release_publish(version, wait=wait)
            else:
                recover_existing_release(version)
            return version.tag
        raise RuntimeError(f"stable tag already exists: {version.tag}")

    print(
        f"autodev-train stable: preparing {version.tag} from {previous.tag}; channel={target.channel}",
        flush=True,
    )
    emit_train_event(
        "cycle_prepare",
        previous_tag=previous.tag,
        target_tag=version.tag,
        channel=target.channel,
        publish=publish,
        wait=wait,
        dry_run=dry_run,
    )
    if dry_run:
        print(
            json.dumps(
                {
                    "action": "prepare_stable",
                    "base": previous.tag,
                    "channel": target.channel,
                    "publish": publish,
                    "version": version.tag,
                    "wait": wait,
                },
                indent=2,
                sort_keys=True,
            ),
            flush=True,
        )
        return version.tag
    update_versions(version)
    write_release_notes(previous, version)
    build_artifacts(version)
    write_release_metadata(version)
    run_local_validation(version)
    commit_and_tag(version)
    if publish:
        push_and_dispatch(version, wait=wait)
    else:
        print(
            f"autodev-train stable: prepared local tag {version.tag}; publish disabled",
            flush=True,
        )
        emit_train_event("cycle_prepared_local", target_tag=version.tag, publish=False)
    return version.tag


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=DEFAULT_POLL_SECONDS)
    parser.add_argument("--stop-file", type=Path, default=DEFAULT_STOP_FILE)
    parser.add_argument("--target-queue", type=Path, default=DEFAULT_TARGET_QUEUE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-publish", action="store_true")
    parser.add_argument("--no-wait", action="store_true")
    args = parser.parse_args(argv)

    while True:
        if args.stop_file.exists():
            print(
                f"autodev-train stable: STOP file exists: {args.stop_file}", flush=True
            )
            return 0
        try:
            result = run_once(
                publish=not args.no_publish,
                wait=not args.no_wait,
                target_queue=args.target_queue,
                dry_run=args.dry_run,
            )
        except Exception as exc:
            if not args.continuous:
                raise
            emit_train_event(
                "cycle_failed", error=str(exc), poll_seconds=args.poll_seconds
            )
            print(
                f"autodev-train stable: cycle failed; sleeping {args.poll_seconds}s before retry: {exc}",
                flush=True,
            )
            time.sleep(args.poll_seconds)
            continue
        if not args.continuous:
            return 0 if result else 1
        emit_train_event(
            "cycle_finished", result=result, poll_seconds=args.poll_seconds
        )
        print(
            f"autodev-train stable: cycle finished for {result}; sleeping {args.poll_seconds}s",
            flush=True,
        )
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
