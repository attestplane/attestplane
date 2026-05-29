# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for :mod:`attestplane.proof_bundle` and :mod:`attestplane.verifier`."""

from __future__ import annotations

import json
from base64 import standard_b64encode
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pytest

from attestplane.hashchain import chain_extend, genesis_head, hash_event
from attestplane.obligations import load_eu_ai_act_article_12
from attestplane.proof_bundle import (
    DEFAULT_FORBIDDEN_FIELDS,
    FrameworkMapping,
    ProofBundleBuilder,
    build_auditor_export,
)
from attestplane.types import ChainedEvent, ChainHead, EventDraft
from attestplane.verifier import (
    BundleSchemaError,
    BundleVerificationError,
    verify_proof_bundle,
    verify_proof_bundle_file,
)
from attestplane.verify_errors import VERIFY_BUNDLE_SCHEMA_INCOMPLETE

_SCHEMAS_DIR = Path(__file__).resolve().parents[3] / "schemas" / "v1"


def _proof_bundle_schema() -> dict[str, object]:
    return json.loads((_SCHEMAS_DIR / "proof_bundle.schema.json").read_text(encoding="utf-8"))


def _auditor_export_schema() -> dict[str, object]:
    return json.loads((_SCHEMAS_DIR / "auditor_export.schema.json").read_text(encoding="utf-8"))


def _build_good_chain(n: int) -> list[ChainedEvent]:
    ts = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    chain: list[ChainedEvent] = []
    head = genesis_head()
    for i in range(n):
        draft = EventDraft(
            event_type=("eval_event" if i % 2 == 0 else "policy_check_event"),
            actor=f"agent://test/{i}",
            payload={"index": i},
            session_id=f"sess-{i}",
        )
        event = chain_extend(
            head,
            draft,
            now=ts,
            event_id=f"00000000-0000-7000-8000-{i:012d}",
        )
        chain.append(event)
        head = ChainHead(seq=event.seq, event_hash=event.event_hash)
    return chain


def _syntactic_signature_for(event: ChainedEvent) -> dict[str, object]:
    return {
        "signature_schema_version": 1,
        "signed_seq": event.seq,
        "signed_event_hash_hex": hash_event(event.event).hex(),
        "signature_hex": "a" * 128,
        "key_id": "b" * 32,
        "public_key_der_b64": standard_b64encode(b"public-key").decode("ascii"),
        "signing_cert_chain_b64": [
            standard_b64encode(b"cert").decode("ascii"),
        ],
        "signed_at": "2026-05-17T12:00:00Z",
        "signature_mode": "per_event",
        "signed_payload_b64": standard_b64encode(b"payload").decode("ascii"),
    }


def _build_signed_schema_bundle() -> dict[str, object]:
    chain = _build_good_chain(1)
    builder = ProofBundleBuilder(chain_id="signed-schema", producer_runtime="test")
    builder.extend(chain)
    bundle = builder.build()
    bundle["signatures"] = [_syntactic_signature_for(chain[0])]
    return bundle


def test_build_empty_bundle() -> None:
    builder = ProofBundleBuilder(chain_id="empty", producer_runtime="test")
    bundle = builder.build()

    assert bundle["bundle_version"] == 1
    assert bundle["events"] == []
    assert bundle["verification_report"]["ok"] is True
    assert bundle["chain_metadata"]["head_seq"] == -1
    assert bundle["chain_metadata"]["head_hash_hex"] == "0" * 64


def test_verify_proof_bundle_can_require_non_empty_events() -> None:
    builder = ProofBundleBuilder(chain_id="empty", producer_runtime="test")
    bundle = builder.build()

    default_result = verify_proof_bundle(bundle)
    strict_result = verify_proof_bundle(bundle, require_non_empty=True)

    assert default_result.ok is True
    assert strict_result.ok is False
    assert strict_result.event_count == 0
    assert strict_result.error_code == "VERIFY_REQUIRED_FIELDS_MISSING"
    assert "at least one event" in (strict_result.metadata_reason or "")


def test_build_bundle_with_chain() -> None:
    builder = ProofBundleBuilder(chain_id="my-chain", producer_runtime="test-runtime v1.0")
    builder.extend(_build_good_chain(3))
    bundle = builder.build()

    assert len(bundle["events"]) == 3
    assert bundle["verification_report"]["ok"] is True
    assert bundle["chain_metadata"]["head_seq"] == 2


def test_bundle_validates_against_proof_bundle_schema() -> None:
    builder = ProofBundleBuilder(chain_id="schema-check", producer_runtime="test")
    builder.extend(_build_good_chain(2))
    bundle = builder.build()
    jsonschema.validate(bundle, _proof_bundle_schema())


