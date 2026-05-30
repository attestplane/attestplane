# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Cross-surface parity test for ``taxonomy_version``.

Verifies that ``taxonomy_version`` is surfaced consistently across three
surfaces for the same input bundle:

1. ``verify --json`` structured output (``payload["taxonomy_version"]``)
2. ``verify --explain`` human-readable summary (``taxonomy_version=...`` line)
3. SDK ``BundleVerificationResult.taxonomy_version`` attribute

All three MUST produce the same value (or all three ``None`` for legacy
bundles). A parity vector here fails if any surface drifts relative to
the others, providing a single gate that covers the consolidated field
per issue #291.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.event_types import EVIDENCE_TAXONOMY_VERSION
from attestplane.proof_bundle import ProofBundleBuilder
from attestplane.verifier import verify_proof_bundle

ROOT = Path(__file__).resolve().parents[2]
PASS_FIXTURE = ROOT / "fixtures" / "positive" / "minimal.json"
V1_SIGNED_FIXTURE = ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"
SIGNED_FIXTURE = ROOT / "tests" / "fixtures" / "v1.7.0_signed.json"
QUARANTINE_FIXTURE = ROOT / "fixtures" / "anchoring" / "quarantine_timeout.att"


def _resolve_taxonomy_from_json(stdout: str) -> int | None:
    """Extract ``taxonomy_version`` from ``verify --json`` output."""
    payload = json.loads(stdout)
    return payload.get("taxonomy_version")


def _resolve_taxonomy_from_explain(stdout: str) -> int | None:
    """Extract ``taxonomy_version`` from ``verify --explain`` output summary.

    The summary line looks like::

        OK signer_subject=... schema_version=1 taxonomy_version=1 anchor=absent

    or::

        FAIL signer_subject=... schema_version=1 taxonomy_version=1 anchor=...
    """
    summary = stdout.strip()
    for token in summary.split():
        if token.startswith("taxonomy_version="):
            raw = token.split("=", 1)[1]
            if raw == "unknown":
                return None
            return int(raw)
    return None


def _run_verify(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def _make_legacy_bundle_path(tmp_path: Path) -> Path:
    """Build and write a bundle without ``evidence_taxonomy_version``."""
    bundle = ProofBundleBuilder(chain_id="legacy-test", producer_runtime="test").build()
    chain_metadata = bundle.get("chain_metadata")
    if isinstance(chain_metadata, dict):
        chain_metadata.pop("evidence_taxonomy_version", None)
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Parity vectors
# ---------------------------------------------------------------------------


def test_taxonomy_version_parity_pass_bundle(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """SDK result, --json, and --explain all report taxonomy_version for a pass bundle."""
    bundle = json.loads(PASS_FIXTURE.read_text(encoding="utf-8"))

    # SDK surface
    sdk_result = verify_proof_bundle(bundle)
    sdk_value = sdk_result.taxonomy_version
    assert sdk_value == EVIDENCE_TAXONOMY_VERSION, (
        f"SDK result taxonomy_version={sdk_value!r}, expected {EVIDENCE_TAXONOMY_VERSION}"
    )

    # CLI --json surface
    rc_json, stdout_json, _ = _run_verify(
        ["verify", "--json", str(PASS_FIXTURE)], capsys
    )
    assert rc_json == 0
    json_value = _resolve_taxonomy_from_json(stdout_json)
    assert json_value == sdk_value, (
        f"--json taxonomy_version={json_value!r} != SDK result {sdk_value!r}"
    )

    # CLI --explain surface
    rc_explain, stdout_explain, _ = _run_verify(
        ["verify", "--explain", str(PASS_FIXTURE)], capsys
    )
    assert rc_explain == 0
    explain_value = _resolve_taxonomy_from_explain(stdout_explain)
    assert explain_value == sdk_value, (
        f"--explain taxonomy_version={explain_value!r} != SDK result {sdk_value!r}"
    )


def test_taxonomy_version_parity_signed_bundle(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Parity holds for a signed pass bundle."""
    bundle = json.loads(V1_SIGNED_FIXTURE.read_text(encoding="utf-8"))

    sdk_result = verify_proof_bundle(bundle, require_signed_attestation=True)
    sdk_value = sdk_result.taxonomy_version
    assert sdk_value == EVIDENCE_TAXONOMY_VERSION

    rc_json, stdout_json, _ = _run_verify(
        ["verify", "--json", "--strict-schema", str(V1_SIGNED_FIXTURE)], capsys
    )
    assert rc_json == 0
    assert _resolve_taxonomy_from_json(stdout_json) == sdk_value


def test_taxonomy_version_parity_legacy_bundle(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """All three surfaces report None/null for legacy bundles without the field."""
    legacy_path = _make_legacy_bundle_path(tmp_path)
    bundle = json.loads(legacy_path.read_text(encoding="utf-8"))

    # SDK surface
    sdk_result = verify_proof_bundle(bundle)
    assert sdk_result.taxonomy_version is None, "SDK result must be None for legacy bundle"

    # CLI --json surface
    rc_json, stdout_json, _ = _run_verify(
        ["verify", "--json", str(legacy_path)], capsys
    )
    assert _resolve_taxonomy_from_json(stdout_json) is None, (
        "legacy bundle must surface null taxonomy_version in --json output"
    )

    # CLI --explain surface
    rc_explain, stdout_explain, _ = _run_verify(
        ["verify", "--explain", str(legacy_path)], capsys
    )
    explain_value = _resolve_taxonomy_from_explain(stdout_explain)
    assert explain_value is None, (
        f"legacy bundle must surface null taxonomy_version in --explain, got {explain_value}"
    )


def test_taxonomy_version_parity_fail_bundle(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Parity holds even for a fail/quarantine bundle with resolvable taxonomy_version."""
    bundle_json = json.loads(QUARANTINE_FIXTURE.read_text(encoding="utf-8"))

    sdk_result = verify_proof_bundle(bundle_json)
    sdk_value = sdk_result.taxonomy_version
    assert sdk_value == EVIDENCE_TAXONOMY_VERSION

    # CLI --json surface
    rc_json, stdout_json, _ = _run_verify(
        ["verify", "--json", str(QUARANTINE_FIXTURE)], capsys
    )
    assert rc_json == 2  # quarantine
    assert _resolve_taxonomy_from_json(stdout_json) == sdk_value

    # CLI --explain surface (the summary includes taxonomy_version)
    rc_explain, stdout_explain, _ = _run_verify(
        ["verify", "--explain", str(QUARANTINE_FIXTURE)], capsys
    )
    assert rc_explain == 2
    assert _resolve_taxonomy_from_explain(stdout_explain) == sdk_value
