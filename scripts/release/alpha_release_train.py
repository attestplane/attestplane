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
import hashlib
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
DEFAULT_PROPOSALS_DIR = ROOT / "release" / "alpha-train" / "proposals"
DEFAULT_REPORTS_DIR = ROOT / "release" / "alpha-train" / "reports"
DEFAULT_STATE_FILE = ROOT / "release" / "alpha-train" / "reports" / "continuous-state.json"
DEFAULT_STOP_FILE = ROOT / "release" / "alpha-train" / "STOP"
DEFAULT_MAX_RELEASES_PER_DAY = 1

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
    remote_tag = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--tags", "origin", release],
        cwd=ROOT,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return remote_tag.returncode == 0


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
            ]
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
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
            "- Keep npm latest unchanged; alpha channel only.",
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


def advisory_header(prompt: str, removed_lines: list[str]) -> str:
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return "\n".join(
        [
            "# Next Alpha Advisory Issue Plan",
            "",
            "STATUS: ADVISORY",
            "AUTHORITY: NOT_AUTHORIZED_FOR_PUBLISH",
            "SCOPE: ISSUE_PLANNING_ONLY",
            f"PROMPT_SHA256: {prompt_hash}",
            f"REMOVED_FORBIDDEN_COMMAND_LINES: {len(removed_lines)}",
            "",
            "> This file is not a release queue entry, not approval, and not",
            "> authorization to tag, publish, deploy, close issues, or change npm latest.",
            "",
        ]
    )


def write_advisory_plan(raw_output: str, *, prompt: str, proposals_dir: Path) -> Path:
    cleaned, removed = strip_forbidden_advisory_commands(raw_output)
    proposals_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    output = proposals_dir / f"next-alpha-{stamp}.md"
    tmp = output.with_suffix(".tmp")
    tmp.write_text(advisory_header(prompt, removed) + cleaned, encoding="utf-8")
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
        raw_output = subprocess.check_output(
            ["ask_opus.sh", "architect", prompt],
            cwd=ROOT,
            text=True,
            timeout=timeout_seconds,
        )
    output = write_advisory_plan(raw_output, prompt=prompt, proposals_dir=proposals_dir)
    try:
        display = output.relative_to(ROOT)
    except ValueError:
        display = output
    print(f"alpha advisory issue plan written: {display}")
    return output


def write_pipeline_report(
    *,
    advisory_plan: Path | None,
    queue: Path,
    candidates: list[AlphaCandidate],
    executed: bool,
    reports_dir: Path,
) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    report = reports_dir / f"alpha-pipeline-{stamp}.json"
    payload = {
        "schema": "attestplane_alpha_release_pipeline_report.v1",
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
            "npm_latest_changed": False,
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


def load_continuous_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema": "attestplane_alpha_continuous_state.v1", "processed_releases": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("processed_releases"), list):
        raise ValueError(f"continuous state is malformed: {path}")
    return payload


def save_continuous_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def mark_processed(path: Path, candidate: AlphaCandidate, *, dry_run: bool) -> None:
    if dry_run:
        return
    state = load_continuous_state(path)
    processed = set(str(item) for item in state.get("processed_releases", []))
    processed.add(candidate.release)
    state["processed_releases"] = sorted(processed)
    releases_by_day = dict(state.get("release_count_by_day", {}))
    day = time.strftime("%Y-%m-%d", time.gmtime())
    releases_by_day[day] = int(releases_by_day.get(day, 0)) + 1
    state["release_count_by_day"] = releases_by_day
    state["updated_at_epoch"] = int(time.time())
    save_continuous_state(path, state)


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
            queue_candidates = merge_prepared_candidates(args.queue, discovered, dry_run=not args.execute)
            print(f"alpha train: auto-promote discovered {len(discovered)} prepared candidates", flush=True)

        candidates = unprocessed_candidates(queue_candidates, args.state_file)
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
            )
            print(f"alpha pipeline report written: {display_path(report)}")

        if candidates:
            for candidate in candidates[: args.max_count]:
                try:
                    run_candidate(candidate, dry_run=not args.execute)
                    mark_processed(args.state_file, candidate, dry_run=not args.execute)
                except Exception as exc:
                    if args.execute:
                        request_stop(args.stop_file, f"fail-closed after {candidate.release}: {type(exc).__name__}")
                    raise
            cycles += 1
        else:
            print(f"alpha train: no unprocessed candidates; sleeping {args.poll_seconds}s", flush=True)
            cycles += 1

        if args.idle_exit_after and cycles >= args.idle_exit_after:
            print("alpha train: idle-exit limit reached")
            return 0
        time.sleep(args.poll_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--execute", action="store_true", help="Perform mutations. Default is dry-run.")
    parser.add_argument("--max-count", type=int, default=1, help="Maximum candidates to process in this invocation.")
    parser.add_argument("--plan-next-alpha", action="store_true", help="Call Opus advisory to draft next-alpha issues first.")
    parser.add_argument("--pipeline", action="store_true", help="Run the linked advisory-plan then finite release-queue pipeline.")
    parser.add_argument("--continuous", action="store_true", help="Continuously watch the queue until manually stopped.")
    parser.add_argument(
        "--auto-promote-prepared",
        action="store_true",
        help="Continuously add fully prepared local alpha artifacts to the queue. Advisory text is never promoted.",
    )
    parser.add_argument("--advisor-timeout", type=int, default=120, help="Seconds to wait for Opus advisory planning.")
    parser.add_argument("--plan-interval-seconds", type=int, default=3600, help="Minimum seconds between Opus advisory planning calls in continuous mode.")
    parser.add_argument("--poll-seconds", type=int, default=300, help="Seconds to sleep between continuous queue checks.")
    parser.add_argument("--idle-exit-after", type=int, default=0, help="Testing helper: exit continuous mode after N cycles. 0 means never.")
    parser.add_argument("--max-releases-per-day", type=int, default=DEFAULT_MAX_RELEASES_PER_DAY, help="UTC daily release cap in continuous execute mode. 0 means unlimited.")
    parser.add_argument("--stop-file", type=Path, default=DEFAULT_STOP_FILE, help="If this file exists, continuous mode exits before starting the next cycle.")
    parser.add_argument("--proposals-dir", type=Path, default=DEFAULT_PROPOSALS_DIR)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    args = parser.parse_args()
    if args.max_count < 1:
        raise SystemExit("--max-count must be >= 1; unbounded release loops are intentionally unsupported")
    if args.poll_seconds < 1:
        raise SystemExit("--poll-seconds must be >= 1")
    if args.plan_interval_seconds < 1:
        raise SystemExit("--plan-interval-seconds must be >= 1")
    if args.max_releases_per_day < 0:
        raise SystemExit("--max-releases-per-day must be >= 0")
    if args.continuous:
        return run_continuous_pipeline(args)

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
        )
        print(f"alpha pipeline report written: {display_path(report)}")
    if not candidates:
        print("alpha train: no candidates; nothing to release")
        return 0
    for candidate in candidates[: args.max_count]:
        run_candidate(candidate, dry_run=not args.execute)
    print("alpha train: completed finite candidate batch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
