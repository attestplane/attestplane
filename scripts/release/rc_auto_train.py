#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Autodev release-candidate train.

This is the RC counterpart to the historical alpha train. It advances one RC
only when the repository HEAD has commits after the latest RC tag, prepares
local package artifacts, commits the version bump, creates an immutable tag,
pushes main plus that tag, and delegates publication to GitHub release-cd.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RC_TAG_RE = re.compile(r"^v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)-rc\.(?P<ordinal>\d+)$")
MAX_RC_ORDINAL_PER_PATCH = 10
DEFAULT_STOP_FILE = ROOT / "release" / "alpha-train" / "STOP"
DEFAULT_POLL_SECONDS = 300
GIT_HTTP_VERSION = "HTTP/1.1"
REMOTE_PROBE_TIMEOUT_SECONDS = 30


@dataclass(frozen=True, order=True)
class RcVersion:
    major: int
    minor: int
    patch: int
    ordinal: int

    @classmethod
    def parse(cls, tag: str) -> "RcVersion":
        match = RC_TAG_RE.fullmatch(tag)
        if match is None:
            raise ValueError(f"invalid RC tag: {tag}")
        return cls(*(int(match.group(name)) for name in ("major", "minor", "patch", "ordinal")))

    @property
    def tag(self) -> str:
        return f"v{self.major}.{self.minor}.{self.patch}-rc.{self.ordinal}"

    @property
    def python_version(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}rc{self.ordinal}"

    @property
    def npm_version(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}-rc.{self.ordinal}"

    def next(self) -> "RcVersion":
        if self.ordinal >= MAX_RC_ORDINAL_PER_PATCH:
            return RcVersion(self.major, self.minor, self.patch + 1, 1)
        return RcVersion(self.major, self.minor, self.patch, self.ordinal + 1)


def run(argv: list[str], *, env: dict[str, str] | None = None, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(argv), flush=True)
    return subprocess.run(
        argv,
        cwd=ROOT,
        env=env,
        text=True,
        check=True,
        timeout=timeout,
    )


def capture(argv: list[str], *, timeout: int | None = None) -> str:
    result = subprocess.run(
        argv,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        timeout=timeout,
    )
    return result.stdout.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_clean_tree() -> None:
    status = capture(["git", "status", "--short"])
    if status:
        raise RuntimeError("working tree must be clean before RC autodev train execution")


def assert_on_main() -> None:
    branch = capture(["git", "branch", "--show-current"])
    if branch != "main":
        raise RuntimeError(f"RC autodev train must run on main, currently on {branch!r}")