def test_bundle_with_framework_mapping_validates() -> None:
    builder = ProofBundleBuilder(chain_id="fm", producer_runtime="test")
    builder.extend(_build_good_chain(2))
    builder.add_framework_mapping(
        FrameworkMapping(
            obligation_id="eu_ai_act.art12.3c.matched_input_data",
            evidence_event_indexes=(0,),
            implementation_status_at_bundle_time="field_supported",
        )
    )
    bundle = builder.build()
    jsonschema.validate(bundle, _proof_bundle_schema())
    assert bundle["framework_mappings"][0]["obligation_id"].startswith("eu_ai_act.")


def test_framework_mapping_with_bad_index_rejected() -> None:
    builder = ProofBundleBuilder(chain_id="fm", producer_runtime="test")
    builder.extend(_build_good_chain(2))
    with pytest.raises(ValueError, match="references event index"):
        builder.add_framework_mapping(
            FrameworkMapping(
                obligation_id="eu_ai_act.art12.1.automatic_recording",
                evidence_event_indexes=(99,),
                implementation_status_at_bundle_time="designed_toward",
            )
        )


def test_default_forbidden_fields_present() -> None:
    builder = ProofBundleBuilder(chain_id="x", producer_runtime="test")
    bundle = builder.build()
    assert set(bundle["forbidden_fields"]) == set(DEFAULT_FORBIDDEN_FIELDS)
    for term in ["secrets", "tokens", "jwts", "private_keys", "pii"]:
        assert term in bundle["forbidden_fields"]


def test_verify_proof_bundle_accepts_good_bundle() -> None:
    builder = ProofBundleBuilder(chain_id="v", producer_runtime="test")
    builder.extend(_build_good_chain(3))
    bundle = builder.build()

    result = verify_proof_bundle(bundle)
    assert result.ok is True
    assert result.event_count == 3
    assert result.agreement is True
    assert result.chain_result.ok is True
    assert result.metadata_ok is True
    assert result.policy_trace_refs_ok is True


def test_verify_proof_bundle_accepts_minimum_signed_attestation_schema() -> None:
    result = verify_proof_bundle(
        _build_signed_schema_bundle(),
        require_signed_attestation=True,
    )

    assert result.ok is True
    assert result.signed_attestation_schema_ok is True
    assert result.signed_attestation_schema_reason is None


def test_verify_proof_bundle_require_non_empty_enforces_signature_schema() -> None:
    builder = ProofBundleBuilder(chain_id="unsigned", producer_runtime="test")
    builder.extend(_build_good_chain(1))
    result = verify_proof_bundle(builder.build(), require_non_empty=True)

    assert result.ok is False
    assert result.error_code == VERIFY_BUNDLE_SCHEMA_INCOMPLETE
    assert "signatures" in (result.signed_attestation_schema_reason or "")


@pytest.mark.parametrize(
    ("mutate", "expected_reason"),
    [
        (lambda sig: sig.clear(), "lowercase 64-hex"),
        (lambda sig: sig.update({"signature_schema_version": 0}), "positive integer"),
        (lambda sig: sig.update({"signed_seq": -1}), "non-negative integer"),
        (lambda sig: sig.update({"signed_event_hash_hex": "f" * 64}), "canonical bundle event"),
        (lambda sig: sig.update({"signed_event_hash_hex": "BAD"}), "lowercase 64-hex"),
        (lambda sig: sig.update({"signature_hex": "a"}), "signature_hex"),
        (lambda sig: sig.update({"key_id": "b"}), "key_id"),
        (lambda sig: sig.update({"signature_mode": "detached"}), "signature_mode"),
        (lambda sig: sig.update({"public_key_der_b64": "not base64"}), "public_key_der_b64"),
        (lambda sig: sig.update({"signed_payload_b64": ["not", "text"]}), "signed_payload_b64"),
        (lambda sig: sig.update({"signing_cert_chain_b64": "not-list"}), "signing_cert_chain_b64"),
        (lambda sig: sig.update({"signing_cert_chain_b64": [7]}), "signing_cert_chain_b64[0]"),
        (lambda sig: sig.update({"signing_cert_chain_b64": ["not base64"]}), "must be base64"),
        (lambda sig: sig.update({"signed_at": 7}), "signed_at must be a string"),
        (lambda sig: sig.update({"signed_at": "not-a-date"}), "signed_at must be RFC3339"),
    ],
)
def test_verify_proof_bundle_rejects_malformed_signature_schema(
    mutate: Callable[[dict[str, object]], None],
    expected_reason: str,
) -> None:
    bundle = _build_signed_schema_bundle()
    signature = dict(bundle["signatures"][0])  # type: ignore[index]
    mutate(signature)
    bundle["signatures"] = [signature]

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is False
    assert result.signed_attestation_schema_ok is False
    assert expected_reason in (result.signed_attestation_schema_reason or "")


