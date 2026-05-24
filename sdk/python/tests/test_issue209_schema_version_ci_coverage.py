# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Issue #209 schema-version verifier coverage for the sdk-python CI gate."""

from __future__ import annotations

import copy
import io
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from attestplane import AttestSubstrate, EventDraft
from attestplane.cli.main import main as cli_main
from attestplane.proof_bundle import ProofBundleBuilder
from attestplane.verifier import (
    BundleSchemaError,
    classify_bundle_schema_error,
    main as verifier_main,
    verify_proof_bundle,
    verify_proof_bundle_file,
)
from attestplane.verify_errors import (
    VERIFY_BUNDLE_SCHEMA_INCOMPLETE,
    VERIFY_OK,
    VERIFY_SCHEMA_ERROR,
)
from attestplane.verify_reason_codes import (
    ALL_VERIFY_REASON_CODES_V1,
    VERIFY_REASON_CANONICAL_MISMATCH,
    VERIFY_REASON_REQUIRED_FIELD_MISSING,
    VERIFY_REASON_SCHEMA_INVALID,
    VERIFY_REASON_SCHEMA_UNKNOWN,
    VERIFY_REASON_SCHEMA_VERSION_MISSING,
    VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
    VERIFY_REASON_SIGNATURE_INVALID,
    VERIFY_REASON_SIGNATURE_MISSING,
    is_known_verify_reason_code,
    verify_reason_code_matches_format,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "bundles"
SCHEMA_VERSION_DIR = REPO_ROOT / "tests" / "conformance" / "schema_version"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _schema_case(name: str) -> dict:
    return json.loads((SCHEMA_VERSION_DIR / name / "bundle.json").read_text(encoding="utf-8"))


def _unsigned_bundle() -> dict:
    substrate = AttestSubstrate()
    event = substrate.append(
        EventDraft(event_type="eval_event", actor="agent", payload={"ok": True}),
        now=datetime(2026, 5, 22, tzinfo=UTC),
    )
    builder = ProofBundleBuilder(chain_id="issue-209", producer_runtime="test")
    builder.extend([event])
    return builder.build(now=datetime(2026, 5, 22, tzinfo=UTC))


def _signed_bundle() -> dict:
    bundle = _unsigned_bundle()
    bundle["signatures"] = [
        {
            "key_id": "b" * 32,
            "public_key_der_b64": "AQ==",
            "signature_hex": "a" * 128,
            "signature_mode": "per_event",
            "signature_schema_version": 1,
            "signed_at": "2026-05-22T00:00:00+00:00",
            "signed_event_hash_hex": bundle["events"][0]["event_hash_hex"],
            "signed_payload_b64": "AQ==",
            "signed_seq": 0,
            "signing_cert_chain_b64": [],
        }
    ]
    return bundle


def test_schema_version_conformance_vectors_are_covered_by_sdk_gate() -> None:
    expectations = {
        "additive_minor_ok": (True, None, ()),
        "additive_with_unknown_field_ok": (True, None, ()),
        "missing": (False, VERIFY_REASON_SCHEMA_VERSION_MISSING, ()),
        "unknown_major": (False, VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED, ()),
    }

    for case, (ok, primary, secondary) in expectations.items():
        result = verify_proof_bundle(_schema_case(case), require_signed_attestation=True)
        assert result.ok is ok
        assert result.primary_reason == primary
        assert result.secondary_reasons == secondary


def test_unknown_schema_major_keeps_canonical_mismatch_primary() -> None:
    bundle = _schema_case("unknown_major")
    bundle["events"][0]["event_hash_hex"] = "f" * 64

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is False
    assert result.primary_reason == VERIFY_REASON_CANONICAL_MISMATCH
    assert VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED in result.secondary_reasons


def test_verify_reason_code_taxonomy_and_format_helpers() -> None:
    for code in ALL_VERIFY_REASON_CODES_V1:
        assert is_known_verify_reason_code(code)
        assert verify_reason_code_matches_format(code)

    assert not is_known_verify_reason_code("att.verify.future_reason")
    assert not verify_reason_code_matches_format("bad-code")


def test_signed_attestation_schema_reason_mapping() -> None:
    missing = verify_proof_bundle(_unsigned_bundle(), require_signed_attestation=True)
    assert missing.error_code == VERIFY_BUNDLE_SCHEMA_INCOMPLETE
    assert missing.primary_reason == VERIFY_REASON_SIGNATURE_MISSING

    malformed = _signed_bundle()
    malformed["signatures"][0]["signature_hex"] = "not-hex"
    result = verify_proof_bundle(malformed, require_signed_attestation=True)
    assert result.error_code == VERIFY_BUNDLE_SCHEMA_INCOMPLETE
    assert result.primary_reason == VERIFY_REASON_SIGNATURE_INVALID

    incomplete = _signed_bundle()
    del incomplete["signatures"][0]["signature_hex"]
    result = verify_proof_bundle(incomplete, require_signed_attestation=True)
    assert result.primary_reason == VERIFY_REASON_REQUIRED_FIELD_MISSING


@pytest.mark.parametrize(
    ("mutator", "expected"),
    [
        (lambda bundle: bundle.pop("bundle_version"), VERIFY_REASON_REQUIRED_FIELD_MISSING),
        (lambda bundle: bundle.__setitem__("bundle_version", 2), VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED),
        (lambda bundle: bundle.__setitem__("proof_type", "future-critical"), VERIFY_REASON_SCHEMA_UNKNOWN),
        (lambda bundle: bundle.__setitem__("critical_future_field", True), VERIFY_REASON_SCHEMA_UNKNOWN),
        (lambda bundle: bundle.__setitem__("chain_metadata", []), VERIFY_REASON_SCHEMA_INVALID),
        (lambda bundle: bundle.__setitem__("events", {}), VERIFY_REASON_SCHEMA_INVALID),
        (lambda bundle: bundle.__setitem__("verification_report", []), VERIFY_REASON_SCHEMA_INVALID),
        (
            lambda bundle: bundle["verification_report"].__setitem__("verification_method", "future-method"),
            VERIFY_REASON_SCHEMA_UNKNOWN,
        ),
        (lambda bundle: bundle.__setitem__("forbidden_fields", ["secret"]), VERIFY_REASON_SCHEMA_INVALID),
        (lambda bundle: bundle.__setitem__("framework_mappings", {}), VERIFY_REASON_SCHEMA_INVALID),
        (lambda bundle: bundle.__setitem__("policy_trace_refs", {}), VERIFY_REASON_SCHEMA_INVALID),
        (lambda bundle: bundle.__setitem__("retention_proofs", {}), VERIFY_REASON_SCHEMA_INVALID),
    ],
)
def test_bundle_schema_errors_map_to_public_reason_codes(mutator, expected: str) -> None:
    bundle = _signed_bundle()
    mutator(bundle)

    with pytest.raises(BundleSchemaError) as exc_info:
        verify_proof_bundle(bundle, require_signed_attestation=True)

    assert classify_bundle_schema_error(exc_info.value) == expected


def test_metadata_schema_version_shape_failures_are_reported_as_reasons() -> None:
    missing = _signed_bundle()
    del missing["chain_metadata"]["schema_version"]
    assert verify_proof_bundle(missing, require_signed_attestation=True).primary_reason == (
        VERIFY_REASON_SCHEMA_VERSION_MISSING
    )

    invalid = _signed_bundle()
    invalid["chain_metadata"]["schema_version"] = "1"
    assert verify_proof_bundle(invalid, require_signed_attestation=True).primary_reason == (
        VERIFY_REASON_SCHEMA_INVALID
    )


def test_metadata_and_report_closure_failure_branches() -> None:
    bundle = _signed_bundle()
    bundle["chain_metadata"]["genesis_hash_hex"] = "f" * 64
    assert verify_proof_bundle(bundle, require_signed_attestation=True).metadata_reason == (
        "chain_metadata.genesis_hash_hex does not match substrate genesis hash"
    )

    bundle = _signed_bundle()
    bundle["chain_metadata"]["evidence_taxonomy_version"] = 2
    assert verify_proof_bundle(bundle, require_signed_attestation=True).metadata_reason == (
        "chain_metadata.evidence_taxonomy_version must be 1 when present"
    )

    bundle = _signed_bundle()
    bundle["verification_report"]["reason"] = "unexpected"
    assert verify_proof_bundle(bundle, require_signed_attestation=True).metadata_reason == (
        "verification_report.reason disagrees with recomputed chain result"
    )


def test_policy_trace_ref_failure_branches() -> None:
    bundle = _signed_bundle()
    bundle["policy_trace_refs"] = []
    assert verify_proof_bundle(bundle, require_signed_attestation=True).policy_trace_refs_reason == (
        "policy_trace_refs must be absent, not empty, when no policy_check_event exists"
    )

    bundle = _signed_bundle()
    bundle["policy_trace_refs"] = ["bad"]
    assert verify_proof_bundle(bundle, require_signed_attestation=True).policy_trace_refs_reason == (
        "policy_trace_refs present but bundle contains no policy_check_event"
    )


def test_additive_unknown_fields_surface_reserved_cli_explain_reason(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = _fixture("valid_signed_attestation.json")
    bundle["future_bundle_field"] = {"preserved": True}
    bundle["chain_metadata"]["future_metadata_field"] = "kept"
    bundle["verification_report"]["future_report_field"] = "ignored"
    bundle["framework_mappings"] = [{"obligation_id": "o", "future_mapping_field": "kept"}]
    bundle["signatures"][0]["future_signature_field"] = "kept"
    path = tmp_path / "additive.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    rc = cli_main(["verify", "--json", "--explain", str(path)])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["reasons"][0]["code"] == VERIFY_REASON_SCHEMA_UNKNOWN
    detail = payload["reasons"][0]["detail"]
    assert "bundle.future_bundle_field" in detail
    assert "chain_metadata.future_metadata_field" in detail
    assert "framework_mappings[0].future_mapping_field" in detail
    assert "signatures[0].future_signature_field" in detail


def test_cli_schema_errors_return_structured_verify_reason(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "unsupported.json"
    bundle = _signed_bundle()
    bundle["bundle_version"] = 2
    path.write_text(json.dumps(bundle), encoding="utf-8")

    rc = cli_main(["verify", "--json", str(path)])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert payload["error_code"] == VERIFY_SCHEMA_ERROR
    assert payload["primary_reason"] == VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED


def test_verifier_file_and_module_entrypoints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "signed.json"
    path.write_text(json.dumps(_signed_bundle()), encoding="utf-8")

    assert verify_proof_bundle_file(path, require_signed_attestation=True).error_code == VERIFY_OK
    assert verifier_main(["--bad-flag"]) == 2

    monkeypatch.setattr(sys, "stdin", io.StringIO(path.read_text(encoding="utf-8")))
    assert verifier_main([]) == 0

    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_unsigned_bundle())))
    assert verifier_main(["--strict"]) == 2

    monkeypatch.setattr(sys, "stdin", io.StringIO("{"))
    assert verifier_main([]) == 2


def test_schema_shape_validation_does_not_mutate_input() -> None:
    bundle = _signed_bundle()
    original = copy.deepcopy(bundle)

    assert verify_proof_bundle(bundle, require_signed_attestation=True).ok is True
    assert bundle == original
