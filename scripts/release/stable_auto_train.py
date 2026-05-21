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

The train does not force-push, delete tags, publish directly from the local
machine, or move npm ca. Suffix-free stable packages publish through
release-cd with channel=latest, which also means PyPI default installs advance
because PyPI has no dist-tag concept.
"""

from __future__ import annotations

import argparse
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


ROOT = Path(__file__).resolve().parents[2]
RELEASE_GATE_PATH = ROOT / "scripts" / "release" / "release_gate.py"
STABLE_TAG_RE = re.compile(r"^v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")
DEFAULT_STOP_FILE = ROOT / "release" / "alpha-train" / "STOP"
DEFAULT_TARGET_QUEUE = ROOT / "release" / "autodev-train-targets.json"
DEFAULT_POLL_SECONDS = 300
GIT_HTTP_VERSION = "HTTP/1.1"
REMOTE_PROBE_TIMEOUT_SECONDS = 30
REMOTE_PUSH_ATTEMPTS = 3
REMOTE_PUSH_RETRY_SECONDS = 10
REMOTE_PUSH_TIMEOUT_SECONDS = 120
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


@dataclass(frozen=True, order=True)
class StableVersion:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "StableVersion":
        normalized = value.removeprefix("v")
        match = re.fullmatch(r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)", normalized)
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

    @property
    def complete(self) -> bool:
        return self.python_visible and self.npm_visible and self.npm_latest and self.github_release

    @property
    def unknown(self) -> bool:
        return (
            self.python_visible is None
            or self.npm_visible is None
            or self.npm_latest is None
            or self.github_release is None
        )


def run(argv: list[str], *, env: dict[str, str] | None = None, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
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
        raise subprocess.CalledProcessError(result.returncode, argv, output=out, stderr=err)
    return result


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
    if (
        len(argv) >= 5
        and argv[0] == "git"
        and argv[1] == "-c"
        and argv[2] == f"http.version={GIT_HTTP_VERSION}"
        and argv[3] == "push"
    ):
        return argv
    if len(argv) >= 4 and argv[:3] == ["git", "push", "origin"]:
        return ["git", "-c", f"http.version={GIT_HTTP_VERSION}", *argv[1:]]
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
            f"git push preflight remote probe failed ({preflight_reason}); attempting push anyway",
            flush=True,
        )

    last_error: subprocess.CalledProcessError | subprocess.TimeoutExpired | None = None
    for attempt in range(1, REMOTE_PUSH_ATTEMPTS + 1):
        try:
            return attempt_git_push_once(argv)
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


def attempt_git_push_once(argv: list[str]) -> subprocess.CompletedProcess[str]:
    argv = normalize_git_push_argv(argv)
    result = run_process(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=REMOTE_PUSH_TIMEOUT_SECONDS,
    )
    echo_subprocess_output(result.stdout)
    echo_subprocess_output(result.stderr)
    if result.returncode == 0:
        return result
    raise subprocess.CalledProcessError(result.returncode, argv, output=result.stdout, stderr=result.stderr)


def echo_subprocess_output(text: str | None) -> None:
    if not text:
        return
    print(text, end="" if text.endswith("\n") else "\n", flush=True)


def git_push_remote_converged(argv: list[str]) -> bool:
    return git_push_remote_status(argv)[0]


def git_push_remote_status(argv: list[str]) -> tuple[bool, str | None]:
    argv = normalize_git_push_argv(argv)
    if len(argv) != 6 or argv[:4] != ["git", "-c", f"http.version={GIT_HTTP_VERSION}", "push"] or argv[4] != "origin":
        return False, None
    ref = argv[5]
    try:
        if ref == "main":
            local_head = capture(["git", "rev-parse", "HEAD"], timeout=REMOTE_PROBE_TIMEOUT_SECONDS)
            remote_head = capture(["git", "ls-remote", "origin", "refs/heads/main"], timeout=REMOTE_PROBE_TIMEOUT_SECONDS)
            return bool(remote_head) and remote_head.split()[0] == local_head, None
        if STABLE_TAG_RE.fullmatch(ref):
            remote_tag = capture(["git", "ls-remote", "origin", f"refs/tags/{ref}"], timeout=REMOTE_PROBE_TIMEOUT_SECONDS)
            return bool(remote_tag), None
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
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
    if any(phrase in text for phrase in ("non-fast-forward", "fetch first", "rejected", "failed to push some refs")):
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
        raise RuntimeError("working tree must be clean before stable autodev train execution")


def assert_on_main() -> None:
    branch = capture(["git", "branch", "--show-current"])
    if branch != "main":
        raise RuntimeError(f"stable autodev train must run on main, currently on {branch!r}")


def git_ref_exists(ref: str) -> bool:
    result = run_process(
        ["git", "rev-parse", "-q", "--verify", ref],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def remote_tag_exists(tag: str) -> bool:
    try:
        result = run_process(
            ["git", "ls-remote", "--exit-code", "--tags", "origin", tag],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=REMOTE_PROBE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        print(f"autodev-train stable: warning: remote tag probe timed out for {tag}: {exc}", flush=True)
        return False
    return result.returncode == 0


def local_tag_points_to_head(tag: str) -> bool:
    try:
        tag_commit = capture(["git", "rev-parse", f"{tag}^{{commit}}"])
        head_commit = capture(["git", "rev-parse", "HEAD"])
    except subprocess.CalledProcessError:
        return False
    return tag_commit == head_commit


def best_effort_fetch_tags() -> None:
    try:
        run(
            ["git", "-c", f"http.version={GIT_HTTP_VERSION}", "fetch", "origin", "--tags"],
            timeout=REMOTE_PROBE_TIMEOUT_SECONDS,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"autodev-train stable: warning: best-effort tag fetch failed or timed out: {exc}", flush=True)


def list_stable_tags() -> list[StableVersion]:
    raw = capture(["git", "tag", "--list", "v*.*.*"])
    versions: list[StableVersion] = []
    for line in raw.splitlines():
        try:
            versions.append(StableVersion.parse_tag(line.strip()))
        except ValueError:
            continue
    return sorted(versions)


def latest_stable_before(target: StableVersion) -> StableVersion:
    candidates = [version for version in list_stable_tags() if version < target]
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
            raise RuntimeError(f"target {version.tag} min_soak_hours must be non-negative")
        if status == "queued":
            targets.append(ReleaseTarget(version=version, channel=channel, min_soak_hours=min_soak_hours))
    return targets


def select_target(path: Path) -> ReleaseTarget:
    try:
        base = latest_stable()
    except RuntimeError:
        base = None
    if base is not None and not publication_status(base).complete:
        print(f"autodev-train stable: latest tag {base.tag} is not fully published; recovering before advancing", flush=True)
        return ReleaseTarget(version=base, channel="latest", min_soak_hours=0)

    for target in load_target_queue(path):
        if git_ref_exists(f"refs/tags/{target.version.tag}") or remote_tag_exists(target.version.tag):
            print(f"autodev-train stable: target {target.version.tag} already has stable tag; skipping", flush=True)
            continue
        return target
    base = latest_stable()
    generated = next_stable_after(base)
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
        audit_verified=release_gate.truthy(os.environ.get("ATTESTPLANE_RELEASE_AUDIT_VERIFIED", "")),
        audit_plan_url=os.environ.get("ATTESTPLANE_RELEASE_AUDIT_PLAN_URL", ""),
    )
    if not verification.allowed:
        raise RuntimeError(
            "release gate blocked stable autodev target "
            f"{target.version.tag}: {verification.reason}; reasons={','.join(decision.reasons)}"
        )


def read_python_version() -> str:
    with (ROOT / "sdk/python/pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    return str(data["project"]["version"])


def read_npm_version() -> str:
    return str(json.loads((ROOT / "sdk/typescript/package.json").read_text(encoding="utf-8"))["version"])


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
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def update_versions(version: StableVersion) -> None:
    replace_one(ROOT / "sdk/python/pyproject.toml", r'^version = "[^"]+"$', f'version = "{version.python_version}"')
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


def write_release_notes(previous: StableVersion, version: StableVersion) -> None:
    path = ROOT / "docs" / "release-notes" / f"{version.tag}.draft.md"
    commits = capture(["git", "log", "--format=%s", f"{previous.tag}..HEAD"])
    changes = [f"- {line}" for line in commits.splitlines()[:20]]
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


def artifact_entry(kind: str, name: str, package_version: str, path: str) -> dict[str, Any]:
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
        artifact_entry("python-wheel", "attestplane", version.python_version, artifact_paths(version)[0]),
        artifact_entry("python-sdist", "attestplane", version.python_version, artifact_paths(version)[1]),
        artifact_entry("npm-tarball", "@attestplane/attestplane", version.npm_version, artifact_paths(version)[2]),
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
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksums_path = release_dir / "checksums.sha256"
    checksums_path.write_text(
        "\n".join(f"{artifact['sha256']}  {artifact['path']}" for artifact in artifacts) + "\n",
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
                f"git tag -a {version.tag} -m \"{version.tag}\"",
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


def resume_tagged_release_publish(version: StableVersion, *, wait: bool) -> None:
    if not git_ref_exists(f"refs/tags/{version.tag}"):
        raise RuntimeError(f"cannot resume {version.tag}: local tag is missing")
    if not local_tag_points_to_head(version.tag):
        raise RuntimeError(f"cannot resume {version.tag}: local tag does not point to HEAD")
    print(f"autodev-train stable: resuming publish for locally tagged {version.tag}", flush=True)
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
        print(f"autodev-train stable: warning: PyPI probe failed for {version.tag}: {exc}", flush=True)
        return None
    return payload.get("info", {}).get("version") == version.python_version


def npm_version_visible(version: StableVersion) -> bool | None:
    try:
        result = run_process(
            ["npm", "view", f"@attestplane/attestplane@{version.npm_version}", "version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        print(f"autodev-train stable: warning: npm version probe timed out for {version.tag}: {exc}", flush=True)
        return None
    return result.returncode == 0 and (result.stdout or "").strip() == version.npm_version


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
        print(f"autodev-train stable: warning: npm dist-tag probe timed out for {version.tag}: {exc}", flush=True)
        return None
    return result.returncode == 0 and (result.stdout or "").strip() == version.npm_version


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
        print(f"autodev-train stable: warning: GitHub Release probe timed out for {version.tag}: {exc}", flush=True)
        return None
    return result.returncode == 0


def publication_status(version: StableVersion) -> PublicationStatus:
    status = PublicationStatus(
        python_visible=pypi_version_visible(version),
        npm_visible=npm_version_visible(version),
        npm_latest=npm_latest_points_to(version),
        github_release=github_release_exists(version),
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
    print(f"waiting for delegated publish-python workflow for {version.tag}", flush=True)
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
    raise TimeoutError(f"timed out waiting for delegated publish-python workflow for {version.tag}")


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
        run(["gh", "release", "create", version.tag, "--verify-tag", *release_flags, *assets])


def recover_existing_release(version: StableVersion) -> None:
    status = publication_status(version)
    if status.unknown:
        raise RuntimeError(f"cannot auto-recover {version.tag}: publication status probe is incomplete; retry later")
    if status.complete:
        print(f"autodev-train stable: existing release {version.tag} is complete", flush=True)
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
                print(f"autodev-train stable: recovering PyPI publish for {version.tag} (attempt {attempt}/3)", flush=True)
                dispatch_publish_python(version)
                wait_for_pypi(version)
                break
            except Exception as exc:  # noqa: BLE001 - keep continuous train recoverable after transient publisher failures.
                last_error = exc
                print(f"autodev-train stable: PyPI recovery attempt failed for {version.tag}: {exc}", flush=True)
                time.sleep(30)
        else:
            raise RuntimeError(f"cannot auto-recover PyPI publication for {version.tag}: {last_error}") from last_error
    ensure_github_release(version)
    final = publication_status(version)
    if final.unknown:
        raise RuntimeError(f"release recovery status is incomplete for {version.tag}: {final}")
    if not final.complete:
        raise RuntimeError(f"release recovery did not complete for {version.tag}: {final}")


def wait_for_push_ci(head_sha: str) -> None:
    print(f"waiting for push CI workflows for {head_sha}", flush=True)
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
            raise RuntimeError(f"push CI failed for {head_sha}: {details}")

        missing = sorted(expected - set(matched))
        pending = sorted(
            name
            for name, run in matched.items()
            if run.get("status") != "completed" or run.get("conclusion") != "success"
        )
        if not missing and not pending:
            print(f"push CI workflows passed for {head_sha}", flush=True)
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

        summary = f"missing={','.join(missing) or '-'} pending={','.join(pending) or '-'}"
        if summary != last_summary:
            print(f"push CI waiting for {head_sha}: {summary}", flush=True)
            last_summary = summary
        time.sleep(20)

    raise TimeoutError(f"timed out waiting for push CI workflows for {head_sha}")


def wait_for_release_cd(version: StableVersion) -> None:
    print(f"waiting for release-cd workflow for {version.tag}", flush=True)
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
                    print(f"release-cd reported failure but registries and GitHub Release are complete for {version.tag}", flush=True)
                    return
                raise
            return
    raise TimeoutError(f"timed out waiting for release-cd workflow for {version.tag}")


def run_once(*, publish: bool, wait: bool, target_queue: Path, dry_run: bool) -> str:
    assert_clean_tree()
    assert_on_main()
    best_effort_fetch_tags()
    target = select_target(target_queue)
    assert_release_gate_allows_target(target)
    previous = latest_stable_before(target.version)
    version = target.version
    if git_ref_exists(f"refs/tags/{version.tag}") or remote_tag_exists(version.tag):
        if publish:
            status = publication_status(version)
            if status.unknown:
                raise RuntimeError(f"cannot auto-recover {version.tag}: publication status probe is incomplete; retry later")
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
        print(f"autodev-train stable: prepared local tag {version.tag}; publish disabled", flush=True)
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
            print(f"autodev-train stable: STOP file exists: {args.stop_file}", flush=True)
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
            print(
                f"autodev-train stable: cycle failed; sleeping {args.poll_seconds}s before retry: {exc}",
                flush=True,
            )
            time.sleep(args.poll_seconds)
            continue
        if not args.continuous:
            return 0 if result else 1
        print(f"autodev-train stable: cycle finished for {result}; sleeping {args.poll_seconds}s", flush=True)
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
