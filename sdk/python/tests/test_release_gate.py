from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts/release/release_gate.py"

spec = importlib.util.spec_from_file_location("release_gate", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
release_gate = importlib.util.module_from_spec(spec)
sys.modules["release_gate"] = release_gate
spec.loader.exec_module(release_gate)


def test_stable_patch_release_defaults_to_fast_track() -> None:
    decision = release_gate.decide_release_gate(
        release_tag="v0.8.10",
        channel="latest",
        labels=[],
        release_audit=False,
        milestone=None,
        dependency_major_bump=False,
        env={},
    )

    assert decision.track == "fast"
    assert decision.audit_required is False
    assert decision.reasons == ["default_fast_track"]


def test_major_boundary_uses_audit_track() -> None:
    decision = release_gate.decide_release_gate(
        release_tag="v1.0.0",
        channel="latest",
        labels=[],
        release_audit=False,
        milestone=None,
        dependency_major_bump=False,
        env={},
    )

    assert decision.track == "audit"
    assert decision.audit_required is True
    assert decision.reasons == ["major_boundary"]


def test_minor_zero_release_after_major_defaults_to_fast_track() -> None:
    decision = release_gate.decide_release_gate(
        release_tag="v1.1.0",
        channel="latest",
        labels=[],
        release_audit=False,
        milestone=None,
        dependency_major_bump=False,
        env={},
    )

    assert decision.track == "fast"
    assert decision.audit_required is False
    assert decision.reasons == ["default_fast_track"]


def test_next_major_zero_zero_release_uses_audit_track() -> None:
    decision = release_gate.decide_release_gate(
        release_tag="v2.0.0",
        channel="latest",
        labels=[],
        release_audit=False,
        milestone=None,
        dependency_major_bump=False,
        env={},
    )

    assert decision.track == "audit"
    assert decision.audit_required is True
    assert decision.reasons == ["major_boundary"]


def test_kill_switch_forces_fast_track_even_at_major_boundary() -> None:
    decision = release_gate.decide_release_gate(
        release_tag="v1.0.0",
        channel="latest",
        labels=[],
        release_audit=False,
        milestone=None,
        dependency_major_bump=False,
        env={"ATTESTPLANE_RELEASE_AUDIT": "off"},
    )

    assert decision.track == "fast"
    assert decision.audit_required is False
    assert decision.reasons == ["audit_disabled"]


def test_security_and_compat_labels_use_audit_track() -> None:
    decision = release_gate.decide_release_gate(
        release_tag="v0.8.10",
        channel="latest",
        labels=["security", "compat-break"],
        release_audit=False,
        milestone=None,
        dependency_major_bump=False,
        env={},
    )

    assert decision.track == "audit"
    assert decision.audit_required is True
    assert decision.reasons == ["label:compat-break", "label:security"]


def test_manual_release_audit_and_ga_ca_milestones_use_audit_track() -> None:
    ga = release_gate.decide_release_gate(
        release_tag="v0.8.10",
        channel="latest",
        labels=[],
        release_audit=False,
        milestone="GA",
        dependency_major_bump=False,
        env={},
    )
    manual_ca = release_gate.decide_release_gate(
        release_tag="v0.8.10",
        channel="latest",
        labels=[],
        release_audit=True,
        milestone="ca",
        dependency_major_bump=False,
        env={},
    )

    assert ga.track == "audit"
    assert ga.reasons == ["milestone:ga"]
    assert manual_ca.track == "audit"
    assert manual_ca.reasons == ["manual_release_audit", "milestone:ca"]


def test_dependency_major_bump_uses_audit_track() -> None:
    decision = release_gate.decide_release_gate(
        release_tag="v0.8.10",
        channel="latest",
        labels=[],
        release_audit=False,
        milestone=None,
        dependency_major_bump=True,
        env={},
    )

    assert decision.track == "audit"
    assert decision.reasons == ["dependency_major_bump"]


def test_audit_gate_blocks_without_verified_plan() -> None:
    decision = release_gate.decide_release_gate(
        release_tag="v1.0.0",
        channel="latest",
        labels=[],
        release_audit=False,
        milestone=None,
        dependency_major_bump=False,
        env={},
    )

    result = release_gate.validate_audit_verification(
        decision,
        audit_verified=False,
        audit_plan_url="",
    )

    assert result.allowed is False
    assert result.reason == "audit_required_without_verified_plan"


def test_audit_gate_allows_verified_plan() -> None:
    decision = release_gate.decide_release_gate(
        release_tag="v1.0.0",
        channel="latest",
        labels=[],
        release_audit=False,
        milestone=None,
        dependency_major_bump=False,
        env={},
    )

    result = release_gate.validate_audit_verification(
        decision,
        audit_verified=True,
        audit_plan_url="https://github.com/attestplane/attestplane/issues/1",
    )

    assert result.allowed is True
    assert result.reason == "audit_verified"
