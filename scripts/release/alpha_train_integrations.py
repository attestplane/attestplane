#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Read-only integration status adapter for the alpha release train.

This module gathers release-train facts from optional external tools and writes
machine-readable plus Markdown evidence. It is deliberately non-authoritative:
adapter output cannot approve, tag, publish, dispatch workflows, or move npm
dist-tags.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORTS_DIR = ROOT / "release" / "alpha-train" / "reports"
DEFAULT_STATE_FILE = DEFAULT_REPORTS_DIR / "continuous-state.json"
PACKAGE_NPM = "@attestplane/attestplane"
PACKAGE_PYPI = "attestplane"
LINEAR_GRAPHQL_URL = "https://api.linear.app/graphql"
SENTRY_API_BASE_URL = "https://sentry.io/api/0"


def generated_at() -> tuple[int, str]:
    epoch = int(time.time())
    return epoch, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def state_db_path(state_path: Path) -> Path:
    if state_path.suffix == ".sqlite":
        return state_path
    return state_path.with_suffix(".sqlite")


def alpha_python_version(release: str) -> str:
    return release.removeprefix("v").removesuffix("-alpha") + "a0"


def alpha_npm_version(release: str) -> str:
    return release.removeprefix("v")


def run_capture(argv: list[str], *, timeout: int = 20) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            argv,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, type(exc).__name__
    output = result.stdout.strip() or result.stderr.strip()
    return result.returncode == 0, output


