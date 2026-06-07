#!/usr/bin/env python3
"""Validate Attestplane GitHub CD release inputs.

This script is intentionally local and deterministic. It reads package version
metadata, validates the release tag/channel policy, and optionally writes
GitHub Actions outputs. It never creates tags, publishes packages, or reads
secrets.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

TAG_RE = re.compile(
    r"^v(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<channel>alpha|beta|rc)\.(?P<ordinal>0|[1-9]\d*))?$"
)
MAX_RC_ORDINAL_PER_PATCH = 10


class ReleaseCdPolicyError(ValueError):
    """Raised when the requested release violates the CD policy."""


@dataclass(frozen=True)
class ReleaseCdDecision:
    release_tag: str
    channel: str
    python_version: str
    npm_version: str
    npm_dist_tag: str
    is_prerelease: bool


def parse_release_tag(release_tag: str) -> dict[str, str]:
    match = TAG_RE.match(release_tag)
    if match is None:
        raise ReleaseCdPolicyError(
            "release tag must match vMAJOR.MINOR.PATCH or "
            "vMAJOR.MINOR.PATCH-(alpha|beta|rc).N"
        )
    return {k: v for k, v in match.groupdict().items() if v is not None}


def expected_versions(release_tag: str) -> tuple[str, str, str, bool]:
    parts = parse_release_tag(release_tag)
    base = f"{parts['major']}.{parts['minor']}.{parts['patch']}"
    channel = parts.get("channel")
    ordinal = parts.get("ordinal")
    if channel is None:
        return base, base, "latest", False
    assert ordinal is not None
    if channel == "rc" and int(ordinal) > MAX_RC_ORDINAL_PER_PATCH:
        next_patch = int(parts["patch"]) + 1
        next_tag = f"v{parts['major']}.{parts['minor']}.{next_patch}-rc.1"
        raise ReleaseCdPolicyError(
            f"RC ordinal {ordinal} exceeds the per-patch maximum "
            f"{MAX_RC_ORDINAL_PER_PATCH}; use {next_tag} instead"
        )
    py_suffix = {"alpha": "a", "beta": "b", "rc": "rc"}[channel]
    return f"{base}{py_suffix}{ordinal}", f"{base}-{channel}.{ordinal}", channel, True


def _git_show_text(repo_root: Path, ref: str, path: str) -> str:
    git = shutil.which("git")
    if git is None:
        raise ReleaseCdPolicyError("git executable not found")
    result = subprocess.run(  # noqa: S603 - fixed git executable with validated release refs and no shell.
        [git, "show", f"{ref}:{path}"],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def read_python_version(repo_root: Path, metadata_ref: str | None = None) -> str:
    if metadata_ref is not None:
        data = tomllib.loads(_git_show_text(repo_root, metadata_ref, "sdk/python/pyproject.toml"))
        try:
            return str(data["project"]["version"])
        except KeyError as exc:
            raise ReleaseCdPolicyError("sdk/python/pyproject.toml missing project.version") from exc

    with (repo_root / "sdk/python/pyproject.toml").open("rb") as f:
        data = tomllib.load(f)
    try:
        return str(data["project"]["version"])
    except KeyError as exc:
        raise ReleaseCdPolicyError("sdk/python/pyproject.toml missing project.version") from exc


def read_npm_version(repo_root: Path, metadata_ref: str | None = None) -> str:
    try:
        if metadata_ref is not None:
            raw = _git_show_text(repo_root, metadata_ref, "sdk/typescript/package.json")
        else:
            raw = (repo_root / "sdk/typescript/package.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        return str(data["version"])
    except KeyError as exc:
        raise ReleaseCdPolicyError("sdk/typescript/package.json missing version") from exc


# Both SDKs must derive their runtime version from package metadata (pyproject
# `version` / package.json `version`) rather than a hand-maintained literal, so
# the module-level version can never drift from the published artifact. A
# hardcoded literal previously shipped a stale "1.8.4" inside 1.9.x/1.10.0.
# The optional `(?::[^=]+)?` tolerates a type annotation (`VERSION: string =`,
# `__version__: str =`); the char class includes a backtick so a template
# literal (`VERSION = `1.8.4``) is also caught.
_VERSION_SOURCE_LITERALS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "sdk/python/src/attestplane/__init__.py",
        re.compile(r'^__version__\b\s*(?::[^=]+)?=\s*["\']\d', re.M),
    ),
    (
        "sdk/typescript/src/index_version.ts",
        re.compile(r'\bVERSION\b\s*(?::[^=]+)?=\s*["\'`]\d'),
    ),
)


def assert_version_sources_derive(repo_root: Path, metadata_ref: str | None = None) -> None:
    """Fail if either SDK reintroduces a hand-maintained version literal.

    Tolerant of a missing source file (other gates cover structural absence);
    this guard only rejects a *present* file that hardcodes the version,
    blocking reintroduction of the literal-drift class of bug.
    """
    for rel_path, literal_re in _VERSION_SOURCE_LITERALS:
        if metadata_ref is not None:
            try:
                text = _git_show_text(repo_root, metadata_ref, rel_path)
            except (ReleaseCdPolicyError, subprocess.CalledProcessError):
                # Source file absent from the ref -> tolerated (see docstring).
                continue
        else:
            source = repo_root / rel_path
            if not source.is_file():
                continue
            text = source.read_text(encoding="utf-8")
        if literal_re.search(text):
            raise ReleaseCdPolicyError(
                f"{rel_path} reintroduces a hardcoded version literal; the SDK "
                f"version must derive from package metadata (single source of truth)"
            )


def decide_release(
    *,
    release_tag: str,
    requested_channel: str,
    repo_root: Path,
    metadata_ref: str | None = None,
    allow_prerelease_latest: bool = False,
) -> ReleaseCdDecision:
    expected_python, expected_npm, canonical_channel, is_prerelease = expected_versions(release_tag)
    if requested_channel != canonical_channel:
        if not (allow_prerelease_latest and is_prerelease and requested_channel == "latest"):
            raise ReleaseCdPolicyError(
                f"channel {requested_channel!r} does not match release tag {release_tag!r}; "
                f"expected {canonical_channel!r}"
            )

    if is_prerelease and requested_channel == "latest" and not allow_prerelease_latest:
        raise ReleaseCdPolicyError("pre-release packages must not publish with npm latest")

    python_version = read_python_version(repo_root, metadata_ref=metadata_ref)
    npm_version = read_npm_version(repo_root, metadata_ref=metadata_ref)
    if python_version != expected_python:
        raise ReleaseCdPolicyError(
            f"Python package version {python_version!r} does not match {release_tag!r}; "
            f"expected {expected_python!r}"
        )
    if npm_version != expected_npm:
        raise ReleaseCdPolicyError(
            f"npm package version {npm_version!r} does not match {release_tag!r}; "
            f"expected {expected_npm!r}"
        )

    assert_version_sources_derive(repo_root, metadata_ref=metadata_ref)

    return ReleaseCdDecision(
        release_tag=release_tag,
        channel=requested_channel,
        python_version=python_version,
        npm_version=npm_version,
        npm_dist_tag=requested_channel,
        is_prerelease=is_prerelease,
    )


def write_github_outputs(decision: ReleaseCdDecision) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as f:
        f.write(f"release_tag={decision.release_tag}\n")
        f.write(f"channel={decision.channel}\n")
        f.write(f"python_version={decision.python_version}\n")
        f.write(f"npm_version={decision.npm_version}\n")
        f.write(f"npm_dist_tag={decision.npm_dist_tag}\n")
        f.write(f"is_prerelease={str(decision.is_prerelease).lower()}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--channel", required=True, choices=["alpha", "beta", "rc", "latest"])
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--metadata-ref",
        help="Read package versions from this Git ref instead of the current working tree.",
    )
    parser.add_argument(
        "--allow-prerelease-latest",
        action="store_true",
        help="Allow a maintainer-recorded prerelease latest movement.",
    )
    args = parser.parse_args(argv)

    try:
        decision = decide_release(
            release_tag=args.release_tag,
            requested_channel=args.channel,
            repo_root=args.repo_root.resolve(),
            metadata_ref=args.metadata_ref,
            allow_prerelease_latest=args.allow_prerelease_latest,
        )
    except ReleaseCdPolicyError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 2

    write_github_outputs(decision)
    print(
        "release CD policy ok: "
        f"tag={decision.release_tag} python={decision.python_version} "
        f"npm={decision.npm_version} npm_dist_tag={decision.npm_dist_tag}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
