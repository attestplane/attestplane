from __future__ import annotations

import json
import importlib.util
import sqlite3
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "release" / "alpha_train_integrations.py"

spec = importlib.util.spec_from_file_location("alpha_train_integrations", MODULE_PATH)
assert spec is not None
alpha_train_integrations = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["alpha_train_integrations"] = alpha_train_integrations
spec.loader.exec_module(alpha_train_integrations)


def test_integration_payload_is_non_authoritative(monkeypatch, tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    db_path = tmp_path / "state.sqlite"
    with sqlite3.connect(db_path) as db:
        db.execute(
            "CREATE TABLE release_state (release TEXT PRIMARY KEY, python_version TEXT, npm_version TEXT, status TEXT NOT NULL, updated_at_epoch INTEGER NOT NULL)"
        )
        db.execute(
            "CREATE TABLE release_stages (release TEXT NOT NULL, stage TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL, updated_at_epoch INTEGER NOT NULL, PRIMARY KEY (release, stage))"
        )
        db.execute(
            "INSERT INTO release_state VALUES ('v0.1.5-alpha', '0.1.5a0', '0.1.5-alpha', 'released', 1)"
        )
        db.execute(
            "INSERT INTO release_stages VALUES ('v0.1.5-alpha', 'registry_verified', 'done', '{}', 1)"
        )

    def fake_run(argv: list[str], *, timeout: int = 20) -> tuple[bool, str]:
        if argv[:3] == ["git", "rev-parse", "HEAD"]:
            return True, "abc123"
        if argv[:3] == ["git", "ls-remote", "origin"] and argv[-1] == "refs/heads/main":
            return True, "abc123\trefs/heads/main"
        if (
            argv[:3] == ["git", "ls-remote", "origin"]
            and argv[-1] == "refs/tags/v0.1.5-alpha"
        ):
            return True, "tag123\trefs/tags/v0.1.5-alpha"
        if argv[:3] == ["git", "status", "--short"]:
            return True, ""
        if argv[:3] == ["gh", "release", "view"]:
            return True, json.dumps(
                {"tagName": "v0.1.5-alpha", "isPrerelease": True, "assets": []}
            )
        if argv[:3] == ["gh", "run", "list"]:
            return True, "[]"
        if argv[:2] == ["npm", "view"] and "@0.1.5-alpha" in argv[2]:
            return True, json.dumps("0.1.5-alpha")
        if argv[:3] == ["npm", "view", "@attestplane/attestplane"]:
            return True, json.dumps({"latest": "0.1.5-alpha", "alpha": "0.1.5-alpha"})
        if argv[:2] == ["coderabbit", "--version"]:
            return True, "coderabbit 1.0.0"
        if argv[:3] == ["coderabbit", "auth", "status"]:
            return True, "authenticated"
        raise AssertionError(argv)

    monkeypatch.setattr(
        alpha_train_integrations.shutil, "which", lambda name: f"/bin/{name}"
    )
    monkeypatch.setattr(alpha_train_integrations, "run_capture", fake_run)
    monkeypatch.setattr(
        alpha_train_integrations, "pypi_version_exists", lambda version: True
    )

    class FakeResponse:
        def __init__(self, body: dict[str, object] | list[object]) -> None:
            self._body = json.dumps(body).encode("utf-8")

        def read(self) -> bytes:
            return self._body

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

    def fake_urlopen(request: object, timeout: int = 20) -> FakeResponse:
        url = getattr(request, "full_url", "")
        if "api.linear.app/graphql" in url:
            return FakeResponse(
                {
                    "data": {
                        "viewer": {"id": "viewer-1", "name": "Attestplane"},
                        "organization": {"id": "org-1", "name": "Attestplane"},
                    }
                }
            )
        if "sentry.io/api/0/organizations/" in url:
            return FakeResponse([{"id": "issue-1"}, {"id": "issue-2"}])
        raise AssertionError(url)

    monkeypatch.setenv("LINEAR_API_KEY", "linear-token")
    monkeypatch.setenv("SENTRY_AUTH_TOKEN", "sentry-token")
    monkeypatch.setenv("SENTRY_ORG", "attestplane")
    monkeypatch.setattr(
        alpha_train_integrations.urllib.request, "urlopen", fake_urlopen
    )

    payload = alpha_train_integrations.build_status_payload(
        "v0.1.5-alpha", state_path=state_file
    )

    assert payload["authority"]["authoritative"] is False
    assert payload["authority"]["permission_granted"] is False
    assert payload["github"]["release_found"] is True
    assert payload["registries"]["pypi"]["published"] is True
    assert payload["registries"]["npm"]["latest_points_to_version"] is True
    assert payload["linear"]["available"] is True
    assert payload["linear"]["workspace_observed"] is True
    assert payload["sentry"]["available"] is True
    assert payload["sentry"]["unresolved_issue_count"] == 2
    assert payload["coderabbit"]["advisory_only"] is True
    assert payload["codex_security"]["permission_granted"] is False
    assert payload["state"]["stages"]["registry_verified"]["status"] == "done"


def test_integration_reports_write_json_and_markdown(
    monkeypatch, tmp_path: Path
) -> None:
    state_file = tmp_path / "state.json"
    payload: dict[str, Any] = {
        "schema": "attestplane_alpha_integration_status.v1",
        "generated_at": "2026-05-19T00:00:00Z",
        "release": "v0.1.5-alpha",
        "authority": {"authoritative": False, "permission_granted": False},
        "github": {"release_found": True},
        "git": {"main_converged": True, "tag_exists": True},
        "registries": {
            "pypi": {"version": "0.1.5a0", "published": True},
            "npm": {
                "version": "0.1.5-alpha",
                "published": True,
                "latest_points_to_version": True,
                "alpha_points_to_version": True,
            },
        },
        "linear": {
            "available": True,
            "configured": True,
            "workspace_observed": True,
            "viewer_observed": True,
        },
        "sentry": {
            "available": True,
            "configured": True,
            "organization_observed": True,
            "unresolved_issue_count": 2,
        },
        "state": {"stages": {"registry_verified": {"status": "done"}}},
        "coderabbit": {"available": False, "advisory_only": True},
        "codex_security": {"advisory_only": True},
        "explicit_non_actions": {"publish": "not performed by integration adapter"},
        "limitations": [],
    }
    monkeypatch.setattr(
        alpha_train_integrations,
        "build_status_payload",
        lambda release, state_path: payload,
    )

    json_path, md_path = alpha_train_integrations.write_alpha_integration_reports(
        "v0.1.5-alpha",
        reports_dir=tmp_path,
        state_path=state_file,
    )

    assert (
        json.loads(json_path.read_text(encoding="utf-8"))["schema"]
        == "attestplane_alpha_integration_status.v1"
    )
    text = md_path.read_text(encoding="utf-8")
    assert "Alpha Integration Status: v0.1.5-alpha" in text
    assert "Permission granted by integrations: `false`" in text
    assert "Linear available" in text
    assert "Sentry available" in text


def test_integration_payload_marks_missing_optional_workflow_surfaces(
    monkeypatch, tmp_path: Path
) -> None:
    state_file = tmp_path / "state.json"
    db_path = tmp_path / "state.sqlite"
    with sqlite3.connect(db_path) as db:
        db.execute(
            "CREATE TABLE release_state (release TEXT PRIMARY KEY, python_version TEXT, npm_version TEXT, status TEXT NOT NULL, updated_at_epoch INTEGER NOT NULL)"
        )
    monkeypatch.setattr(
        alpha_train_integrations.shutil, "which", lambda name: f"/bin/{name}"
    )
    monkeypatch.setattr(
        alpha_train_integrations,
        "run_capture",
        lambda argv, timeout=20: (False, "missing"),
    )
    monkeypatch.setattr(
        alpha_train_integrations, "pypi_version_exists", lambda version: False
    )
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)
    monkeypatch.delenv("LINEAR_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("SENTRY_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("SENTRY_ORG", raising=False)

    payload = alpha_train_integrations.build_status_payload(
        "v0.1.5-alpha", state_path=state_file
    )

    assert payload["linear"]["available"] is False
    assert payload["linear"]["limitations"] == ["linear_api_token_missing"]
    assert payload["sentry"]["available"] is False
    assert payload["sentry"]["limitations"] == ["sentry_api_credentials_missing"]
