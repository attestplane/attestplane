from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_release_cd_delegates_real_pypi_publish_to_direct_workflow() -> None:
    release_cd = (REPO_ROOT / ".github/workflows/release-cd.yml").read_text(encoding="utf-8")
    publish_python = (REPO_ROOT / ".github/workflows/publish-python.yml").read_text(
        encoding="utf-8",
    )

    assert "gh workflow run publish-python.yml" in release_cd
    assert "-f caller_run_id=\"${CALLER_RUN_ID}\"" in release_cd
    assert "gh run watch \"$run_id\" --exit-status" in release_cd
    assert "caller_run_id:" in publish_python
    assert "run-name: publish-python" in publish_python


def test_release_cd_records_release_gate_decision_without_blocking_fast_track() -> None:
    release_cd = (REPO_ROOT / ".github/workflows/release-cd.yml").read_text(encoding="utf-8")

    assert "id: release_gate" in release_cd
    assert "python scripts/release/release_gate.py" in release_cd
    assert "ATTESTPLANE_RELEASE_AUDIT: ${{ vars.ATTESTPLANE_RELEASE_AUDIT }}" in release_cd
    assert "release_track: ${{ steps.release_gate.outputs.track }}" in release_cd


def test_release_cd_enforces_verified_audit_for_audit_track() -> None:
    release_cd = (REPO_ROOT / ".github/workflows/release-cd.yml").read_text(encoding="utf-8")

    assert "audit_verified:" in release_cd
    assert "audit_plan_url:" in release_cd
    assert "--enforce" in release_cd
    assert "--audit-verified" in release_cd
    assert "--audit-plan-url" in release_cd
