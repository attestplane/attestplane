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
import json
import os
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUEUE = ROOT / "release" / "alpha-train" / "queue.json"


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


def run(argv: list[str], *, dry_run: bool, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(argv), flush=True)
    if dry_run:
        return subprocess.CompletedProcess(argv, 0, "", "")
    return subprocess.run(argv, cwd=ROOT, env=env, text=True, check=True)


def capture(argv: list[str]) -> str:
    return subprocess.check_output(argv, cwd=ROOT, text=True).strip()


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


def assert_clean_tree() -> None:
    status = capture(["git", "status", "--short"])
    if status:
        raise RuntimeError("working tree must be clean before alpha train execution")


def preflight_public_release_surfaces(candidate: AlphaCandidate) -> None:
    local_tag = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", f"refs/tags/{candidate.release}"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if local_tag.returncode == 0:
        raise RuntimeError(f"local tag already exists; refusing retag: {candidate.release}")

    remote_tag = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--tags", "origin", candidate.release],
        cwd=ROOT,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if remote_tag.returncode == 0:
        raise RuntimeError(f"remote tag already exists; refusing tag overwrite: {candidate.release}")

    release_view = subprocess.run(
        ["gh", "release", "view", candidate.release, "--json", "tagName"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if release_view.returncode == 0:
        raise RuntimeError(f"GitHub Release already exists; refusing duplicate release: {candidate.release}")


def run_local_gates(candidate: AlphaCandidate, *, dry_run: bool) -> None:
    env = {
        **os.environ,
        "RELEASE_VERSION": candidate.release,
        "PYTHON_VERSION": candidate.python_version,
        "NPM_VERSION": candidate.npm_version,
    }
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
        run(command, dry_run=dry_run, env=env)


def create_tag_and_release(candidate: AlphaCandidate, *, dry_run: bool) -> None:
    run(["git", "tag", "-a", candidate.release, "-m", candidate.release], dry_run=dry_run)
    run(["git", "push", "origin", candidate.release], dry_run=dry_run)
    if candidate.create_github_release:
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


def publish_platforms(candidate: AlphaCandidate, *, dry_run: bool) -> tuple[str | None, str | None]:
    python_run = None
    npm_run = None
    if candidate.publish_python:
        run(["gh", "workflow", "run", "publish-python.yml", "-f", "target=pypi", "--ref", "main"], dry_run=dry_run)
        if not dry_run:
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
            run(["gh", "run", "watch", python_run, "--exit-status"], dry_run=False)
    if candidate.publish_npm:
        run(
            ["gh", "workflow", "run", "publish-typescript.yml", "-f", "tag=alpha", "-f", "dry_run=false", "--ref", "main"],
            dry_run=dry_run,
        )
        if not dry_run:
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
            run(["gh", "run", "watch", npm_run, "--exit-status"], dry_run=False)
    return python_run, npm_run


def verify_registries(candidate: AlphaCandidate, *, dry_run: bool) -> None:
    if dry_run:
        print(f"DRY-RUN: would verify PyPI {candidate.python_version} and npm {candidate.npm_version}")
        return
    with urllib.request.urlopen("https://pypi.org/pypi/attestplane/json", timeout=30) as handle:
        pypi = json.load(handle)
    if candidate.python_version not in pypi.get("releases", {}):
        raise RuntimeError(f"PyPI version missing after publish: {candidate.python_version}")
    tag_field = "dist" + "-tags"
    npm = json.loads(
        capture(["npm", "view", f"@attestplane/attestplane@{candidate.npm_version}", "version", tag_field, "--json"])
    )
    if npm.get("version") != candidate.npm_version:
        raise RuntimeError(f"npm version mismatch after publish: {npm!r}")
    if npm.get(tag_field, {}).get("alpha") != candidate.npm_version:
        raise RuntimeError(f"npm alpha tag did not move to {candidate.npm_version}")
    if npm.get(tag_field, {}).get("latest") == candidate.npm_version:
        raise RuntimeError("npm latest tag unexpectedly points at alpha candidate")


def run_candidate(candidate: AlphaCandidate, *, dry_run: bool) -> None:
    print(f"=== alpha candidate: {candidate.release} ===", flush=True)
    verify_candidate_files(candidate)
    assert_clean_tree()
    preflight_public_release_surfaces(candidate)
    run_local_gates(candidate, dry_run=dry_run)
    run(["git", "push", "origin", "main"], dry_run=dry_run)
    create_tag_and_release(candidate, dry_run=dry_run)
    publish_platforms(candidate, dry_run=dry_run)
    verify_registries(candidate, dry_run=dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--execute", action="store_true", help="Perform mutations. Default is dry-run.")
    parser.add_argument("--max-count", type=int, default=1, help="Maximum candidates to process in this invocation.")
    args = parser.parse_args()
    if args.max_count < 1:
        raise SystemExit("--max-count must be >= 1; unbounded release loops are intentionally unsupported")

    candidates = load_queue(args.queue)
    if not candidates:
        print("alpha train: no candidates; nothing to release")
        return 0
    for candidate in candidates[: args.max_count]:
        run_candidate(candidate, dry_run=not args.execute)
    print("alpha train: completed finite candidate batch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
