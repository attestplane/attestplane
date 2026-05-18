# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the wire-format schemas under schemas/v1/.

These tests pin the schemas at the JSON Schema validity level and at
the field-level contract level. Adding new optional fields is allowed
without modifying these tests; renaming or removing required fields
will fail one of the assertions below.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

_SCHEMAS_DIR = Path(__file__).resolve().parents[3] / "schemas" / "v1"


def _load(name: str) -> dict[str, Any]:
    return json.loads((_SCHEMAS_DIR / name).read_text(encoding="utf-8"))


def test_schemas_dir_exists() -> None:
    assert _SCHEMAS_DIR.is_dir()


@pytest.mark.parametrize("schema_file", [
    "proof_bundle.schema.json",
    "auditor_export.schema.json",
    "governance_ingestion.schema.json",
])
def test_schema_is_valid_draft_2020_12(schema_file: str) -> None:
    schema = _load(schema_file)
    # jsonschema's check_schema raises on malformed schemas.
    jsonschema.Draft202012Validator.check_schema(schema)


def test_proof_bundle_minimum_valid_instance() -> None:
    schema = _load("proof_bundle.schema.json")
    instance = {
        "bundle_version": 1,
        "chain_metadata": {
            "chain_id": "demo-chain",
            "schema_version": 1,
            "genesis_hash_hex": "0" * 64,
            "head_hash_hex": "a" * 64,
            "head_seq": -1,
            "producer_runtime": "test-runtime",
        },
        "events": [],
        "verification_report": {
            "ok": True,
            "first_bad_index": None,
            "reason": None,
            "verified_at": "2026-05-17T12:00:00.000000Z",
            "verifier_version": "0.1.0",
            "verification_method": "canonical-bytes-walk",
        },
        "forbidden_fields": ["secrets", "tokens", "pii"],
    }
    jsonschema.validate(instance, schema)


