# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import copy
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk" / "python" / "src"))

from attestplane import AttestSubstrate, EventDraft  # noqa: E402
from attestplane.proof_bundle import ProofBundleBuilder  # noqa: E402
from attestplane.verifier import (  # noqa: E402
    BundleSchemaError,
    classify_bundle_schema_error,
    verify_proof_bundle,
)
from attestplane.verify_reason_codes import (  # noqa: E402
    ALL_VERIFY_REASON_CODES_V1,
    VERIFY_REASON_ANCHOR_INVALID,
    VERIFY_REASON_CANONICAL_MISMATCH,
    VERIFY_REASON_REQUIRED_FIELD_MISSING,
    VERIFY_REASON_SCHEMA_INVALID,
    VERIFY_REASON_SCHEMA_UNKNOWN,
    VERIFY_REASON_SCHEMA_VERSION_MISSING,
    VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
    VERIFY_REASON_TAXONOMY_VERSION_UNSUPPORTED,
    VERIFY_REASON_SIGNATURE_INVALID,
    VERIFY_REASON_SIGNATURE_MISSING,
    VERIFY_REASON_STRUCTURE_INVALID,
    VERIFY_REASON_TAXONOMY_VERSION,
    is_known_verify_reason_code,
    verify_reason_code_explanation,
    verify_reason_code_matches_format,
)


def _bundle() -> dict:
    substrate = AttestSubstrate()
    event = substrate.append(
        EventDraft(event_type="eval_event", actor="agent", payload={"ok": True}),
        now=datetime(2026, 5, 22, tzinfo=UTC),
    )
    builder = ProofBundleBuilder(chain_id="reason-code", producer_runtime="test")
    builder.extend([event])
    return builder.build(now=datetime(2026, 5, 22, tzinfo=UTC))


def _signed_bundle() -> dict:
    bundle = _bundle()
    event_hash = bundle["events"][0]["event_hash_hex"]
    bundle["signatures"] = [
        {
            "key_id": "b" * 32,
            "public_key_der_b64": "AQ==",
            "signature_hex": "a" * 128,
            "signature_mode": "per_event",
            "signature_schema_version": 1,
            "signed_at": "2026-05-22T00:00:00+00:00",
            "signed_event_hash_hex": event_hash,
            "signed_payload_b64": "AQ==",
            "signed_seq": 0,
            "signing_cert_chain_b64": [],
        }
    ]
    return bundle


def test_verify_reason_code_taxonomy_is_stable_and_namespaced() -> None:
    assert VERIFY_REASON_TAXONOMY_VERSION == 1
    expected = (
        VERIFY_REASON_ANCHOR_INVALID,
        VERIFY_REASON_CANONICAL_MISMATCH,
        VERIFY_REASON_REQUIRED_FIELD_MISSING,
        VERIFY_REASON_SCHEMA_INVALID,
        VERIFY_REASON_SCHEMA_UNKNOWN,
        VERIFY_REASON_SCHEMA_VERSION_MISSING,
        VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
        VERIFY_REASON_TAXONOMY_VERSION_UNSUPPORTED,
        VERIFY_REASON_SIGNATURE_INVALID,
        VERIFY_REASON_SIGNATURE_MISSING,
        VERIFY_REASON_STRUCTURE_INVALID,
    )

    assert ALL_VERIFY_REASON_CODES_V1 == expected
    for code in ALL_VERIFY_REASON_CODES_V1:
        assert is_known_verify_reason_code(code)
        assert verify_reason_code_matches_format(code)
        assert verify_reason_code_explanation(code)


def test_verify_reason_code_ok_result_has_no_rejection_reason() -> None:
    result = verify_proof_bundle(_bundle())

    assert result.ok is True
    assert result.primary_reason is None
    assert result.secondary_reasons == ()


def test_verify_reason_code_canonical_mismatch_is_primary() -> None:
    bundle = _bundle()
    bundle["events"][0]["event_hash_hex"] = "f" * 64

    result = verify_proof_bundle(bundle)

    assert result.ok is False
    assert result.primary_reason == VERIFY_REASON_CANONICAL_MISMATCH


def test_verify_reason_code_signature_missing_is_primary_for_strict_unsigned_bundle() -> (
    None
):
    result = verify_proof_bundle(_bundle(), require_signed_attestation=True)

    assert result.ok is False
    assert result.primary_reason == VERIFY_REASON_SIGNATURE_MISSING


