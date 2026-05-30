# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from attestplane.cli.main import main  # noqa: E402
from attestplane.verifier import verify_proof_bundle, verify_proof_bundle_file  # noqa: E402
from attestplane.verify_errors import VERIFY_BUNDLE_SCHEMA_INCOMPLETE, VERIFY_OK  # noqa: E402
from attestplane.verify_reason_codes import (  # noqa: E402
    VERIFY_REASON_SCHEMA_VERSION_MISSING,
    VERIFY_REASON_SCHEMA_UNKNOWN,
    VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
)

FIXTURES = ROOT / "tests" / "fixtures" / "bundles"


def _load_fixture(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def test_strict_verifier_accepts_bundle_with_signed_attestation_schema() -> None:
    result = verify_proof_bundle(
        _load_fixture("valid_signed_attestation.json"),
        require_signed_attestation=True,
    )

    assert result.ok is True
    assert result.error_code == VERIFY_OK
    assert result.primary_reason is None
    assert result.secondary_reasons == ()
    assert result.signed_attestation_schema_ok is True
    assert result.signed_attestation_schema_reason is None


def test_require_non_empty_also_enforces_signed_attestation_schema() -> None:
    result = verify_proof_bundle(
        _load_fixture("empty_attestations.json"),
        require_non_empty=True,
    )

    assert result.ok is False
    assert result.event_count == 1
    assert result.error_code == VERIFY_BUNDLE_SCHEMA_INCOMPLETE
    assert result.primary_reason == "att.verify.signature_missing"
    assert result.signed_attestation_schema_ok is False
    assert "signatures" in (result.signed_attestation_schema_reason or "")


def test_empty_event_bundle_keeps_existing_non_empty_error_code() -> None:
    bundle = _load_fixture("empty_attestations.json")
    bundle["events"] = []
    bundle["chain_metadata"]["head_hash_hex"] = "0" * 64
    bundle["chain_metadata"]["head_seq"] = -1

    result = verify_proof_bundle(bundle, require_non_empty=True)

    assert result.ok is False
    assert result.error_code == "VERIFY_REQUIRED_FIELDS_MISSING"
    assert result.primary_reason == "att.verify.required_field_missing"


def test_missing_signatures_fixture_fails_with_incomplete_schema() -> None:
    result = verify_proof_bundle_file(
        FIXTURES / "missing_signatures.json",
        require_signed_attestation=True,
    )

    assert result.ok is False
    assert result.error_code == VERIFY_BUNDLE_SCHEMA_INCOMPLETE
    assert result.primary_reason == "att.verify.signature_missing"


def test_malformed_signature_fixture_fails_with_incomplete_schema() -> None:
    result = verify_proof_bundle_file(
        FIXTURES / "malformed_signature.json",
        require_signed_attestation=True,
    )

    assert result.ok is False
    assert result.error_code == VERIFY_BUNDLE_SCHEMA_INCOMPLETE
    assert result.primary_reason == "att.verify.signature_invalid"
    assert "malformed" in (result.signed_attestation_schema_reason or "")


def test_signature_digest_mismatch_fixture_fails_with_incomplete_schema() -> None:
    result = verify_proof_bundle_file(
        FIXTURES / "signature_digest_mismatch.json",
        require_signed_attestation=True,
    )

    assert result.ok is False
    assert result.error_code == VERIFY_BUNDLE_SCHEMA_INCOMPLETE
    assert result.primary_reason == "att.verify.signature_invalid"
    assert "canonical bundle event" in (result.signed_attestation_schema_reason or "")


def test_bundle_verifier_accepts_additive_unknown_fields() -> None:
    bundle = _load_fixture("valid_signed_attestation.json")
    bundle["future_bundle_field"] = {"preserved": True}
    bundle["chain_metadata"]["future_metadata_field"] = "kept"
    bundle["verification_report"]["future_report_field"] = "ignored"

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is True
    assert result.error_code == VERIFY_OK
    assert result.primary_reason is None
    assert result.secondary_reasons == ()


def test_bundle_verifier_rejects_missing_schema_version() -> None:
    bundle = _load_fixture("valid_signed_attestation.json")
    del bundle["chain_metadata"]["schema_version"]

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is False
    assert result.primary_reason == VERIFY_REASON_SCHEMA_VERSION_MISSING
    assert result.error_code != VERIFY_OK


def test_bundle_verifier_rejects_unknown_schema_version_major() -> None:
    bundle = _load_fixture("valid_signed_attestation.json")
    bundle["chain_metadata"]["schema_version"] = 999

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is False
    assert result.primary_reason == VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED


def test_bundle_verifier_rejects_unknown_required_metadata_field() -> None:
    bundle = _load_fixture("valid_signed_attestation.json")
    bundle["chain_metadata"]["critical_future_field"] = True

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is False
    assert result.primary_reason == VERIFY_REASON_SCHEMA_UNKNOWN
    assert "critical_future_field" in (result.metadata_reason or "")


def test_cli_bundle_option_uses_strict_schema_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(["verify", "--bundle", str(FIXTURES / "empty_attestations.json")])
    out = capsys.readouterr().out

    assert rc == 2
    assert "bundle.schema.incomplete" in out