def git_ref_exists(ref: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", ref],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def remote_tag_exists(tag: str) -> bool:
    result = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--tags", "origin", tag],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def best_effort_fetch_tags() -> None:
    try:
        run(
            ["git", "-c", f"http.version={GIT_HTTP_VERSION}", "fetch", "origin", "--tags"],
            timeout=REMOTE_PROBE_TIMEOUT_SECONDS,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"autodev-train rc: warning: best-effort tag fetch failed or timed out: {exc}", flush=True)


def latest_rc() -> RcVersion:
    raw = capture(["git", "tag", "--list", "v*-rc.*"])
    versions: list[RcVersion] = []
    for line in raw.splitlines():
        try:
            versions.append(RcVersion.parse(line.strip()))
        except ValueError:
            continue
    if not versions:
        raise RuntimeError("no existing RC tag found; seed the RC train with an initial RC first")
    return max(versions)


def head_has_changes_since(tag: str) -> bool:
    count = int(capture(["git", "rev-list", "--count", f"{tag}..HEAD"]))
    return count > 0


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


def update_versions(version: RcVersion) -> None:
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


def write_release_notes(previous: RcVersion, version: RcVersion) -> None:
    path = ROOT / "docs" / "release-notes" / f"{version.tag}.draft.md"
    commits = capture(["git", "log", "--oneline", f"{previous.tag}..HEAD"])
    changes = [f"- `{line}`" for line in commits.splitlines()[:20]]
    if not changes:
        changes = ["- No source changes after the previous RC tag."]
    path.write_text(
        "\n".join(
            [
                f"# {version.tag}",
                "",
                f"`{version.tag}` is an automated release-candidate cut from the autodev-train RC loop.",
                "",
                "## Changes Since Previous RC",
                "",
                *changes,
                "",
                "## Highlights",
                "",
                "- Cuts the current Attestplane SDK and verifier surface as a release-candidate package release.",
                "- Preserves deterministic verifier, release-artifact, and claim-safety boundaries.",
                "- Delegates package publication to GitHub `release-cd` after local prep and immutable tag push.",
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


def build_artifacts(version: RcVersion) -> None:
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


def artifact_paths(version: RcVersion) -> list[str]:
    return [
        f"sdk/python/dist/attestplane-{version.python_version}-py3-none-any.whl",
        f"sdk/python/dist/attestplane-{version.python_version}.tar.gz",
        f"sdk/typescript/attestplane-attestplane-{version.npm_version}.tgz",
    ]


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


def write_release_metadata(version: RcVersion) -> None:
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
            "npm_latest_change": "not performed during RC prep",
            "release_publish": "not performed during prep",
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
            "prepared_by": "autodev_train_rc_release_prep",
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
                "This plan documents artifacts prepared for the RC release path.",
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
                f"gh workflow run release-cd.yml -f release_tag={version.tag} -f channel=rc -f dry_run=false --ref main",
                "```",
                "",
                "## Explicit Non-Actions in Release Prep",
                "",
                "- Force push: not performed.",
                "- npm `latest` dist-tag change: not performed during RC prep.",
                "- Deploy: not performed.",
                "- Workflow dispatch: not performed during local prep.",
                "- Registry publication: not performed during local prep.",
                "",
                "## Claim Boundary",
                "",
                "This RC candidate is limited to the package artifacts listed above. Legal,",
                "compliance, certification, provenance-attestation, and supply-chain assurance",
                "categories remain out of scope unless backed by separate verified artifacts.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def run_local_validation(version: RcVersion) -> None:
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
            "rc",
            "--repo-root",
            str(ROOT),
        ]
    )


def commit_and_tag(version: RcVersion) -> None:
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


def push_and_dispatch(version: RcVersion, *, wait: bool) -> None:
    run(["git", "push", "origin", "main"])
    run(["git", "push", "origin", version.tag])
    run(
        [
            "gh",
            "workflow",
            "run",
            "release-cd.yml",
            "-f",
            f"release_tag={version.tag}",
            "-f",
            "channel=rc",
            "-f",
            "dry_run=false",
            "--ref",
            "main",
        ]
    )
    if wait:
        wait_for_release_cd(version)


def wait_for_release_cd(version: RcVersion) -> None:
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
            run(["gh", "run", "watch", run_id, "--exit-status"])
            return
    raise TimeoutError(f"timed out waiting for release-cd workflow for {version.tag}")


def run_once(*, publish: bool, wait: bool) -> str:
    assert_clean_tree()
    assert_on_main()
    best_effort_fetch_tags()
    previous = latest_rc()
    if not head_has_changes_since(previous.tag):
        print(f"autodev-train rc: no commits after {previous.tag}; no new RC needed", flush=True)
        return "noop"
    version = previous.next()
    if git_ref_exists(f"refs/tags/{version.tag}") or remote_tag_exists(version.tag):
        raise RuntimeError(f"next RC tag already exists: {version.tag}")
    if read_python_version() != previous.python_version or read_npm_version() != previous.npm_version:
        raise RuntimeError(
            f"package versions do not match latest RC {previous.tag}; "
            f"expected {previous.python_version} and {previous.npm_version}"
        )

    print(f"autodev-train rc: preparing {version.tag} from {previous.tag}", flush=True)
    update_versions(version)
    write_release_notes(previous, version)
    build_artifacts(version)
    write_release_metadata(version)
    run_local_validation(version)
    commit_and_tag(version)
    if publish:
        push_and_dispatch(version, wait=wait)
    else:
        print(f"autodev-train rc: prepared local tag {version.tag}; publish disabled", flush=True)
    return version.tag


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=DEFAULT_POLL_SECONDS)
    parser.add_argument("--stop-file", type=Path, default=DEFAULT_STOP_FILE)
    parser.add_argument("--no-publish", action="store_true")
    parser.add_argument("--no-wait", action="store_true")
    args = parser.parse_args(argv)

    while True:
        if args.stop_file.exists():
            print(f"autodev-train rc: STOP file exists: {args.stop_file}", flush=True)
            return 0
        result = run_once(publish=not args.no_publish, wait=not args.no_wait)
        if not args.continuous:
            return 0 if result else 1
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