def parse_json_output(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def collect_git_facts(release: str) -> dict[str, Any]:
    head_ok, head = run_capture(["git", "rev-parse", "HEAD"])
    remote_ok, remote = run_capture(["git", "ls-remote", "origin", "refs/heads/main"])
    tag_ok, tag = run_capture(["git", "ls-remote", "origin", f"refs/tags/{release}"])
    status_ok, status = run_capture(["git", "status", "--short"])
    remote_head = remote.split()[0] if remote_ok and remote else None
    remote_tag = tag.split()[0] if tag_ok and tag else None
    return {
        "head": head if head_ok else None,
        "remote_main_head": remote_head,
        "remote_tag_head": remote_tag,
        "main_converged": bool(head_ok and remote_head == head),
        "tag_exists": bool(remote_tag),
        "working_tree_clean": bool(status_ok and not status),
    }


def collect_sqlite_stage_facts(release: str, state_path: Path) -> dict[str, Any]:
    db_path = state_db_path(state_path)
    if not db_path.exists():
        return {
            "available": False,
            "state_db": str(db_path),
            "stages": {},
            "status": None,
        }
    with sqlite3.connect(db_path) as db:
        state = db.execute(
            "SELECT status FROM release_state WHERE release = ?", (release,)
        ).fetchone()
        try:
            stages = db.execute(
                "SELECT stage, status, detail FROM release_stages WHERE release = ? ORDER BY stage",
                (release,),
            ).fetchall()
        except sqlite3.OperationalError:
            stages = []
    return {
        "available": True,
        "state_db": str(db_path),
        "status": str(state[0]) if state else None,
        "stages": {
            str(stage): {
                "status": str(status),
                "detail": parse_json_output(str(detail)) or {},
            }
            for stage, status, detail in stages
        },
    }


def collect_github_facts(release: str) -> dict[str, Any]:
    if shutil.which("gh") is None:
        return {"available": False, "limitation": "gh_cli_not_found"}
    ok, release_json = run_capture(
        [
            "gh",
            "release",
            "view",
            release,
            "--json",
            "tagName,isPrerelease,url,assets,publishedAt,targetCommitish",
        ],
        timeout=30,
    )
    release_payload = parse_json_output(release_json) if ok else None
    ok_runs, runs_json = run_capture(
        [
            "gh",
            "run",
            "list",
            "--limit",
            "20",
            "--json",
            "databaseId,workflowName,status,conclusion,headSha,createdAt,url",
        ],
        timeout=30,
    )
    runs_payload = parse_json_output(runs_json) if ok_runs else None
    return {
        "available": True,
        "release_found": bool(release_payload),
        "release": release_payload,
        "recent_workflow_runs": runs_payload if isinstance(runs_payload, list) else [],
        "limitations": [] if ok and ok_runs else ["github_cli_query_failed"],
    }


def pypi_version_exists(version: str) -> bool:
    url = f"https://pypi.org/pypi/{PACKAGE_PYPI}/{version}/json"
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            return response.status == 200
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return False


def collect_registry_facts(release: str) -> dict[str, Any]:
    python_version = alpha_python_version(release)
    npm_version = alpha_npm_version(release)
    npm_version_ok, npm_version_text = run_capture(
        ["npm", "view", f"{PACKAGE_NPM}@{npm_version}", "version", "--json"]
    )
    npm_tags_ok, npm_tags_text = run_capture(
        ["npm", "view", PACKAGE_NPM, "dist-tags", "--json"]
    )
    npm_tags = parse_json_output(npm_tags_text) if npm_tags_ok else None
    return {
        "pypi": {
            "version": python_version,
            "published": pypi_version_exists(python_version),
        },
        "npm": {
            "version": npm_version,
            "published": bool(
                npm_version_ok and parse_json_output(npm_version_text) == npm_version
            ),
            "dist_tags": npm_tags if isinstance(npm_tags, dict) else {},
            "latest_points_to_version": bool(
                isinstance(npm_tags, dict) and npm_tags.get("latest") == npm_version
            ),
            "alpha_points_to_version": bool(
                isinstance(npm_tags, dict) and npm_tags.get("alpha") == npm_version
            ),
        },
    }


def collect_coderabbit_facts() -> dict[str, Any]:
    if shutil.which("coderabbit") is None:
        return {
            "available": False,
            "advisory_only": True,
            "limitation": "coderabbit_cli_not_found",
        }
    version_ok, version = run_capture(["coderabbit", "--version"])
    auth_ok, auth = run_capture(["coderabbit", "auth", "status", "--agent"])
    return {
        "available": True,
        "version": version if version_ok else None,
        "auth_status_available": auth_ok,
        "auth_status_summary": "authenticated"
        if auth_ok
        else "unavailable_or_unauthenticated",
        "advisory_only": True,
        "permission_granted": False,
        "limitations": [] if version_ok and auth_ok else ["coderabbit_review_not_run"],
    }


def linear_api_token() -> str | None:
    return os.getenv("LINEAR_API_KEY") or os.getenv("LINEAR_ACCESS_TOKEN")


def collect_linear_facts() -> dict[str, Any]:
    token = linear_api_token()
    if not token:
        return {
            "available": False,
            "configured": False,
            "advisory_only": True,
            "permission_granted": False,
            "workspace_observed": False,
            "workspace_name": None,
            "viewer_observed": False,
            "limitations": ["linear_api_token_missing"],
        }

    body = json.dumps(
        {"query": "query { viewer { id name } organization { id name } }"}
    ).encode("utf-8")
    request = urllib.request.Request(
        LINEAR_GRAPHQL_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = parse_json_output(response.read().decode("utf-8"))
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
    ) as exc:
        return {
            "available": True,
            "configured": True,
            "advisory_only": True,
            "permission_granted": False,
            "workspace_observed": False,
            "workspace_name": None,
            "viewer_observed": False,
            "limitations": [type(exc).__name__],
        }

    data = payload.get("data") if isinstance(payload, dict) else None
    organization = data.get("organization") if isinstance(data, dict) else None
    viewer = data.get("viewer") if isinstance(data, dict) else None
    return {
        "available": True,
        "configured": True,
        "advisory_only": True,
        "permission_granted": False,
        "workspace_observed": bool(isinstance(organization, dict)),
        "workspace_name": organization.get("name")
        if isinstance(organization, dict)
        else None,
        "viewer_observed": bool(isinstance(viewer, dict)),
        "limitations": []
        if isinstance(data, dict)
        else ["linear_api_response_unavailable"],
    }


def sentry_api_credentials() -> dict[str, str | None]:
    return {
        "auth_token": os.getenv("SENTRY_AUTH_TOKEN"),
        "organization": os.getenv("SENTRY_ORG"),
        "project": os.getenv("SENTRY_PROJECT"),
        "base_url": os.getenv("SENTRY_API_BASE_URL", SENTRY_API_BASE_URL),
    }


def collect_sentry_facts() -> dict[str, Any]:
    credentials = sentry_api_credentials()
    auth_token = credentials["auth_token"]
    organization = credentials["organization"]
    project = credentials["project"]
    base_url = str(credentials["base_url"]).rstrip("/")
    if not auth_token or not organization:
        return {
            "available": False,
            "configured": False,
            "advisory_only": True,
            "permission_granted": False,
            "organization_observed": False,
            "project_observed": False,
            "unresolved_issue_count": None,
            "limitations": ["sentry_api_credentials_missing"],
        }

    url = f"{base_url}/organizations/{urllib.parse.quote(organization)}/issues/"
    query = {"query": "is:unresolved", "statsPeriod": "14d", "per_page": "5"}
    if project:
        query["project"] = project
    request = urllib.request.Request(
        f"{url}?{urllib.parse.urlencode(query)}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = parse_json_output(response.read().decode("utf-8"))
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
    ) as exc:
        return {
            "available": True,
            "configured": True,
            "advisory_only": True,
            "permission_granted": False,
            "organization_observed": True,
            "project_observed": bool(project),
            "unresolved_issue_count": None,
            "limitations": [type(exc).__name__],
        }

    issues = payload if isinstance(payload, list) else []
    return {
        "available": True,
        "configured": True,
        "advisory_only": True,
        "permission_granted": False,
        "organization_observed": True,
        "project_observed": bool(project),
        "unresolved_issue_count": len(issues),
        "limitations": []
        if isinstance(payload, list)
        else ["sentry_issue_feed_unavailable"],
    }


def collect_codex_security_facts() -> dict[str, Any]:
    checks = [
        "gitleaks detect --source . --no-git --redact",
        "scripts/check-proofbundle-verifier.sh",
        "scripts/check-public-api.sh",
        "scripts/check-release-assets-prep.sh",
    ]
    return {
        "available": True,
        "mode": "local_security_surface_inventory",
        "advisory_only": True,
        "permission_granted": False,
        "checks": checks,
        "note": "Codex Security remains an advisory scan surface; local gates remain deterministic release checks.",
    }


def build_status_payload(release: str, *, state_path: Path) -> dict[str, Any]:
    epoch, iso = generated_at()
    payload = {
        "schema": "attestplane_alpha_integration_status.v1",
        "generated_at_epoch": epoch,
        "generated_at": iso,
        "release": release,
        "authority": {
            "authoritative": False,
            "permission_granted": False,
            "advisory_outputs_can_publish": False,
        },
        "git": collect_git_facts(release),
        "state": collect_sqlite_stage_facts(release, state_path),
        "github": collect_github_facts(release),
        "registries": collect_registry_facts(release),
        "linear": collect_linear_facts(),
        "sentry": collect_sentry_facts(),
        "coderabbit": collect_coderabbit_facts(),
        "codex_security": collect_codex_security_facts(),
        "documents": {
            "markdown_evidence_enabled": True,
            "docx_generated": False,
            "note": "Markdown evidence is generated locally; DOCX is intentionally not required for release automation.",
        },
        "explicit_non_actions": {
            "publish": "not performed by integration adapter",
            "deploy": "not performed",
            "workflow_dispatch": "not performed by integration adapter",
            "tag": "not performed by integration adapter",
            "release_write": "not performed by integration adapter",
            "coderabbit_authorized_release": False,
            "codex_security_authorized_release": False,
            "secrets_printed": False,
        },
        "limitations": [],
    }
    if not payload["github"].get("release_found"):
        payload["limitations"].append("github_release_not_observed")
    if not payload["registries"]["pypi"]["published"]:
        payload["limitations"].append("pypi_version_not_observed")
    if not payload["registries"]["npm"]["published"]:
        payload["limitations"].append("npm_version_not_observed")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def markdown_report(payload: dict[str, Any]) -> str:
    release = payload["release"]
    registries = payload["registries"]
    stages = payload["state"].get("stages", {})
    lines = [
        f"# Alpha Integration Status: {release}",
        "",
        f"- Generated: `{payload['generated_at']}`",
        "- Authority: advisory-only / non-authoritative",
        "- Permission granted by integrations: `false`",
        "",
        "## GitHub",
        "",
        f"- Release observed: `{payload['github'].get('release_found')}`",
        f"- Remote main converged: `{payload['git'].get('main_converged')}`",
        f"- Remote tag observed: `{payload['git'].get('tag_exists')}`",
        "",
        "## Registries",
        "",
        f"- PyPI `{registries['pypi']['version']}` published: `{registries['pypi']['published']}`",
        f"- npm `{registries['npm']['version']}` published: `{registries['npm']['published']}`",
        f"- npm `latest` points to version: `{registries['npm']['latest_points_to_version']}`",
        f"- npm `alpha` points to version: `{registries['npm']['alpha_points_to_version']}`",
        "",
        "## Release Stages",
        "",
    ]
    if stages:
        for stage, value in stages.items():
            lines.append(f"- `{stage}`: `{value.get('status')}`")
    else:
        lines.append("- No SQLite stage rows observed.")
    lines.extend(
        [
            "",
            "## Workflow Surfaces",
            "",
            f"- Linear available: `{payload['linear'].get('available')}`",
            f"- Linear configured: `{payload['linear'].get('configured')}`",
            f"- Linear workspace observed: `{payload['linear'].get('workspace_observed')}`",
            f"- Linear viewer observed: `{payload['linear'].get('viewer_observed')}`",
            f"- Sentry available: `{payload['sentry'].get('available')}`",
            f"- Sentry configured: `{payload['sentry'].get('configured')}`",
            f"- Sentry organization observed: `{payload['sentry'].get('organization_observed')}`",
            f"- Sentry unresolved issues observed: `{payload['sentry'].get('unresolved_issue_count')}`",
            "",
            "## Advisory Surfaces",
            "",
            f"- CodeRabbit available: `{payload['coderabbit'].get('available')}`",
            f"- CodeRabbit advisory-only: `{payload['coderabbit'].get('advisory_only')}`",
            f"- Codex Security advisory-only: `{payload['codex_security'].get('advisory_only')}`",
            "",
            "## Explicit Non-Actions",
            "",
        ]
    )
    for key, value in payload["explicit_non_actions"].items():
        lines.append(f"- `{key}`: `{value}`")
    if payload["limitations"]:
        lines.extend(["", "## Limitations", ""])
        for limitation in payload["limitations"]:
            lines.append(f"- `{limitation}`")
    lines.append("")
    return "\n".join(lines)


def write_alpha_integration_reports(
    release: str, *, reports_dir: Path, state_path: Path
) -> tuple[Path, Path]:
    payload = build_status_payload(release, state_path=state_path)
    safe_release = release.replace("/", "_")
    json_path = reports_dir / f"integration-status-{safe_release}.json"
    md_path = reports_dir / f"integration-status-{safe_release}.md"
    write_json(json_path, payload)
    md_path.write_text(markdown_report(payload), encoding="utf-8")
    return json_path, md_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--release", required=True, help="Alpha release tag, e.g. v0.1.5-alpha."
    )
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument(
        "--json", action="store_true", help="Print the JSON payload to stdout."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    json_path, md_path = write_alpha_integration_reports(
        args.release,
        reports_dir=args.reports_dir,
        state_path=args.state_file,
    )
    if args.json:
        print(json_path.read_text(encoding="utf-8"), end="")
    else:
        print(f"alpha integration status written: {json_path}")
        print(f"alpha integration evidence written: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