def test_proof_bundle_rejects_unknown_top_level_field() -> None:
    schema = _load("proof_bundle.schema.json")
    instance = {
        "bundle_version": 1,
        "chain_metadata": {
            "chain_id": "demo",
            "schema_version": 1,
            "genesis_hash_hex": "0" * 64,
            "head_hash_hex": "a" * 64,
            "head_seq": -1,
            "producer_runtime": "test-runtime",
        },
        "events": [],
        "verification_report": {
            "ok": True,
            "first_bad_index": None,
            "reason": None,
            "verified_at": "2026-05-17T12:00:00.000000Z",
            "verifier_version": "0.1.0",
            "verification_method": "canonical-bytes-walk",
        },
        "forbidden_fields": ["secrets"],
        "definitely_not_in_v1": True,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


def test_proof_bundle_rejects_wrong_bundle_version() -> None:
    schema = _load("proof_bundle.schema.json")
    instance = {
        "bundle_version": 99,
        "chain_metadata": {
            "chain_id": "demo",
            "schema_version": 1,
            "genesis_hash_hex": "0" * 64,
            "head_hash_hex": "a" * 64,
            "head_seq": -1,
            "producer_runtime": "test-runtime",
        },
        "events": [],
        "verification_report": {
            "ok": True,
            "first_bad_index": None,
            "reason": None,
            "verified_at": "2026-05-17T12:00:00.000000Z",
            "verifier_version": "0.1.0",
            "verification_method": "canonical-bytes-walk",
        },
        "forbidden_fields": ["secrets"],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


def test_proof_bundle_rejects_invalid_event_type_pattern() -> None:
    schema = _load("proof_bundle.schema.json")
    instance = {
        "bundle_version": 1,
        "chain_metadata": {
            "chain_id": "demo",
            "schema_version": 1,
            "genesis_hash_hex": "0" * 64,
            "head_hash_hex": "a" * 64,
            "head_seq": 0,
            "producer_runtime": "test-runtime",
        },
        "events": [
            {
                "seq": 0,
                "prev_hash_hex": "0" * 64,
                "event_hash_hex": "a" * 64,
                "event": {
                    "schema_version": 1,
                    "event_id": "00000000-0000-7000-8000-000000000001",
                    "timestamp": "2026-05-17T12:00:00.000000Z",
                    "event_type": "NotAValidPattern",
                    "actor": "agent://test/v1",
                    "payload": {},
                    "subject_ref": None,
                    "session_id": None,
                    "reference_db_ref": None,
                    "matched_input_ref": None,
                    "human_verifier": None,
                },
            }
        ],
        "verification_report": {
            "ok": True,
            "first_bad_index": None,
            "reason": None,
            "verified_at": "2026-05-17T12:00:00.000000Z",
            "verifier_version": "0.1.0",
            "verification_method": "canonical-bytes-walk",
        },
        "forbidden_fields": ["secrets"],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


def test_auditor_export_minimum_valid_instance() -> None:
    schema = _load("auditor_export.schema.json")
    instance = {
        "export_version": 1,
        "chain_summary": {
            "chain_id": "demo",
            "head_hash_hex": "a" * 64,
            "event_count": 0,
            "time_range": {
                "earliest": "2026-05-17T12:00:00.000000Z",
                "latest": "2026-05-17T12:00:00.000000Z",
            },
            "producer_runtime": "test-runtime",
        },
        "verification_status": {
            "ok": True,
            "verified_at": "2026-05-17T12:00:00.000000Z",
            "verifier_version": "0.1.0",
            "verification_method": "canonical-bytes-walk",
        },
        "framework_coverage": [],
        "redaction_policy": {
            "forbidden_fields": ["secrets"],
            "redaction_status": "enforced_by_adapter",
        },
    }
    jsonschema.validate(instance, schema)


def test_auditor_export_redaction_status_enum() -> None:
    schema = _load("auditor_export.schema.json")
    instance = {
        "export_version": 1,
        "chain_summary": {
            "chain_id": "demo",
            "head_hash_hex": "a" * 64,
            "event_count": 0,
            "time_range": {
                "earliest": "2026-05-17T12:00:00.000000Z",
                "latest": "2026-05-17T12:00:00.000000Z",
            },
            "producer_runtime": "test-runtime",
        },
        "verification_status": {
            "ok": True,
            "verified_at": "2026-05-17T12:00:00.000000Z",
            "verifier_version": "0.1.0",
            "verification_method": "canonical-bytes-walk",
        },
        "framework_coverage": [],
        "redaction_policy": {
            "forbidden_fields": ["secrets"],
            "redaction_status": "not_in_enum",
        },
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


def test_default_forbidden_fields_includes_critical_terms() -> None:
    """The proof_bundle schema's default forbidden_fields list seeds the
    redaction floor; critical terms MUST be present."""
    schema = _load("proof_bundle.schema.json")
    defaults = schema["properties"]["forbidden_fields"]["default"]
    must_include = {"secrets", "tokens", "jwts", "private_keys",
                    "pii", "raw_audit_payloads"}
    assert must_include.issubset(set(defaults))


def test_obligation_id_pattern_matches_registry_entries() -> None:
    """The framework_mappings obligation_id pattern must accept real entries."""
    from attestplane.obligations import load_all_registries

    schema = _load("proof_bundle.schema.json")
    pattern = (
        schema["properties"]["framework_mappings"]["items"]["properties"]
        ["obligation_id"]["pattern"]
    )
    import re
    compiled = re.compile(pattern)
    for registry in load_all_registries():
        for entry in registry.entries:
            assert compiled.match(entry.obligation_id), entry.obligation_id


def test_implementation_status_enum_matches_registry() -> None:
    """The framework_mappings implementation_status_at_bundle_time enum must
    match the locked four-value set used by the obligation registry."""
    schema = _load("proof_bundle.schema.json")
    enum_values = set(
        schema["properties"]["framework_mappings"]["items"]["properties"]
        ["implementation_status_at_bundle_time"]["enum"]
    )
    assert enum_values == {
        "mapping_target", "designed_toward",
        "field_supported", "verified_in_test",
    }


def test_governance_ingestion_minimum_valid_instance() -> None:
    schema = _load("governance_ingestion.schema.json")
    instance = {
        "ingestion_version": 1,
        "chain_summary": {
            "chain_id": "demo",
            "head_hash_hex": "a" * 64,
            "event_count": 0,
            "time_range": {
                "earliest": "2026-05-17T12:00:00.000000Z",
                "latest": "2026-05-17T12:00:00.000000Z",
            },
        },
        "verification_status": {
            "ok": True,
            "verified_at": "2026-05-17T12:00:00.000000Z",
            "verifier_version": "0.0.3a0",
            "verification_method": "canonical-bytes-walk",
        },
        "framework_coverage": [],
        "redaction_policy": {
            "forbidden_fields": ["secrets"],
            "redaction_status": "enforced_by_adapter",
        },
    }
    jsonschema.validate(instance, schema)


def test_governance_ingestion_rejects_wrong_version() -> None:
    schema = _load("governance_ingestion.schema.json")
    instance = {
        "ingestion_version": 99,
        "chain_summary": {
            "chain_id": "demo",
            "head_hash_hex": "a" * 64,
            "event_count": 0,
            "time_range": {
                "earliest": "2026-05-17T12:00:00.000000Z",
                "latest": "2026-05-17T12:00:00.000000Z",
            },
        },
        "verification_status": {
            "ok": True,
            "verified_at": "2026-05-17T12:00:00.000000Z",
            "verifier_version": "0.0.3a0",
            "verification_method": "canonical-bytes-walk",
        },
        "framework_coverage": [],
        "redaction_policy": {
            "forbidden_fields": ["secrets"],
            "redaction_status": "enforced_by_adapter",
        },
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


def test_governance_ingestion_implementation_status_enum_locked() -> None:
    schema = _load("governance_ingestion.schema.json")
    enum_values = set(
        schema["properties"]["framework_coverage"]["items"]["properties"]
        ["obligation_ids_with_evidence"]["items"]["properties"]
        ["implementation_status"]["enum"]
    )
    assert enum_values == {
        "mapping_target", "designed_toward",
        "field_supported", "verified_in_test",
    }


def test_governance_ingestion_with_framework_coverage() -> None:
    schema = _load("governance_ingestion.schema.json")
    instance = {
        "ingestion_version": 1,
        "chain_summary": {
            "chain_id": "demo",
            "head_hash_hex": "a" * 64,
            "event_count": 3,
            "time_range": {
                "earliest": "2026-05-17T12:00:00.000000Z",
                "latest": "2026-05-17T13:00:00.000000Z",
            },
        },
        "verification_status": {
            "ok": True,
            "verified_at": "2026-05-17T13:00:00.000000Z",
            "verifier_version": "0.0.3a0",
            "verification_method": "canonical-bytes-walk",
        },
        "framework_coverage": [
            {
                "framework": "EU AI Act",
                "article": "12",
                "obligation_ids_with_evidence": [
                    {
                        "obligation_id": "eu_ai_act.art12.3c.matched_input_data",
                        "implementation_status": "field_supported",
                        "evidence_event_indexes": [0, 2],
                    },
                ],
                "obligation_ids_without_evidence": [
                    "eu_ai_act.art12.1.automatic_recording",
                ],
            },
        ],
        "redaction_policy": {
            "forbidden_fields": ["secrets"],
            "redaction_status": "enforced_by_adapter",
        },
    }
    jsonschema.validate(instance, schema)


def test_governance_ingestion_rejects_bad_implementation_status() -> None:
    schema = _load("governance_ingestion.schema.json")
    instance = {
        "ingestion_version": 1,
        "chain_summary": {
            "chain_id": "demo",
            "head_hash_hex": "a" * 64,
            "event_count": 0,
            "time_range": {
                "earliest": "2026-05-17T12:00:00.000000Z",
                "latest": "2026-05-17T12:00:00.000000Z",
            },
        },
        "verification_status": {
            "ok": True,
            "verified_at": "2026-05-17T12:00:00.000000Z",
            "verifier_version": "0.0.3a0",
            "verification_method": "canonical-bytes-walk",
        },
        "framework_coverage": [
            {
                "framework": "EU AI Act",
                "article": "12",
                "obligation_ids_with_evidence": [
                    {
                        "obligation_id": "eu_ai_act.art12.3c.matched_input_data",
                        "implementation_status": "compliant",  # forbidden
                    },
                ],
                "obligation_ids_without_evidence": [],
            },
        ],
        "redaction_policy": {
            "forbidden_fields": ["secrets"],
            "redaction_status": "enforced_by_adapter",
        },
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)