def test_verify_proof_bundle_skips_bad_signature_when_later_record_is_usable() -> None:
    bundle = _build_signed_schema_bundle()
    good_signature = dict(bundle["signatures"][0])  # type: ignore[index]
    bundle["signatures"] = ["not-an-object", good_signature]

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is True
    assert result.signed_attestation_schema_ok is True


def test_verify_proof_bundle_is_read_only() -> None:
    builder = ProofBundleBuilder(chain_id="readonly", producer_runtime="test")
    builder.extend(_build_good_chain(3))
    bundle = builder.build()
    before = deepcopy(bundle)
    result = verify_proof_bundle(bundle)
    assert result.ok is True
    assert bundle == before


def test_verify_proof_bundle_rejects_unknown_top_level_metadata() -> None:
    builder = ProofBundleBuilder(chain_id="unknown", producer_runtime="test")
    bundle = builder.build()
    bundle["proof_type"] = "critical-unknown"
    with pytest.raises(BundleSchemaError, match="unknown top-level"):
        verify_proof_bundle(bundle)


def test_verify_proof_bundle_detects_head_metadata_mismatch() -> None:
    builder = ProofBundleBuilder(chain_id="head", producer_runtime="test")
    builder.extend(_build_good_chain(2))
    bundle = builder.build()
    bundle["chain_metadata"]["head_hash_hex"] = "f" * 64
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert result.metadata_ok is False
    assert "head_hash_hex" in (result.metadata_reason or "")


def test_verify_proof_bundle_detects_report_reason_mismatch() -> None:
    builder = ProofBundleBuilder(chain_id="report", producer_runtime="test")
    builder.extend(_build_good_chain(2))
    bundle = builder.build()
    bundle["verification_report"]["reason"] = "forged"
    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert result.metadata_ok is False
    assert "reason disagrees" in (result.metadata_reason or "")


def test_verify_proof_bundle_rejects_bad_bundle_version() -> None:
    builder = ProofBundleBuilder(chain_id="v", producer_runtime="test")
    bundle = builder.build()
    bundle["bundle_version"] = 99
    with pytest.raises(BundleSchemaError, match="bundle_version"):
        verify_proof_bundle(bundle)


def test_verify_proof_bundle_rejects_missing_field() -> None:
    bundle: dict[str, object] = {"bundle_version": 1}
    with pytest.raises(BundleSchemaError, match="missing required fields"):
        verify_proof_bundle(bundle)


def test_verify_proof_bundle_detects_tampered_chain() -> None:
    builder = ProofBundleBuilder(chain_id="t", producer_runtime="test")
    builder.extend(_build_good_chain(3))
    bundle = builder.build()
    # Tamper: mutate the second event's payload but leave hashes.
    bundle["events"][1]["event"]["payload"] = {"index": 999}

    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert result.chain_result.ok is False
    assert result.chain_result.first_bad_index == 1
    assert result.metadata_ok is False


def test_verify_proof_bundle_disagreement_flag() -> None:
    """Bundle says ok=True but chain actually broken -> agreement=False."""
    builder = ProofBundleBuilder(chain_id="d", producer_runtime="test")
    builder.extend(_build_good_chain(3))
    bundle = builder.build()
    bundle["events"][1]["event"]["payload"] = {"index": 999}
    # Keep the embedded report at ok=True (the producer was honest at build
    # time but the bundle was mutated after build) — simulating tampering
    # between generation and reading.

    result = verify_proof_bundle(bundle)
    assert result.ok is False
    assert result.bundle_reported_ok is True
    assert result.chain_result.ok is False
    assert result.agreement is False


def test_verify_proof_bundle_file_round_trips(tmp_path: Path) -> None:
    builder = ProofBundleBuilder(chain_id="f", producer_runtime="test")
    builder.extend(_build_good_chain(2))
    bundle = builder.build()
    out = tmp_path / "bundle.json"
    out.write_text(json.dumps(bundle), encoding="utf-8")

    result = verify_proof_bundle_file(out)
    assert result.ok is True
    assert result.event_count == 2


