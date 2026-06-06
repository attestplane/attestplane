# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coverage-completion tests for attestplane.cli.proofbundle_alpha.

These tests exercise the internal helper functions directly (via the module's
public + private API) to reach every missing branch identified in the coverage
report, while also verifying the full CLI integration path for a representative
set of cases.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# ── module under test ──────────────────────────────────────────────────────────
from attestplane.canonical import canonicalize
from attestplane.cli.proofbundle_alpha import (
    AlphaCheck,
    _alpha_error_code,
    _anchor_extension,
    _check_artifact,
    _check_dsse_envelope,
    _check_hash_chain,
    _check_in_toto_statement,
    _check_obligation_refs,
    _check_proof_bundle,
    _check_provenance,
    _check_root_shape,
    _check_schema_version,
    _check_storage_compatibility,
    _is_hex64,
    _load_json,
    _report,
    _signature_extension,
    verify_alpha_proofbundle_file,
)
from attestplane.intoto import DSSE_PAYLOAD_TYPE as _DSSE_PAYLOAD_TYPE
from attestplane.intoto import dsse_pae
from attestplane.verify_errors import (
    VERIFY_ARTIFACT_HASH_FAILED,
    VERIFY_CHAIN_RECOMPUTE_FAILED,
    VERIFY_EXTENSION_FAILED,
    VERIFY_EXTENSION_INVALID_INPUT,
    VERIFY_EXTENSION_UNSUPPORTED,
    VERIFY_OK,
    VERIFY_REQUIRED_FIELDS_MISSING,
    VERIFY_SCHEMA_ERROR,
)

# ── fixture helpers ────────────────────────────────────────────────────────────
FIXTURE_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "proofbundle"
VALID_MINIMAL = FIXTURE_DIR / "valid_minimal.json"


def _base() -> dict[str, Any]:
    """Return a deep copy of the valid_minimal fixture as a Python dict."""
    result: dict[str, Any] = json.loads(VALID_MINIMAL.read_text(encoding="utf-8"))
    return result


def _write(tmp_path: Path, data: dict[str, Any], name: str = "bundle.json") -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def _recompute_artifact_sha(data: dict[str, Any]) -> dict[str, Any]:
    """Recompute artifact.sha256 for a mutated proof_bundle."""
    data = copy.deepcopy(data)
    data["artifact"]["sha256"] = hashlib.sha256(canonicalize(data["proof_bundle"])).hexdigest()
    return data


# ═══════════════════════════════════════════════════════════════════════════════
# _is_hex64
# ═══════════════════════════════════════════════════════════════════════════════


def test_is_hex64_valid() -> None:
    assert _is_hex64("a" * 64) is True
    assert _is_hex64("0123456789abcdef" * 4) is True


def test_is_hex64_invalid() -> None:
    assert _is_hex64("A" * 64) is False  # uppercase
    assert _is_hex64("a" * 63) is False  # too short
    assert _is_hex64("a" * 65) is False  # too long
    assert _is_hex64(123) is False  # not a string
    assert _is_hex64("") is False


# ═══════════════════════════════════════════════════════════════════════════════
# _load_json
# ═══════════════════════════════════════════════════════════════════════════════


def test_load_json_file_not_found(tmp_path: Path) -> None:
    missing = tmp_path / "no_such_file.json"
    result, check = _load_json(missing)
    assert result is None
    assert check.status == "fail"
    assert check.name == "json_read"
    assert check.failure_kind == "invalid_input"
    assert "cannot read input file" in (check.detail or "")