def test_verify_reason_code_signature_invalid_is_primary_for_malformed_signature_material() -> (
    None
):
    bundle = _signed_bundle()
    bundle["signatures"][0]["signature_hex"] = "not-hex"

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is False
    assert result.primary_reason == VERIFY_REASON_SIGNATURE_INVALID


def test_verify_reason_code_required_field_missing_is_primary_for_missing_signature_field() -> (
    None
):
    bundle = _signed_bundle()
    del bundle["signatures"][0]["signature_hex"]

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is False
    assert result.primary_reason == VERIFY_REASON_REQUIRED_FIELD_MISSING


def test_verify_reason_code_schema_version_unsupported_from_metadata_closure() -> None:
    bundle = _signed_bundle()
    bundle["chain_metadata"]["schema_version"] = 999

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is False
    assert result.primary_reason == VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED


def test_verify_reason_code_schema_version_missing_from_metadata_closure() -> None:
    bundle = _signed_bundle()
    del bundle["chain_metadata"]["schema_version"]

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is False
    assert result.primary_reason == VERIFY_REASON_SCHEMA_VERSION_MISSING


def test_verify_reason_code_unknown_required_metadata_field_is_schema_unknown() -> None:
    bundle = _signed_bundle()
    bundle["chain_metadata"]["critical_future_field"] = True

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is False
    assert result.primary_reason == VERIFY_REASON_SCHEMA_UNKNOWN
    assert "critical_future_field" in (result.metadata_reason or "")


def test_verify_reason_code_additive_unknown_fields_are_accepted() -> None:
    bundle = _signed_bundle()
    bundle["chain_metadata"]["future_minor_field"] = {"preserved": True}
    bundle["verification_report"]["future_minor_field"] = "ignored"
    bundle["future_top_level_field"] = "preserved"

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is True
    assert result.error_code == "VERIFY_OK"
    assert result.primary_reason is None
    assert result.secondary_reasons == ()


def test_verify_reason_code_canonical_mismatch_keeps_primary_before_schema_version() -> (
    None
):
    bundle = _signed_bundle()
    bundle["events"][0]["event_hash_hex"] = "f" * 64
    bundle["chain_metadata"]["schema_version"] = 999

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is False
    assert result.primary_reason == VERIFY_REASON_CANONICAL_MISMATCH
    assert VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED in result.secondary_reasons


def test_verify_reason_code_structure_invalid_for_policy_trace_refs() -> None:
    bundle = _bundle()
    bundle["policy_trace_refs"] = []

    result = verify_proof_bundle(bundle)

    assert result.ok is False
    assert result.primary_reason == VERIFY_REASON_STRUCTURE_INVALID


def test_verify_reason_code_secondary_reasons_are_deterministic_and_deduped() -> None:
    bundle = _bundle()
    bundle["events"][0]["event_hash_hex"] = "f" * 64
    bundle["policy_trace_refs"] = []

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.primary_reason == VERIFY_REASON_CANONICAL_MISMATCH
    assert list(result.secondary_reasons) == [
        VERIFY_REASON_SIGNATURE_MISSING,
        VERIFY_REASON_STRUCTURE_INVALID,
    ]


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ({"bundle_version": 999}, VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED),
        ({"verification_method": "future-method"}, VERIFY_REASON_SCHEMA_UNKNOWN),
        ({"events": "not-an-array"}, VERIFY_REASON_SCHEMA_INVALID),
    ],
)
def test_verify_reason_code_schema_exception_classification(
    mutation: dict[str, object],
    expected: str,
) -> None:
    bundle = copy.deepcopy(_bundle())
    if "verification_method" in mutation:
        bundle["verification_report"]["verification_method"] = mutation[
            "verification_method"
        ]
    else:
        bundle.update(mutation)

    with pytest.raises(BundleSchemaError) as exc_info:
        verify_proof_bundle(bundle)

    assert classify_bundle_schema_error(exc_info.value) == expected


def test_verify_reason_code_cli_json_smoke(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from attestplane.cli.main import main

    path = tmp_path / "unsigned.json"
    path.write_text(json.dumps(_bundle(), sort_keys=True), encoding="utf-8")

    rc = main(["verify", "--json", "--strict-schema", str(path)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 2
    assert payload["schema_version"] == 1
    assert payload["result"] == "fail"
    assert payload["exit_code"] == 2
    assert payload["reasons"][0]["code"] == VERIFY_REASON_SIGNATURE_MISSING