def test_verify_proof_bundle_file_can_require_non_empty_events(tmp_path: Path) -> None:
    builder = ProofBundleBuilder(chain_id="empty-file", producer_runtime="test")
    bundle = builder.build()
    out = tmp_path / "empty.json"
    out.write_text(json.dumps(bundle), encoding="utf-8")

    result = verify_proof_bundle_file(out, require_non_empty=True)

    assert result.ok is False
    assert result.error_code == "VERIFY_REQUIRED_FIELDS_MISSING"


def test_verify_proof_bundle_file_missing_path(tmp_path: Path) -> None:
    with pytest.raises(BundleVerificationError, match="not found"):
        verify_proof_bundle_file(tmp_path / "nope.json")


def test_verify_proof_bundle_file_malformed_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("this is not json", encoding="utf-8")
    with pytest.raises(BundleSchemaError, match="not valid JSON"):
        verify_proof_bundle_file(bad)


def test_short_summary_format_ok() -> None:
    builder = ProofBundleBuilder(chain_id="my-id", producer_runtime="test")
    builder.extend(_build_good_chain(2))
    bundle = builder.build()
    summary = verify_proof_bundle(bundle).short_summary()
    assert summary.startswith("OK")
    assert "'my-id'" in summary


def test_short_summary_format_fail() -> None:
    builder = ProofBundleBuilder(chain_id="bad-id", producer_runtime="test")
    builder.extend(_build_good_chain(2))
    bundle = builder.build()
    bundle["events"][1]["event"]["payload"] = {"changed": True}
    summary = verify_proof_bundle(bundle).short_summary()
    assert summary.startswith("FAIL")


def test_build_auditor_export_minimal() -> None:
    builder = ProofBundleBuilder(chain_id="ax", producer_runtime="test")
    builder.extend(_build_good_chain(3))
    bundle = builder.build()

    export = build_auditor_export(bundle)

    assert export["export_version"] == 1
    assert export["chain_summary"]["event_count"] == 3
    assert export["verification_status"]["ok"] is True
    assert export["redaction_policy"]["redaction_status"] == "enforced_by_producer"


def test_auditor_export_validates_against_schema() -> None:
    builder = ProofBundleBuilder(chain_id="ax-schema", producer_runtime="test")
    builder.extend(_build_good_chain(2))
    bundle = builder.build()
    export = build_auditor_export(bundle)
    jsonschema.validate(export, _auditor_export_schema())


def test_auditor_export_with_framework_coverage() -> None:
    builder = ProofBundleBuilder(chain_id="ax-fm", producer_runtime="test")
    builder.extend(_build_good_chain(3))
    builder.add_framework_mapping(
        FrameworkMapping(
            obligation_id="eu_ai_act.art12.3c.matched_input_data",
            evidence_event_indexes=(0,),
            implementation_status_at_bundle_time="field_supported",
        )
    )
    bundle = builder.build()

    export = build_auditor_export(
        bundle,
        framework_coverage_registries=[load_eu_ai_act_article_12()],
    )
    jsonschema.validate(export, _auditor_export_schema())

    rows = export["framework_coverage"]
    assert len(rows) >= 1
    # The covered obligation appears in exactly one row's with_evidence list.
    with_set: set[str] = set()
    without_set: set[str] = set()
    for row in rows:
        with_set.update(row["obligation_ids_with_evidence"])
        without_set.update(row["obligation_ids_without_evidence"])
    assert "eu_ai_act.art12.3c.matched_input_data" in with_set
    assert "eu_ai_act.art12.3c.matched_input_data" not in without_set
    # Other registry entries surface as without_evidence.
    assert len(without_set) >= 1


def test_auditor_export_event_type_histogram() -> None:
    builder = ProofBundleBuilder(chain_id="hist", producer_runtime="test")
    builder.extend(_build_good_chain(4))
    bundle = builder.build()

    export = build_auditor_export(bundle)
    histogram = export["chain_summary"]["event_type_histogram"]
    assert histogram.get("eval_event", 0) == 2
    assert histogram.get("policy_check_event", 0) == 2


def test_auditor_export_anchor_status_unanchored_in_v1() -> None:
    builder = ProofBundleBuilder(chain_id="a", producer_runtime="test")
    bundle = builder.build()
    export = build_auditor_export(bundle)
    assert export["chain_summary"]["anchor_status"] == "unanchored"


def test_auditor_export_disclaimer_present() -> None:
    builder = ProofBundleBuilder(chain_id="d", producer_runtime="test")
    bundle = builder.build()
    export = build_auditor_export(bundle)
    assert "compliance opinion" in export["legal_disclaimer"]
