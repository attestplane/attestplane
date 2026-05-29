# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from attestplane import AttestSubstrate, EventDraft
from attestplane.cli.main import main as cli_main
from attestplane.proof_bundle import ProofBundleBuilder
from attestplane.retention import build_deletion_proof
from attestplane.verifier import verify_proof_bundle
from tests.cli.verify_json_contract_v1 import (
    UNKNOWN_REQUIRED_FIXTURE,
    VERIFY_JSON_CONTRACT_V1,
    render_verify_json_payload,
)

ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = ROOT.parents[1]
VECTORS = ROOT / "tests" / "conformance" / "verifier_conformance_vectors.json"
MINIMUM_SCHEMA_NEGATIVE_VECTORS = ROOT / "tests" / "conformance" / "proof_bundle_minimum_schema_negative_vectors.json"


def _base_bundle() -> dict:
    sub = AttestSubstrate()
    base = datetime(2026, 5, 19, tzinfo=UTC)
    chain = [
        sub.append(EventDraft(event_type="eval_event", actor="agent", payload={"i": 0}), now=base),
        sub.append(
            EventDraft(event_type="redaction_event", actor="agent", payload={"i": 1}),
            now=base + timedelta(microseconds=1),
        ),
    ]
    builder = ProofBundleBuilder(chain_id="conf", producer_runtime="test")
    builder.extend(chain)
    return builder.build(now=base)


def _case_bundle(case_id: str) -> dict:
    bundle = _base_bundle()
    if case_id == "valid_minimal":
        return bundle
    if case_id == "tampered_event_hash":
        bundle["events"][0]["event"]["payload"] = {"i": 999}
        return bundle
    if case_id == "dangling_policy_trace_ref":
        bundle["policy_trace_refs"] = ["f" * 64]
        return bundle
    if case_id == "forged_deletion_proof":
        bundle["retention_proofs"] = [
            build_deletion_proof(
                proof_id="forged",
                target_event_hash_hex=bundle["events"][0]["event_hash_hex"],
                commit_event_hash_hex=bundle["events"][1]["event_hash_hex"],
                redacted_event_hash_hex="f" * 64,
                reason="forged",
            )
        ]
        return bundle
    if case_id == "tampered_verification_report":
        bundle["verification_report"]["ok"] = False
        bundle["verification_report"]["first_bad_index"] = 0
        bundle["verification_report"]["reason"] = "tampered report"
        return bundle
    if case_id == "version_skew_chain_schema":
        bundle["chain_metadata"]["schema_version"] = 999
        return bundle
    if case_id == "malformed_policy_trace_refs_empty":
        bundle["policy_trace_refs"] = []
        return bundle
    if case_id == "empty_bundle_require_non_empty":
        return ProofBundleBuilder(chain_id="empty-conf", producer_runtime="test").build(
            now=datetime(2026, 5, 19, tzinfo=UTC)
        )
    raise AssertionError(f"unknown case_id={case_id}")


@pytest.mark.parametrize("case", json.loads(VECTORS.read_text(encoding="utf-8"))["cases"])
def test_verifier_conformance_vectors(case: dict) -> None:
    result = verify_proof_bundle(_case_bundle(case["case_id"]), **case.get("verify_options", {}))
    assert result.ok is case["expected_ok"]
    assert result.error_code == case["expected_error_code"]


@pytest.mark.parametrize(
    "case",
    json.loads(MINIMUM_SCHEMA_NEGATIVE_VECTORS.read_text(encoding="utf-8"))["cases"],
)
def test_minimum_schema_negative_conformance_vectors(case: dict) -> None:
    vector = json.loads((REPO_ROOT / case["path"]).read_text(encoding="utf-8"))
    assert vector["case_id"] == case["case_id"]
    assert vector["expected_ok"] is case["expected_ok"]
    assert vector["expected_error_code"] == case["expected_error_code"]
    assert vector["expected_primary_reason"] == case["expected_primary_reason"]
    assert vector["expected_secondary_reasons"] == case["expected_secondary_reasons"]
    assert vector["verify_options"] == case["verify_options"]

    result = verify_proof_bundle(vector["bundle"], **case["verify_options"])

    assert result.ok is case["expected_ok"]
    assert result.error_code == case["expected_error_code"]
    assert result.primary_reason == case["expected_primary_reason"]
    assert list(result.secondary_reasons) == case["expected_secondary_reasons"]


def test_verify_json_exit_code_table_is_pinned() -> None:
    assert VERIFY_JSON_CONTRACT_V1["exit_codes"] == {
        "success": 0,
        "verification_failure": 1,
        "quarantined": 3,
        "usage_error": 2,
    }


def test_unknown_required_field_exit_code_is_pinned(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = cli_main(["verify", "--json", str(UNKNOWN_REQUIRED_FIXTURE)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    expected = VERIFY_JSON_CONTRACT_V1["cases"]["unknown_required_field"]["payload"]

    assert rc == VERIFY_JSON_CONTRACT_V1["exit_codes"]["verification_failure"]
    assert captured.err == ""
    assert captured.out == render_verify_json_payload(expected)
    assert payload == expected