def test_load_json_malformed(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    result, check = _load_json(bad)
    assert result is None
    assert check.status == "fail"
    assert check.name == "json_parse"
    assert "malformed JSON" in (check.detail or "")


def test_load_json_valid(tmp_path: Path) -> None:
    p = tmp_path / "good.json"
    p.write_text('{"key": 1}', encoding="utf-8")
    result, check = _load_json(p)
    assert result == {"key": 1}
    assert check.status == "pass"
    assert check.name == "json_parse"


# ═══════════════════════════════════════════════════════════════════════════════
# _check_root_shape
# ═══════════════════════════════════════════════════════════════════════════════


def test_check_root_shape_non_dict() -> None:
    res_dict, check = _check_root_shape([1, 2, 3])
    assert res_dict is None
    assert check.status == "fail"
    assert check.name == "root_object"
    assert "must be a JSON object" in (check.detail or "")


def test_check_root_shape_missing_fields() -> None:
    root: dict[str, Any] = {"proofbundle_verifier_schema_version": 1}
    res_dict, check = _check_root_shape(root)
    # Returns root (not None) even when fields missing
    assert res_dict is root
    assert check.status == "fail"
    assert check.name == "required_fields"
    assert "missing required fields" in (check.detail or "")


def test_check_root_shape_valid() -> None:
    data = _base()
    res_dict, check = _check_root_shape(data)
    assert res_dict is data
    assert check.status == "pass"
    assert check.name == "required_fields"


# ═══════════════════════════════════════════════════════════════════════════════
# _check_schema_version
# ═══════════════════════════════════════════════════════════════════════════════


def test_check_schema_version_unsupported() -> None:
    data = _base()
    data["proofbundle_verifier_schema_version"] = 99
    check = _check_schema_version(data)
    assert check.status == "fail"
    assert "unsupported" in (check.detail or "")


def test_check_schema_version_none() -> None:
    data = _base()
    data["proofbundle_verifier_schema_version"] = None
    check = _check_schema_version(data)
    assert check.status == "fail"


def test_check_schema_version_valid() -> None:
    check = _check_schema_version(_base())
    assert check.status == "pass"


# ═══════════════════════════════════════════════════════════════════════════════
# _check_artifact
# ═══════════════════════════════════════════════════════════════════════════════


def test_check_artifact_not_dict() -> None:
    data = _base()
    data["artifact"] = "string"
    check = _check_artifact(data)
    assert check.status == "fail"
    assert "must be a JSON object" in (check.detail or "")


def test_check_artifact_wrong_hash_algorithm() -> None:
    data = _base()
    data["artifact"]["hash_algorithm"] = "md5"
    check = _check_artifact(data)
    assert check.status == "fail"
    assert "hash_algorithm" in (check.detail or "")


def test_check_artifact_wrong_target() -> None:
    data = _base()
    data["artifact"]["target"] = "something_else"
    check = _check_artifact(data)
    assert check.status == "fail"
    assert "target" in (check.detail or "")


def test_check_artifact_bad_sha256_format() -> None:
    data = _base()
    data["artifact"]["sha256"] = "not-hex"
    check = _check_artifact(data)
    assert check.status == "fail"
    assert "64-hex" in (check.detail or "")


def test_check_artifact_non_canonicalizable(tmp_path: Path) -> None:
    """proof_bundle contains a float NaN → CanonicalizationError path."""
    data = _base()
    # Patch canonicalize to raise CanonicalizationError
    from attestplane.canonical import CanonicalizationError

    with patch("attestplane.cli.proofbundle_alpha.canonicalize", side_effect=CanonicalizationError("nan")):
        check = _check_artifact(data)
    assert check.status == "fail"
    assert "not canonicalizable" in (check.detail or "")


def test_check_artifact_hash_mismatch() -> None:
    data = _base()
    data["artifact"]["sha256"] = "a" * 64  # wrong hash
    check = _check_artifact(data)
    assert check.status == "fail"
    assert check.failure_kind == "verification_failed"
    assert "does not match" in (check.detail or "")


def test_check_artifact_valid() -> None:
    check = _check_artifact(_base())
    assert check.status == "pass"


# ═══════════════════════════════════════════════════════════════════════════════
# _check_proof_bundle
# ═══════════════════════════════════════════════════════════════════════════════


def test_check_proof_bundle_not_dict() -> None:
    data = _base()
    data["proof_bundle"] = "not a dict"
    pb, checks = _check_proof_bundle(data)
    assert pb is None
    assert len(checks) == 1
    assert checks[0].status == "fail"
    assert "must be a JSON object" in (checks[0].detail or "")


def test_check_proof_bundle_schema_error() -> None:
    """Trigger BundleSchemaError by passing a dict missing required bundle fields."""
    data = _base()
    data["proof_bundle"] = {"bad": "shape"}
    pb, checks = _check_proof_bundle(data)
    # pb is the dict itself (even on schema error), checks has one fail
    assert any(c.status == "fail" and c.name == "proof_bundle_shape" for c in checks)


def test_check_proof_bundle_valid() -> None:
    data = _base()
    pb, checks = _check_proof_bundle(data)
    assert pb is not None
    assert all(c.status == "pass" for c in checks)


def test_check_proof_bundle_broken_hash_chain() -> None:
    """Tamper with an event hash so verify_proof_bundle returns result.ok=False (lines 158-161)."""
    data = _base()
    data["proof_bundle"]["events"][0]["event_hash_hex"] = "a" * 64
    pb, checks = _check_proof_bundle(data)
    assert pb is not None
    failed = [c for c in checks if c.status == "fail"]
    assert len(failed) == 1
    assert failed[0].name == "hash_chain_recompute"
    assert failed[0].failure_kind == "verification_failed"


# ═══════════════════════════════════════════════════════════════════════════════
# _check_hash_chain
# ═══════════════════════════════════════════════════════════════════════════════


def test_check_hash_chain_not_dict() -> None:
    data = _base()
    data["hash_chain"] = "not dict"
    check = _check_hash_chain(data, data["proof_bundle"])
    assert check.status == "fail"
    assert "must be a JSON object" in (check.detail or "")


def test_check_hash_chain_bad_head_hash_hex() -> None:
    data = _base()
    data["hash_chain"]["head_hash_hex"] = "not-hex"
    check = _check_hash_chain(data, data["proof_bundle"])
    assert check.status == "fail"
    assert "head_hash_hex" in (check.detail or "")


def test_check_hash_chain_head_seq_not_int() -> None:
    data = _base()
    data["hash_chain"]["head_seq"] = "not-int"
    check = _check_hash_chain(data, data["proof_bundle"])
    assert check.status == "fail"
    assert "head_seq" in (check.detail or "")


def test_check_hash_chain_proof_bundle_none() -> None:
    data = _base()
    check = _check_hash_chain(data, None)
    assert check.status == "fail"
    assert "unavailable" in (check.detail or "")


def test_check_hash_chain_chain_metadata_not_dict() -> None:
    data = _base()
    pb = copy.deepcopy(data["proof_bundle"])
    pb["chain_metadata"] = "not dict"
    check = _check_hash_chain(data, pb)
    assert check.status == "fail"
    assert "chain_metadata unavailable" in (check.detail or "")


def test_check_hash_chain_mismatch() -> None:
    data = _base()
    data["hash_chain"]["head_seq"] = 999
    check = _check_hash_chain(data, data["proof_bundle"])
    assert check.status == "fail"
    assert check.failure_kind == "verification_failed"


def test_check_hash_chain_valid() -> None:
    data = _base()
    check = _check_hash_chain(data, data["proof_bundle"])
    assert check.status == "pass"


# ═══════════════════════════════════════════════════════════════════════════════
# _check_obligation_refs
# ═══════════════════════════════════════════════════════════════════════════════


def test_check_obligation_refs_not_list() -> None:
    data = _base()
    data["obligation_references"] = "not a list"
    check = _check_obligation_refs(data, data["proof_bundle"])
    assert check.status == "fail"
    assert "must be an array" in (check.detail or "")


def test_check_obligation_refs_item_not_dict() -> None:
    data = _base()
    data["obligation_references"] = ["not a dict"]
    check = _check_obligation_refs(data, data["proof_bundle"])
    assert check.status == "fail"
    assert "must be an object" in (check.detail or "")


def test_check_obligation_refs_missing_obligation_id() -> None:
    data = _base()
    data["obligation_references"] = [{"source": "fw"}]
    check = _check_obligation_refs(data, data["proof_bundle"])
    assert check.status == "fail"
    assert "obligation_id is invalid" in (check.detail or "")


def test_check_obligation_refs_empty_obligation_id() -> None:
    data = _base()
    data["obligation_references"] = [{"obligation_id": ""}]
    check = _check_obligation_refs(data, data["proof_bundle"])
    assert check.status == "fail"
    assert "obligation_id is invalid" in (check.detail or "")


def test_check_obligation_refs_duplicate() -> None:
    data = _base()
    oid = "eu_ai_act.art12.3c.matched_input_data"
    data["obligation_references"] = [{"obligation_id": oid}, {"obligation_id": oid}]
    check = _check_obligation_refs(data, data["proof_bundle"])
    assert check.status == "fail"
    assert "duplicate" in (check.detail or "")


def test_check_obligation_refs_unknown() -> None:
    data = _base()
    data["obligation_references"] = [{"obligation_id": "unknown.obligation.xyz"}]
    check = _check_obligation_refs(data, data["proof_bundle"])
    assert check.status == "fail"
    assert "unknown obligation ids" in (check.detail or "")


def test_check_obligation_refs_framework_mappings_not_list() -> None:
    data = _base()
    data["obligation_references"] = [{"obligation_id": "eu_ai_act.art12.3c.matched_input_data"}]
    pb = copy.deepcopy(data["proof_bundle"])
    pb["framework_mappings"] = "not a list"
    check = _check_obligation_refs(data, pb)
    assert check.status == "fail"
    assert "framework_mappings must be an array" in (check.detail or "")


def test_check_obligation_refs_framework_mappings_item_invalid() -> None:
    data = _base()
    data["obligation_references"] = [{"obligation_id": "eu_ai_act.art12.3c.matched_input_data"}]
    pb = copy.deepcopy(data["proof_bundle"])
    pb["framework_mappings"] = [{"no_obligation_id": "bad"}]
    check = _check_obligation_refs(data, pb)
    assert check.status == "fail"
    assert "obligation_id invalid" in (check.detail or "")


def test_check_obligation_refs_order_mismatch() -> None:
    data = _base()
    data["obligation_references"] = [{"obligation_id": "eu_ai_act.art12.1.automatic_recording"}]
    check = _check_obligation_refs(data, data["proof_bundle"])
    assert check.status == "fail"
    assert check.failure_kind == "verification_failed"
    assert "must match" in (check.detail or "")


def test_check_obligation_refs_proof_bundle_none() -> None:
    """With proof_bundle=None, declared=[] => bundle_ids=[] => only obligation order is checked."""
    data = _base()
    data["obligation_references"] = []
    check = _check_obligation_refs(data, None)
    # declared=[], bundle_ids=[] => pass (no bundle to compare against)
    assert check.status == "pass"


def test_check_obligation_refs_valid() -> None:
    check = _check_obligation_refs(_base(), _base()["proof_bundle"])
    assert check.status == "pass"


# ═══════════════════════════════════════════════════════════════════════════════
# _check_in_toto_statement
# ═══════════════════════════════════════════════════════════════════════════════


def test_check_in_toto_statement_not_dict() -> None:
    data = _base()
    data["in_toto_statement"] = "not dict"
    check = _check_in_toto_statement(data, data["proof_bundle"])
    assert check.status == "fail"
    assert "must be a JSON object" in (check.detail or "")


def test_check_in_toto_statement_wrong_type() -> None:
    data = _base()
    data["in_toto_statement"]["_type"] = "wrong"
    check = _check_in_toto_statement(data, data["proof_bundle"])
    assert check.status == "fail"
    assert "_type" in (check.detail or "")


def test_check_in_toto_statement_wrong_predicate_type() -> None:
    data = _base()
    data["in_toto_statement"]["predicateType"] = "wrong"
    check = _check_in_toto_statement(data, data["proof_bundle"])
    assert check.status == "fail"
    assert "predicateType" in (check.detail or "")


def test_check_in_toto_statement_empty_subject() -> None:
    data = _base()
    data["in_toto_statement"]["subject"] = []
    check = _check_in_toto_statement(data, data["proof_bundle"])
    assert check.status == "fail"
    assert "subject" in (check.detail or "")


def test_check_in_toto_statement_subject_not_list() -> None:
    data = _base()
    data["in_toto_statement"]["subject"] = "not a list"
    check = _check_in_toto_statement(data, data["proof_bundle"])
    assert check.status == "fail"


def test_check_in_toto_statement_bad_digest() -> None:
    data = _base()
    data["in_toto_statement"]["subject"][0]["digest"]["sha256"] = "not-hex"
    check = _check_in_toto_statement(data, data["proof_bundle"])
    assert check.status == "fail"
    assert "digest" in (check.detail or "")


def test_check_in_toto_statement_digest_missing() -> None:
    data = _base()
    data["in_toto_statement"]["subject"][0]["digest"] = {}
    check = _check_in_toto_statement(data, data["proof_bundle"])
    assert check.status == "fail"


def test_check_in_toto_statement_predicate_not_dict() -> None:
    data = _base()
    data["in_toto_statement"]["predicate"] = "not dict"
    check = _check_in_toto_statement(data, data["proof_bundle"])
    assert check.status == "fail"
    assert "predicate must be an object" in (check.detail or "")


def test_check_in_toto_statement_proof_bundle_none() -> None:
    data = _base()
    check = _check_in_toto_statement(data, None)
    assert check.status == "fail"
    assert "proof_bundle unavailable" in (check.detail or "")


def test_check_in_toto_statement_digest_mismatch() -> None:
    data = _base()
    data["in_toto_statement"]["subject"][0]["digest"]["sha256"] = "a" * 64
    check = _check_in_toto_statement(data, data["proof_bundle"])
    assert check.status == "fail"
    assert check.failure_kind == "verification_failed"
    assert "does not match chain head" in (check.detail or "")


def test_check_in_toto_statement_chain_metadata_mismatch() -> None:
    data = _base()
    data["in_toto_statement"]["predicate"]["chain_metadata"] = {"wrong": "data"}
    check = _check_in_toto_statement(data, data["proof_bundle"])
    assert check.status == "fail"
    assert check.failure_kind == "verification_failed"
    assert "chain_metadata does not match" in (check.detail or "")


def test_check_in_toto_statement_valid() -> None:
    data = _base()
    check = _check_in_toto_statement(data, data["proof_bundle"])
    assert check.status == "pass"


# ═══════════════════════════════════════════════════════════════════════════════
# _check_dsse_envelope
# ═══════════════════════════════════════════════════════════════════════════════


def test_check_dsse_envelope_not_dict() -> None:
    data = _base()
    data["dsse_envelope"] = "not dict"
    check = _check_dsse_envelope(data)
    assert check.status == "fail"
    assert "must be a JSON object" in (check.detail or "")


def test_check_dsse_envelope_wrong_payload_type() -> None:
    data = _base()
    data["dsse_envelope"]["payloadType"] = "wrong/type"
    check = _check_dsse_envelope(data)
    assert check.status == "fail"
    assert "payloadType" in (check.detail or "")


def test_check_dsse_envelope_payload_not_string() -> None:
    data = _base()
    data["dsse_envelope"]["payload"] = 123
    check = _check_dsse_envelope(data)
    assert check.status == "fail"
    assert "base64 text" in (check.detail or "")


def test_check_dsse_envelope_signatures_not_list() -> None:
    data = _base()
    data["dsse_envelope"]["signatures"] = "not a list"
    check = _check_dsse_envelope(data)
    assert check.status == "fail"
    assert "must be an array" in (check.detail or "")


def test_check_dsse_envelope_signature_item_not_dict() -> None:
    data = _base()
    data["dsse_envelope"]["signatures"] = ["not_a_dict"]
    check = _check_dsse_envelope(data)
    assert check.status == "fail"
    assert "must be an object" in (check.detail or "")


def test_check_dsse_envelope_payload_not_base64_json() -> None:
    data = _base()
    data["dsse_envelope"]["payload"] = base64.standard_b64encode(b"not json").decode()
    check = _check_dsse_envelope(data)
    assert check.status == "fail"
    assert "not base64 JSON" in (check.detail or "")


def test_check_dsse_envelope_payload_mismatch() -> None:
    data = _base()
    data["dsse_envelope"]["payload"] = base64.standard_b64encode(
        json.dumps({"other": "data"}).encode()
    ).decode()
    check = _check_dsse_envelope(data)
    assert check.status == "fail"
    assert check.failure_kind == "verification_failed"
    assert "does not match in_toto_statement" in (check.detail or "")


def test_check_dsse_envelope_valid() -> None:
    data = _base()
    check = _check_dsse_envelope(data)
    assert check.status == "pass"


def test_check_dsse_envelope_multiple_valid_sig_dicts() -> None:
    """Multiple valid sig dict entries all pass isinstance check (branch 286->285 loops)."""
    data = _base()
    data["dsse_envelope"]["signatures"] = [{"keyid": "k1"}, {"keyid": "k2"}]
    check = _check_dsse_envelope(data)
    assert check.status == "pass"


# ═══════════════════════════════════════════════════════════════════════════════
# _check_storage_compatibility
# ═══════════════════════════════════════════════════════════════════════════════


def test_check_storage_compatibility_not_dict() -> None:
    data = _base()
    data["storage_compatibility"] = "not dict"
    check = _check_storage_compatibility(data)
    assert check.status == "fail"
    assert "must be a JSON object" in (check.detail or "")


def test_check_storage_compatibility_wrong_schema_version() -> None:
    data = _base()
    data["storage_compatibility"]["schema_version"] = "wrong"
    check = _check_storage_compatibility(data)
    assert check.status == "fail"
    assert "schema_version" in (check.detail or "")


def test_check_storage_compatibility_wrong_record_format() -> None:
    data = _base()
    data["storage_compatibility"]["record_format"] = "wrong"
    check = _check_storage_compatibility(data)
    assert check.status == "fail"
    assert "record_format" in (check.detail or "")


def test_check_storage_compatibility_wrong_backend() -> None:
    data = _base()
    data["storage_compatibility"]["backend"] = "postgres"
    check = _check_storage_compatibility(data)
    assert check.status == "fail"
    assert "backend" in (check.detail or "")


def test_check_storage_compatibility_multi_writer_safe_true() -> None:
    data = _base()
    data["storage_compatibility"]["multi_writer_safe"] = True
    check = _check_storage_compatibility(data)
    assert check.status == "fail"
    assert "multi_writer_safe" in (check.detail or "")


def test_check_storage_compatibility_valid() -> None:
    check = _check_storage_compatibility(_base())
    assert check.status == "pass"


# ═══════════════════════════════════════════════════════════════════════════════
# _check_provenance
# ═══════════════════════════════════════════════════════════════════════════════


def test_check_provenance_not_dict() -> None:
    data = _base()
    data["provenance"] = "not dict"
    check = _check_provenance(data)
    assert check.status == "fail"
    assert "must be a JSON object" in (check.detail or "")


def test_check_provenance_slsa_level_not_null() -> None:
    data = _base()
    data["provenance"]["slsa_level_claimed"] = 3
    check = _check_provenance(data)
    assert check.status == "fail"
    assert "slsa_level_claimed" in (check.detail or "")


def test_check_provenance_certified_provenance_not_false() -> None:
    data = _base()
    data["provenance"]["certified_provenance"] = True
    check = _check_provenance(data)
    assert check.status == "fail"
    assert "certified_provenance" in (check.detail or "")


def test_check_provenance_production_supply_chain_security_not_false() -> None:
    data = _base()
    data["provenance"]["production_supply_chain_security"] = True
    check = _check_provenance(data)
    assert check.status == "fail"
    assert "production_supply_chain_security" in (check.detail or "")


def test_check_provenance_valid() -> None:
    check = _check_provenance(_base())
    assert check.status == "pass"


# ═══════════════════════════════════════════════════════════════════════════════
# _signature_extension
# ═══════════════════════════════════════════════════════════════════════════════


def test_signature_extension_not_requested() -> None:
    status, summary, check = _signature_extension(_base(), requested=False)
    assert status == "skipped"
    assert check is None
    assert summary["performed"] is False


def test_signature_extension_root_none() -> None:
    status, summary, check = _signature_extension(None, requested=True)
    assert status == "invalid_input"
    assert check is not None
    assert "unavailable" in (check.detail or "")


def test_signature_extension_unsupported_algorithm() -> None:
    data = _base()
    data["signature_material"] = {"algorithm": "rsa-pss"}
    status, summary, check = _signature_extension(data, requested=True)
    assert status == "unsupported"
    assert summary["reason"] == "unsupported_algorithm"
    assert check is not None
    assert "rsa-pss" in (check.detail or "")


def test_signature_extension_missing_material_empty_signatures() -> None:
    """No signature_material and empty signatures → missing_material."""
    data = _base()
    # dsse_envelope.signatures is already [] in valid_minimal
    status, summary, check = _signature_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "missing_material"


def test_signature_extension_sigs_present_no_material() -> None:
    """Signatures list non-empty but no signature_material block."""
    data = _base()
    data["dsse_envelope"]["signatures"] = [{"keyid": "k", "sig": "abc"}]
    # no signature_material
    status, summary, check = _signature_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "missing_material"
    assert "signature_material block missing" in (check.detail or "")  # type: ignore[union-attr]


def test_signature_extension_wrong_payload_type() -> None:
    data = _base()
    data["dsse_envelope"]["payloadType"] = "wrong/type"
    data["dsse_envelope"]["signatures"] = [{"keyid": "k", "sig": "abc"}]
    data["signature_material"] = {
        "algorithm": "ed25519",
        "public_keys": [{"keyid": "k", "public_key_pem": "irrelevant"}],
    }
    status, summary, check = _signature_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "wrong_payload_type"


def test_signature_extension_payload_not_string() -> None:
    data = _base()
    data["dsse_envelope"]["payload"] = 999
    data["dsse_envelope"]["signatures"] = [{"keyid": "k", "sig": "abc"}]
    data["signature_material"] = {
        "algorithm": "ed25519",
        "public_keys": [{"keyid": "k", "public_key_pem": "irrelevant"}],
    }
    status, summary, check = _signature_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "payload_not_base64_string"


def test_signature_extension_payload_bad_b64() -> None:
    data = _base()
    data["dsse_envelope"]["payload"] = "!!!invalid_base64!!!"
    data["dsse_envelope"]["signatures"] = [{"keyid": "k", "sig": "abc"}]
    data["signature_material"] = {
        "algorithm": "ed25519",
        "public_keys": [{"keyid": "k", "public_key_pem": "irrelevant"}],
    }
    status, summary, check = _signature_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "payload_base64_decode_failed"


def test_signature_extension_empty_public_keys() -> None:
    data = _base()
    payload_b64 = data["dsse_envelope"]["payload"]
    data["dsse_envelope"]["signatures"] = [{"keyid": "k", "sig": "abc"}]
    data["signature_material"] = {
        "algorithm": "ed25519",
        "public_keys": [],
    }
    status, summary, check = _signature_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "missing_public_keys"


def test_signature_extension_public_key_item_not_dict() -> None:
    data = _base()
    data["dsse_envelope"]["signatures"] = [{"keyid": "k", "sig": "abc"}]
    data["signature_material"] = {
        "algorithm": "ed25519",
        "public_keys": ["not a dict"],
    }
    status, summary, check = _signature_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "invalid_public_key_entry"


def test_signature_extension_public_key_missing_pem() -> None:
    data = _base()
    data["dsse_envelope"]["signatures"] = [{"keyid": "k", "sig": "abc"}]
    data["signature_material"] = {
        "algorithm": "ed25519",
        "public_keys": [{"keyid": "k"}],  # missing public_key_pem
    }
    status, summary, check = _signature_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "missing_keyid_or_pem"


def test_signature_extension_bad_pem() -> None:
    data = _base()
    data["dsse_envelope"]["signatures"] = [{"keyid": "k", "sig": "abc"}]
    data["signature_material"] = {
        "algorithm": "ed25519",
        "public_keys": [{"keyid": "k", "public_key_pem": "this is not a pem"}],
    }
    status, summary, check = _signature_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "invalid_pem_public_key"


def test_signature_extension_wrong_key_type() -> None:
    """RSA key provided where ed25519 expected → unsupported."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key

    rsa_priv = generate_private_key(65537, 2048)
    pem = rsa_priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    data = _base()
    data["dsse_envelope"]["signatures"] = [{"keyid": "k", "sig": "abc"}]
    data["signature_material"] = {
        "algorithm": "ed25519",
        "public_keys": [{"keyid": "k", "public_key_pem": pem}],
    }
    status, summary, check = _signature_extension(data, requested=True)
    assert status == "unsupported"
    assert summary["reason"] == "wrong_public_key_type"


def test_signature_extension_sig_entry_not_dict() -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    sk = Ed25519PrivateKey.generate()
    pem = sk.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    data = _base()
    data["dsse_envelope"]["signatures"] = ["not_a_dict"]
    data["signature_material"] = {
        "algorithm": "ed25519",
        "public_keys": [{"keyid": "k", "public_key_pem": pem}],
    }
    status, summary, check = _signature_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "invalid_signature_entry"


def test_signature_extension_sig_entry_missing_sig() -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    sk = Ed25519PrivateKey.generate()
    pem = sk.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    data = _base()
    data["dsse_envelope"]["signatures"] = [{"keyid": "k"}]  # missing sig
    data["signature_material"] = {
        "algorithm": "ed25519",
        "public_keys": [{"keyid": "k", "public_key_pem": pem}],
    }
    status, summary, check = _signature_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "missing_sig_or_keyid"


def test_signature_extension_unknown_keyid() -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    sk = Ed25519PrivateKey.generate()
    pem = sk.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    data = _base()
    data["dsse_envelope"]["signatures"] = [{"keyid": "unknown-key", "sig": "abc"}]
    data["signature_material"] = {
        "algorithm": "ed25519",
        "public_keys": [{"keyid": "known-key", "public_key_pem": pem}],
    }
    status, summary, check = _signature_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "unknown_keyid"


def test_signature_extension_tampered_sig_does_not_verify() -> None:
    """InvalidSignature exception → status='failed' (lines 536-546)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    sk = Ed25519PrivateKey.generate()
    pem = sk.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    data = _base()
    payload_bytes = base64.standard_b64decode(data["dsse_envelope"]["payload"])
    pae = dsse_pae(_DSSE_PAYLOAD_TYPE, payload_bytes)
    sig = sk.sign(pae)
    # Corrupt the signature so it fails verification
    bad_sig = bytearray(sig)
    bad_sig[-1] ^= 0x01
    bad_sig_b64 = base64.standard_b64encode(bytes(bad_sig)).decode("ascii")

    data["dsse_envelope"]["signatures"] = [{"keyid": "k1", "sig": bad_sig_b64}]
    data["signature_material"] = {
        "algorithm": "ed25519",
        "public_keys": [{"keyid": "k1", "public_key_pem": pem}],
    }
    status, summary, check = _signature_extension(data, requested=True)
    assert status == "failed"
    assert summary["reason"] == "signature_does_not_verify"
    assert check is not None
    assert check.failure_kind == "verification_failed"


def test_signature_extension_passes_with_valid_sig() -> None:
    """Full success path: signature verifies (lines 536-553)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    sk = Ed25519PrivateKey.generate()
    pem = sk.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    data = _base()
    payload_bytes = base64.standard_b64decode(data["dsse_envelope"]["payload"])
    pae = dsse_pae(_DSSE_PAYLOAD_TYPE, payload_bytes)
    sig_b64 = base64.standard_b64encode(sk.sign(pae)).decode("ascii")

    data["dsse_envelope"]["signatures"] = [{"keyid": "k1", "sig": sig_b64}]
    data["signature_material"] = {
        "algorithm": "ed25519",
        "public_keys": [{"keyid": "k1", "public_key_pem": pem}],
    }
    status, summary, check = _signature_extension(data, requested=True)
    assert status == "passed"
    assert summary["reason"] == "dsse_ed25519_pae_signatures_verified"
    assert summary["verified_signature_count"] == 1
    assert check is not None
    assert check.status == "pass"


def test_signature_extension_bad_sig_b64() -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    sk = Ed25519PrivateKey.generate()
    pem = sk.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    data = _base()
    data["dsse_envelope"]["signatures"] = [{"keyid": "k", "sig": "!!!invalid!!!"}]
    data["signature_material"] = {
        "algorithm": "ed25519",
        "public_keys": [{"keyid": "k", "public_key_pem": pem}],
    }
    status, summary, check = _signature_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "sig_base64_decode_failed"


# ═══════════════════════════════════════════════════════════════════════════════
# _anchor_extension
# ═══════════════════════════════════════════════════════════════════════════════


def test_anchor_extension_not_requested() -> None:
    status, summary, check = _anchor_extension(_base(), requested=False)
    assert status == "skipped"
    assert check is None


def test_anchor_extension_root_none() -> None:
    status, summary, check = _anchor_extension(None, requested=True)
    assert status == "invalid_input"
    assert check is not None
    assert "unavailable" in (check.detail or "")


def test_anchor_extension_no_anchor_records() -> None:
    data = _base()
    # No anchor_records key
    status, summary, check = _anchor_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "missing_material"


def test_anchor_extension_empty_anchor_records() -> None:
    data = _base()
    data["anchor_records"] = []
    status, summary, check = _anchor_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "missing_material"


def test_anchor_extension_record_not_dict() -> None:
    data = _base()
    data["anchor_records"] = ["not a dict"]
    status, summary, check = _anchor_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "invalid_record_shape"


def test_anchor_extension_unsupported_anchor_type() -> None:
    data = _base()
    data["anchor_records"] = [{"anchor_type": "pkcs7"}]
    status, summary, check = _anchor_extension(data, requested=True)
    assert status == "unsupported"
    assert summary["reason"] == "unsupported_anchor_type"


def test_anchor_extension_missing_token() -> None:
    data = _base()
    data["anchor_records"] = [{"anchor_type": "rfc3161"}]  # no tsa_token_b64
    status, summary, check = _anchor_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "missing_token_or_digest"


def test_anchor_extension_missing_trust_roots() -> None:
    data = _base()
    data["anchor_records"] = [
        {"anchor_type": "rfc3161", "tsa_token_b64": "abc", "anchored_event_hash_hex": "aa" * 32}
    ]
    status, summary, check = _anchor_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "missing_trust_roots"


def test_anchor_extension_bad_token_b64() -> None:
    data = _base()
    data["anchor_records"] = [
        {
            "anchor_type": "rfc3161",
            "tsa_token_b64": "!!!invalid!!!",
            "anchored_event_hash_hex": "aa" * 32,
            "trust_roots_der_b64": [base64.standard_b64encode(b"cert").decode()],
        }
    ]
    status, summary, check = _anchor_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "token_base64_decode_failed"


def test_anchor_extension_bad_digest_hex() -> None:
    data = _base()
    data["anchor_records"] = [
        {
            "anchor_type": "rfc3161",
            "tsa_token_b64": base64.standard_b64encode(b"token").decode(),
            "anchored_event_hash_hex": "not-hex!",
            "trust_roots_der_b64": [base64.standard_b64encode(b"cert").decode()],
        }
    ]
    status, summary, check = _anchor_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "digest_not_hex"


def test_anchor_extension_trust_root_not_string() -> None:
    data = _base()
    data["anchor_records"] = [
        {
            "anchor_type": "rfc3161",
            "tsa_token_b64": base64.standard_b64encode(b"token").decode(),
            "anchored_event_hash_hex": "aa" * 32,
            "trust_roots_der_b64": [123],
        }
    ]
    status, summary, check = _anchor_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "invalid_trust_root_entry"


def test_anchor_extension_trust_root_bad_b64() -> None:
    data = _base()
    data["anchor_records"] = [
        {
            "anchor_type": "rfc3161",
            "tsa_token_b64": base64.standard_b64encode(b"token").decode(),
            "anchored_event_hash_hex": "aa" * 32,
            "trust_roots_der_b64": ["!!!invalid!!!"],
        }
    ]
    status, summary, check = _anchor_extension(data, requested=True)
    assert status == "invalid_input"
    assert summary["reason"] == "trust_root_decode_failed"


def test_anchor_extension_token_parse_failed() -> None:
    """Bad DER data → parse_timestamp_response raises AnchorVerificationError."""
    data = _base()
    data["anchor_records"] = [
        {
            "anchor_type": "rfc3161",
            "tsa_token_b64": base64.standard_b64encode(b"bad der data not a real token").decode(),
            "anchored_event_hash_hex": "aa" * 32,
            "trust_roots_der_b64": [base64.standard_b64encode(b"some cert der").decode()],
        }
    ]
    status, summary, check = _anchor_extension(data, requested=True)
    assert status == "failed"
    assert summary["reason"] == "token_parse_failed"


def test_anchor_extension_rfc3161_verify_failed(tmp_path: Path) -> None:
    """Wrong trust root → verify_timestamp_token raises → status='failed' (lines 740-748)."""
    pytest.importorskip("asn1crypto")
    from datetime import UTC, datetime

    from attestplane.anchoring.testing import TestTSAAuthority

    now = datetime.now(UTC)
    auth_a = TestTSAAuthority(now=now)
    auth_b = TestTSAAuthority(now=now, common_name="Other Authority")
    mat_a = auth_a.materials()
    mat_b = auth_b.materials()

    head_hex = _base()["hash_chain"]["head_hash_hex"]
    digest = bytes.fromhex(head_hex)
    token_der = auth_a.sign_timestamp_response(digest, gen_time=now, serial_number=1)

    data = _base()
    data["anchor_records"] = [
        {
            "anchor_type": "rfc3161",
            "tsa_token_b64": base64.standard_b64encode(token_der).decode(),
            "anchored_event_hash_hex": head_hex,
            "trust_roots_der_b64": [
                base64.standard_b64encode(mat_b.root_cert_der).decode()  # wrong root
            ],
        }
    ]
    status, summary, check = _anchor_extension(data, requested=True)
    assert status == "failed"
    assert summary["reason"] == "rfc3161_verify_failed"
    assert check is not None
    assert check.failure_kind == "verification_failed"


def test_anchor_extension_cert_chain_non_list_skipped(tmp_path: Path) -> None:
    """tsa_cert_chain_b64 is not a list → the chain loop is skipped (branch 725->733)."""
    pytest.importorskip("asn1crypto")
    from datetime import UTC, datetime

    from attestplane.anchoring.testing import TestTSAAuthority

    now = datetime.now(UTC)
    authority = TestTSAAuthority(now=now)
    materials = authority.materials()
    head_hex = _base()["hash_chain"]["head_hash_hex"]
    digest = bytes.fromhex(head_hex)
    token_der = authority.sign_timestamp_response(digest, gen_time=now, serial_number=5)

    data = _base()
    data["anchor_records"] = [
        {
            "anchor_type": "rfc3161",
            "tsa_token_b64": base64.standard_b64encode(token_der).decode(),
            "anchored_event_hash_hex": head_hex,
            "trust_roots_der_b64": [base64.standard_b64encode(materials.root_cert_der).decode()],
            "tsa_cert_chain_b64": "not_a_list",  # not a list → skipped
        }
    ]
    status, summary, check = _anchor_extension(data, requested=True)
    assert status == "passed"
    assert summary["verified_anchor_count"] == 1


def test_anchor_extension_cert_chain_only_leaf_no_intermediates(tmp_path: Path) -> None:
    """tsa_cert_chain_b64 with only the leaf (chain_b64s[1:] is empty) covers branch 728->727."""
    pytest.importorskip("asn1crypto")
    from datetime import UTC, datetime

    from attestplane.anchoring.testing import TestTSAAuthority

    now = datetime.now(UTC)
    authority = TestTSAAuthority(now=now)
    materials = authority.materials()
    head_hex = _base()["hash_chain"]["head_hash_hex"]
    digest = bytes.fromhex(head_hex)
    token_der = authority.sign_timestamp_response(digest, gen_time=now, serial_number=7)

    data = _base()
    data["anchor_records"] = [
        {
            "anchor_type": "rfc3161",
            "tsa_token_b64": base64.standard_b64encode(token_der).decode(),
            "anchored_event_hash_hex": head_hex,
            "trust_roots_der_b64": [base64.standard_b64encode(materials.root_cert_der).decode()],
            "tsa_cert_chain_b64": [
                base64.standard_b64encode(materials.leaf_cert_der).decode(),
                # only leaf → chain_b64s[1:] is empty, loop body never runs
            ],
        }
    ]
    status, summary, check = _anchor_extension(data, requested=True)
    assert status == "passed"
    assert summary["verified_anchor_count"] == 1


def test_anchor_extension_cert_chain_non_string_intermediate_skipped(tmp_path: Path) -> None:
    """Non-string entry in tsa_cert_chain_b64[1:] → isinstance(c_b64, str) is False (branch 728->727)."""
    pytest.importorskip("asn1crypto")
    from datetime import UTC, datetime

    from attestplane.anchoring.testing import TestTSAAuthority

    now = datetime.now(UTC)
    authority = TestTSAAuthority(now=now)
    materials = authority.materials()
    head_hex = _base()["hash_chain"]["head_hash_hex"]
    digest = bytes.fromhex(head_hex)
    token_der = authority.sign_timestamp_response(digest, gen_time=now, serial_number=8)

    data = _base()
    data["anchor_records"] = [
        {
            "anchor_type": "rfc3161",
            "tsa_token_b64": base64.standard_b64encode(token_der).decode(),
            "anchored_event_hash_hex": head_hex,
            "trust_roots_der_b64": [base64.standard_b64encode(materials.root_cert_der).decode()],
            "tsa_cert_chain_b64": [
                base64.standard_b64encode(materials.leaf_cert_der).decode(),
                123,  # non-string → isinstance check false, entry skipped
            ],
        }
    ]
    status, summary, check = _anchor_extension(data, requested=True)
    assert status == "passed"
    assert summary["verified_anchor_count"] == 1


def test_anchor_extension_cert_chain_malformed_intermediate_skipped(tmp_path: Path) -> None:
    """Malformed cert in tsa_cert_chain_b64[1:] is best-effort skipped, verify still runs."""
    pytest.importorskip("asn1crypto")
    from datetime import UTC, datetime

    from attestplane.anchoring.testing import TestTSAAuthority

    now = datetime.now(UTC)
    authority = TestTSAAuthority(now=now)
    materials = authority.materials()
    head_hex = _base()["hash_chain"]["head_hash_hex"]
    digest = bytes.fromhex(head_hex)
    token_der = authority.sign_timestamp_response(digest, gen_time=now, serial_number=99)

    data = _base()
    data["anchor_records"] = [
        {
            "anchor_type": "rfc3161",
            "tsa_token_b64": base64.standard_b64encode(token_der).decode(),
            "anchored_event_hash_hex": head_hex,
            "trust_roots_der_b64": [base64.standard_b64encode(materials.root_cert_der).decode()],
            "tsa_cert_chain_b64": [
                base64.standard_b64encode(materials.leaf_cert_der).decode(),
                "!!!bad_base64!!!",  # malformed intermediate → best-effort skipped
            ],
        }
    ]
    status, summary, check = _anchor_extension(data, requested=True)
    assert status == "passed"
    assert summary["reason"] == "rfc3161_tokens_verified"
    assert summary["verified_anchor_count"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# _alpha_error_code
# ═══════════════════════════════════════════════════════════════════════════════


def test_alpha_error_code_no_failures() -> None:
    assert _alpha_error_code([]) == VERIFY_OK


def test_alpha_error_code_required_fields() -> None:
    chk = AlphaCheck(name="required_fields", status="fail", failure_kind="invalid_input", detail="x")
    assert _alpha_error_code([chk]) == VERIFY_REQUIRED_FIELDS_MISSING


def test_alpha_error_code_signature_unsupported() -> None:
    chk = AlphaCheck(
        name="signature_verification",
        status="fail",
        failure_kind="invalid_input",
        detail="algorithm 'rsa-pss' is not in alpha allowlist — unsupported",
    )
    assert _alpha_error_code([chk]) == VERIFY_EXTENSION_UNSUPPORTED


def test_alpha_error_code_signature_invalid_input() -> None:
    chk = AlphaCheck(
        name="signature_verification",
        status="fail",
        failure_kind="invalid_input",
        detail="missing material",
    )
    assert _alpha_error_code([chk]) == VERIFY_EXTENSION_INVALID_INPUT


def test_alpha_error_code_anchor_unsupported() -> None:
    chk = AlphaCheck(
        name="anchor_verification",
        status="fail",
        failure_kind="invalid_input",
        detail="anchor_type(s) ['pkcs7'] not in alpha allowlist — unsupported",
    )
    assert _alpha_error_code([chk]) == VERIFY_EXTENSION_UNSUPPORTED


def test_alpha_error_code_anchor_invalid_input() -> None:
    chk = AlphaCheck(
        name="anchor_verification",
        status="fail",
        failure_kind="invalid_input",
        detail="missing trust roots",
    )
    assert _alpha_error_code([chk]) == VERIFY_EXTENSION_INVALID_INPUT


def test_alpha_error_code_schema_error() -> None:
    chk = AlphaCheck(
        name="schema_version",
        status="fail",
        failure_kind="invalid_input",
        detail="version unsupported",
    )
    assert _alpha_error_code([chk]) == VERIFY_SCHEMA_ERROR


def test_alpha_error_code_artifact_hash_failed() -> None:
    chk = AlphaCheck(
        name="artifact_hash",
        status="fail",
        failure_kind="verification_failed",
        detail="does not match",
    )
    assert _alpha_error_code([chk]) == VERIFY_ARTIFACT_HASH_FAILED


def test_alpha_error_code_hash_chain_recompute_failed() -> None:
    chk = AlphaCheck(
        name="hash_chain_recompute",
        status="fail",
        failure_kind="verification_failed",
        detail="chain broken",
    )
    assert _alpha_error_code([chk]) == VERIFY_CHAIN_RECOMPUTE_FAILED


def test_alpha_error_code_signature_verification_failed() -> None:
    chk = AlphaCheck(
        name="signature_verification",
        status="fail",
        failure_kind="verification_failed",
        detail="does not verify",
    )
    assert _alpha_error_code([chk]) == VERIFY_EXTENSION_FAILED


def test_alpha_error_code_anchor_verification_failed() -> None:
    chk = AlphaCheck(
        name="anchor_verification",
        status="fail",
        failure_kind="verification_failed",
        detail="rfc3161 failed",
    )
    assert _alpha_error_code([chk]) == VERIFY_EXTENSION_FAILED


def test_alpha_error_code_other_verification_failed() -> None:
    """verification_failed on an unexpected name → VERIFY_CHAIN_RECOMPUTE_FAILED."""
    chk = AlphaCheck(
        name="some_other_check",
        status="fail",
        failure_kind="verification_failed",
        detail="bad",
    )
    assert _alpha_error_code([chk]) == VERIFY_CHAIN_RECOMPUTE_FAILED


# ═══════════════════════════════════════════════════════════════════════════════
# verify_alpha_proofbundle_file — integration paths
# ═══════════════════════════════════════════════════════════════════════════════


def test_verify_file_missing(tmp_path: Path) -> None:
    report = verify_alpha_proofbundle_file(tmp_path / "nonexistent.json")
    assert report["ok"] is False
    assert report["exit_code"] == 2
    assert any(c["name"] == "json_read" for c in report["checks"])


def test_verify_file_malformed_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{ invalid json", encoding="utf-8")
    report = verify_alpha_proofbundle_file(bad)
    assert report["ok"] is False
    assert report["exit_code"] == 2
    assert any(c["name"] == "json_parse" for c in report["checks"])


def test_verify_file_root_not_object(tmp_path: Path) -> None:
    p = tmp_path / "list.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    report = verify_alpha_proofbundle_file(p)
    assert report["ok"] is False
    assert report["exit_code"] == 2
    assert any(c["name"] == "root_object" for c in report["checks"])


def test_verify_file_root_not_object_with_verify_signature(tmp_path: Path) -> None:
    """Root-not-object + verify_signature=True → signature_status=invalid_input."""
    p = tmp_path / "list.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    report = verify_alpha_proofbundle_file(p, verify_signature=True)
    assert report["signature_verification_status"] == "invalid_input"
    assert report["signature_verification_summary"]["reason"] == "root_not_object"


def test_verify_file_root_not_object_with_verify_anchor(tmp_path: Path) -> None:
    """Root-not-object + verify_anchor=True → anchor_status=invalid_input."""
    p = tmp_path / "list.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    report = verify_alpha_proofbundle_file(p, verify_anchor=True)
    assert report["anchor_verification_status"] == "invalid_input"
    assert report["anchor_verification_summary"]["reason"] == "root_not_object"


def test_verify_file_parse_fail_with_verify_signature(tmp_path: Path) -> None:
    """Parse fail + verify_signature=True → signature_status=invalid_input."""
    bad = tmp_path / "bad.json"
    bad.write_text("{bad", encoding="utf-8")
    report = verify_alpha_proofbundle_file(bad, verify_signature=True)
    assert report["signature_verification_status"] == "invalid_input"
    assert report["signature_verification_summary"]["reason"] == "input_unparsable"


def test_verify_file_parse_fail_with_verify_anchor(tmp_path: Path) -> None:
    """Parse fail + verify_anchor=True → anchor_status=invalid_input."""
    bad = tmp_path / "bad.json"
    bad.write_text("{bad", encoding="utf-8")
    report = verify_alpha_proofbundle_file(bad, verify_anchor=True)
    assert report["anchor_verification_status"] == "invalid_input"
    assert report["anchor_verification_summary"]["reason"] == "input_unparsable"


def test_verify_file_valid(tmp_path: Path) -> None:
    report = verify_alpha_proofbundle_file(VALID_MINIMAL)
    assert report["ok"] is True
    assert report["exit_code"] == 0
    assert report["signature_verification_status"] == "skipped"
    assert report["anchor_verification_status"] == "skipped"


def test_verify_file_missing_required_field(tmp_path: Path) -> None:
    data = _base()
    del data["provenance"]
    p = _write(tmp_path, data)
    report = verify_alpha_proofbundle_file(p)
    assert report["ok"] is False
    assert report["exit_code"] == 2
    failed = [c for c in report["checks"] if c["status"] == "fail"]
    assert failed[0]["name"] == "required_fields"


def test_verify_file_proof_bundle_not_dict(tmp_path: Path) -> None:
    data = _base()
    data["proof_bundle"] = "not a dict"
    # Need to recompute artifact.sha256 for the new proof_bundle
    data["artifact"]["sha256"] = hashlib.sha256(canonicalize("not a dict")).hexdigest()
    p = _write(tmp_path, data)
    report = verify_alpha_proofbundle_file(p)
    assert report["ok"] is False
    assert any(c["name"] == "proof_bundle_shape" for c in report["checks"])


def test_verify_file_signature_extension_called(tmp_path: Path) -> None:
    """verify_signature=True with valid bundle but empty signatures → invalid_input."""
    # valid_minimal has signatures=[] so requesting verify_signature → missing_material
    report = verify_alpha_proofbundle_file(VALID_MINIMAL, verify_signature=True)
    assert report["signature_verification_status"] == "invalid_input"
    assert report["signature_verification_summary"]["reason"] == "missing_material"
    assert report["exit_code"] == 2


def test_verify_file_anchor_extension_called(tmp_path: Path) -> None:
    """verify_anchor=True with valid bundle but no anchor_records → invalid_input."""
    report = verify_alpha_proofbundle_file(VALID_MINIMAL, verify_anchor=True)
    assert report["anchor_verification_status"] == "invalid_input"
    assert report["anchor_verification_summary"]["reason"] == "missing_material"
    assert report["exit_code"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# AlphaCheck.as_json
# ═══════════════════════════════════════════════════════════════════════════════


def test_alpha_check_as_json_pass_no_detail() -> None:
    chk = AlphaCheck(name="foo", status="pass")
    j = chk.as_json()
    assert j == {"name": "foo", "status": "pass"}
    assert "failure_kind" not in j
    assert "detail" not in j


def test_alpha_check_as_json_fail_with_detail() -> None:
    chk = AlphaCheck(name="bar", status="fail", failure_kind="invalid_input", detail="bad value")
    j = chk.as_json()
    assert j["failure_kind"] == "invalid_input"
    assert j["detail"] == "bad value"


# ═══════════════════════════════════════════════════════════════════════════════
# _report — exit_code logic
# ═══════════════════════════════════════════════════════════════════════════════


def test_report_exit_code_zero_when_all_pass() -> None:
    checks = [AlphaCheck(name="foo", status="pass")]
    r = _report(Path("/fake"), checks)
    assert r["exit_code"] == 0
    assert r["ok"] is True


def test_report_exit_code_one_verification_failed() -> None:
    checks = [
        AlphaCheck(name="artifact_hash", status="fail", failure_kind="verification_failed", detail="x")
    ]
    r = _report(Path("/fake"), checks)
    assert r["exit_code"] == 1
    assert r["ok"] is False


def test_report_exit_code_two_invalid_input() -> None:
    checks = [
        AlphaCheck(name="schema_version", status="fail", failure_kind="invalid_input", detail="x")
    ]
    r = _report(Path("/fake"), checks)
    assert r["exit_code"] == 2
    assert r["ok"] is False


def test_report_signature_performed_reflected() -> None:
    checks: list[AlphaCheck] = []
    r = _report(
        Path("/fake"),
        checks,
        verify_signature=True,
        signature_status="passed",
        signature_summary={"performed": True},
    )
    assert r["signature_verification_performed"] is True
    assert r["signature_verification_claims"]["cryptographic_verification_performed"] is True


def test_report_anchor_performed_reflected() -> None:
    checks: list[AlphaCheck] = []
    r = _report(
        Path("/fake"),
        checks,
        verify_anchor=True,
        anchor_status="passed",
        anchor_summary={"performed": True},
    )
    assert r["anchor_verification_performed"] is True
    assert r["anchor_verification_claims"]["anchor_verification_performed"] is True
