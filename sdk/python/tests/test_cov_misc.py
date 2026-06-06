# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coverage-gap tests for the misc modules:

- attestplane.conformance.negative_vectors (missing: 96, 106, 157-158, 168, 178, 194)
- attestplane.intoto (missing: 176, 182, 189-190)
- attestplane.adapters.langfuse (missing: 119, 210, 212, 217-219)
- attestplane.adapters.langsmith (missing: 203, 211, 217, 221)
- attestplane.canonical (missing: 146)
- attestplane.adapters.base (missing: 143, 168)
- attestplane.obligations.registry (missing: 204)
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from attestplane.adapters.base import AdapterTranslationError, GenericRuntimeAdapter
from attestplane.adapters.langfuse import LangFuseAdapter, LangFuseObservation
from attestplane.adapters.langfuse import _truncate as _lf_truncate
from attestplane.adapters.langsmith import LangSmithAdapter, LangSmithRun
from attestplane.adapters.langsmith import _truncate as _ls_truncate
from attestplane.canonical import CanonicalizationError, _emit_object, canonicalize
from attestplane.conformance.negative_vectors import (
    DuplicateKeyError,
    NegativeVectorResult,
    _has_nfc_violation,
    _has_surrogate,
    _validate_json_candidate,
    _validate_text_candidate,
    _walk_json_values,
    assert_negative_vector,
    classify_negative_vector,
    load_negative_canonicalization_vectors,
    reject_duplicate_keys,
    set_json_path,
)
from attestplane.intoto import (
    IntotoError,
    dsse_envelope_to_statement,
    dsse_pae,
    proof_bundle_to_in_toto_statement,
    statement_to_dsse_envelope,
)
from attestplane.obligations.registry import (
    DuplicateObligationIdError,
    InvalidImplementationStatusError,
    Registry,
    UnknownEventTypeError,
    UnknownEvidenceFieldError,
    _load_from_resource,
    _validate_entry,
    load_all_registries,
    load_dora_article_8,
    load_eu_ai_act_article_12,
)
from attestplane.types import EventDraft

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)

# ---------------------------------------------------------------------------
# attestplane.conformance.negative_vectors
# ---------------------------------------------------------------------------


def test_reject_duplicate_keys_ok() -> None:
    result = reject_duplicate_keys([("a", 1), ("b", 2)])
    assert result == {"a": 1, "b": 2}


def test_reject_duplicate_keys_raises() -> None:
    with pytest.raises(DuplicateKeyError, match="duplicate JSON key"):
        reject_duplicate_keys([("a", 1), ("a", 2)])


def test_walk_json_values_nested() -> None:
    """Line 155-158: walk into dict values."""
    vals = _walk_json_values({"x": [1, {"y": 2}]})
    assert 1 in vals
    assert 2 in vals


def test_has_nfc_violation_string_ok() -> None:
    """Line 163 happy path: NFC string."""
    assert not _has_nfc_violation("hello")


def test_has_nfc_violation_string_bad() -> None:
    """Line 163-164: non-NFC string (e + combining accent = NFD)."""
    nfd = "é"  # e + combining acute accent (NFD)
    assert _has_nfc_violation(nfd)


def test_has_nfc_violation_dict() -> None:
    """Line 165-166: dict with violation in values."""
    nfd_val = "é"  # e + combining acute accent (NFD)
    assert _has_nfc_violation({"key": nfd_val})


def test_has_nfc_violation_list() -> None:
    """Line 167-168: list with violation."""
    nfd_val = "é"  # e + combining acute accent (NFD)
    assert _has_nfc_violation([nfd_val])


def test_has_nfc_violation_other_type() -> None:
    """Line 169 (return False for non-str/dict/list)."""
    assert not _has_nfc_violation(42)
    assert not _has_nfc_violation(None)


def test_has_surrogate_string_ok() -> None:
    """_has_surrogate: clean string."""
    assert not _has_surrogate("hello")


def test_has_surrogate_string_bad() -> None:
    """Line 173-174: string with surrogate codepoint."""
    assert _has_surrogate("\ud800")


def test_has_surrogate_dict() -> None:
    """Line 175-176: dict with surrogate in values."""
    assert _has_surrogate({"k": "\udc00"})


def test_has_surrogate_list() -> None:
    """Line 177-178: list with surrogate."""
    assert _has_surrogate(["\ud801"])


def test_has_surrogate_other_type() -> None:
    """Line 179 (return False for non-str/dict/list)."""
    assert not _has_surrogate(42)


def test_validate_json_candidate_dict_input() -> None:
    """candidate is already a dict → no json.loads needed."""
    vector = {
        "surface": "json",
        "raw_json": {"a": 1},
        "expected": {"reason_code": "att.verify.canonical_mismatch", "pointer": "#/"},
    }
    result = _validate_json_candidate(vector, {"a": 1})
    assert result.ok is True


def test_validate_json_candidate_unsupported_type() -> None:
    """Line 96: AssertionError for unexpected candidate type."""
    vector = {
        "surface": "json",
        "raw_json": {},
        "expected": {"reason_code": "att.verify.canonical_mismatch", "pointer": "#/"},
    }
    with pytest.raises(AssertionError, match="unexpected JSON candidate type"):
        _validate_json_candidate(vector, 12345)


def test_validate_json_candidate_duplicate_key_string() -> None:
    """Line 79-85: string with duplicate key → ok=False."""
    vector = {
        "surface": "json",
        "raw_json": '{"a":1,"a":2}',
        "expected": {"reason_code": "att.verify.structure_invalid", "pointer": "#/"},
    }
    result = _validate_json_candidate(vector, '{"a":1,"a":2}')
    assert not result.ok
    assert result.reason_code == "att.verify.structure_invalid"


def test_validate_json_candidate_malformed_json_string() -> None:
    """Line 86-90: malformed JSON string."""
    vector = {
        "surface": "json",
        "raw_json": '{"a":',
        "expected": {"reason_code": "att.verify.schema_invalid", "pointer": "#/"},
    }
    result = _validate_json_candidate(vector, '{"a":')
    assert not result.ok
    assert result.reason_code == "att.verify.schema_invalid"


def test_validate_json_candidate_schema_version_mismatch() -> None:
    """Line 126-132: schema_version present and != 1."""
    vector = {
        "surface": "json",
        "raw_json": {"schema_version": 2, "x": 1},
        "expected": {"reason_code": "att.verify.schema_version_unsupported", "pointer": "#/"},
    }
    result = _validate_json_candidate(vector, {"schema_version": 2, "x": 1})
    assert not result.ok
    assert result.reason_code == "att.verify.schema_version_unsupported"


def test_validate_json_candidate_trailing_whitespace() -> None:
    """Line 133-138: raw JSON with trailing whitespace."""
    vector = {
        "surface": "json",
        "raw_json": '{"a":1} ',
        "expected": {"reason_code": "att.verify.canonical_mismatch", "pointer": "#/"},
    }
    result = _validate_json_candidate(vector, '{"a":1} ')
    assert not result.ok
    assert "whitespace" in (result.detail or "")


def test_validate_json_candidate_non_canonical_key_order() -> None:
    """Line 140-146: raw != canonical (unsorted keys)."""
    raw = '{"b":1,"a":2}'
    vector = {
        "surface": "json",
        "raw_json": raw,
        "expected": {"reason_code": "att.verify.canonical_mismatch", "pointer": "#/"},
    }
    result = _validate_json_candidate(vector, raw)
    assert not result.ok


def test_validate_json_candidate_float_value() -> None:
    """Line 119-125: float value detected → non-minimal number rejected."""
    vector = {
        "surface": "json",
        "raw_json": {"a": 1.5},
        "expected": {"reason_code": "att.verify.canonical_mismatch", "pointer": "#/"},
    }
    result = _validate_json_candidate(vector, {"a": 1.5})
    assert not result.ok
    assert "non-minimal" in (result.detail or "")


def test_validate_json_candidate_surrogate_value() -> None:
    """Line 105-111: surrogate detected."""
    vector = {
        "surface": "json",
        "raw_json": {"k": "\ud800"},
        "expected": {"reason_code": "att.verify.schema_invalid", "pointer": "#/"},
    }
    result = _validate_json_candidate(vector, {"k": "\ud800"})
    assert not result.ok
    assert "surrogate" in (result.detail or "")


def test_validate_json_candidate_nfc_violation() -> None:
    """Lines 112-118: NFC violation inside dict value → rejected."""
    nfd_str = "é"  # e + combining acute accent (NFD, not NFC U+00E9)
    vector = {
        "surface": "json",
        "raw_json": {"key": nfd_str},
        "expected": {"reason_code": "att.verify.canonical_mismatch", "pointer": "#/"},
    }
    result = _validate_json_candidate(vector, {"key": nfd_str})
    assert not result.ok
    assert "non-NFC" in (result.detail or "")


def test_validate_text_candidate_valid_text() -> None:
    """Lines 182-198: text that passes canonicalize_text → ok=True."""
    vector = {
        "surface": "text",
        "raw_text": "hello world",
        "expected": {"reason_code": "att.verify.canonical_mismatch", "pointer": "#/text"},
    }
    result = _validate_text_candidate(vector, "hello world")
    assert result.ok is True


def test_validate_text_candidate_invalid_text() -> None:
    """Lines 185-193: text that raises CanonicalTextError → ok=False."""
    vector = {
        "surface": "text",
        "raw_text": "",
        "expected": {"reason_code": "att.verify.schema_invalid", "pointer": "#/text"},
    }
    result = _validate_text_candidate(vector, "\x00null byte")
    assert isinstance(result, NegativeVectorResult)


def test_classify_negative_vector_ok_becomes_false() -> None:
    """Lines 210-218: classify returns ok=False when vector unexpectedly passes."""
    vector = {
        "surface": "json",
        "raw_json": '{"a":1}',
        "expected": {"reason_code": "att.verify.canonical_mismatch", "pointer": "#/"},
    }
    result = classify_negative_vector(vector)
    assert not result.ok
    assert "unexpectedly classified" in (result.detail or "")


def test_classify_negative_vector_text_surface() -> None:
    """Line 205-207: surface='text' routes to _validate_text_candidate."""
    vector = {
        "surface": "text",
        "raw_text": "hello",
        "expected": {"reason_code": "att.verify.schema_invalid", "pointer": "#/text"},
    }
    result = classify_negative_vector(vector)
    assert isinstance(result, NegativeVectorResult)


def test_load_negative_canonicalization_vectors() -> None:
    """Lines 33, 37: load_negative_canonicalization_vectors loads vectors from disk."""
    vectors = load_negative_canonicalization_vectors()
    assert isinstance(vectors, list)
    assert len(vectors) > 0


def test_set_json_path() -> None:
    """Lines 52-55: set_json_path modifies nested dict by path."""
    root: dict[str, Any] = {"a": {"b": {"c": 0}}}
    set_json_path(root, ["a", "b", "c"], 42)
    assert root["a"]["b"]["c"] == 42


def test_assert_negative_vector_passes_for_real_vector() -> None:
    """Lines 223-227: assert_negative_vector with a known-bad JSON vector."""
    vector = {
        "case_id": "test_duplicate_key",
        "surface": "json",
        "raw_json": '{"a":1,"a":2}',
        "expected": {
            "reason_code": "att.verify.structure_invalid",
            "pointer": "#/",
        },
    }
    assert_negative_vector(vector)


# ---------------------------------------------------------------------------
# attestplane.intoto missing lines: 176, 182, 189-190
# ---------------------------------------------------------------------------


def test_intoto_bundle_not_dict() -> None:
    """Line ≈69-70: bundle is not a dict."""
    with pytest.raises(IntotoError, match="must be a dict"):
        proof_bundle_to_in_toto_statement("not-a-dict")  # type: ignore[arg-type]


def test_intoto_bundle_missing_chain_metadata() -> None:
    """Line ≈71-73: chain_metadata missing."""
    with pytest.raises(IntotoError, match="chain_metadata missing"):
        proof_bundle_to_in_toto_statement({})


def test_intoto_bundle_missing_chain_id() -> None:
    """Line ≈75-78: chain_id or head_hash_hex missing."""
    with pytest.raises(IntotoError, match="chain_id and head_hash_hex"):
        proof_bundle_to_in_toto_statement({"chain_metadata": {}})


def test_dsse_envelope_to_statement_not_dict() -> None:
    """dsse_envelope_to_statement: envelope is not a dict."""
    with pytest.raises(IntotoError, match="must be a dict"):
        dsse_envelope_to_statement("bad")  # type: ignore[arg-type]


def test_dsse_envelope_to_statement_wrong_payload_type() -> None:
    """unexpected payloadType."""
    with pytest.raises(IntotoError, match="unexpected payloadType"):
        dsse_envelope_to_statement({"payloadType": "wrong/type", "payload": ""})


def test_dsse_envelope_to_statement_payload_not_string() -> None:
    """payload is not a string."""
    with pytest.raises(IntotoError, match="must be a base64 string"):
        dsse_envelope_to_statement({"payloadType": "application/vnd.in-toto+json", "payload": 123})


def test_dsse_envelope_to_statement_invalid_base64() -> None:
    """Line 189: base64 decode fails."""
    with pytest.raises(IntotoError, match="base64-decode"):
        dsse_envelope_to_statement(
            {"payloadType": "application/vnd.in-toto+json", "payload": "!!!not-base64!!!"}
        )


def test_dsse_envelope_to_statement_payload_not_json() -> None:
    """Line 190: decoded bytes are not valid JSON."""
    bad_json = base64.standard_b64encode(b"not json {").decode()
    with pytest.raises(IntotoError, match="not valid JSON"):
        dsse_envelope_to_statement({"payloadType": "application/vnd.in-toto+json", "payload": bad_json})


def test_dsse_envelope_to_statement_payload_not_object() -> None:
    """payload JSON is a list, not an object."""
    list_json = base64.standard_b64encode(b"[1,2,3]").decode()
    with pytest.raises(IntotoError, match="must be an object"):
        dsse_envelope_to_statement({"payloadType": "application/vnd.in-toto+json", "payload": list_json})


def test_dsse_envelope_to_statement_roundtrip() -> None:
    """Happy path: statement → envelope → statement roundtrip."""
    statement = {"_type": "t", "subject": [], "predicateType": "p", "predicate": {}}
    envelope = statement_to_dsse_envelope(statement)
    recovered = dsse_envelope_to_statement(envelope)
    assert recovered["_type"] == "t"


def test_intoto_proof_bundle_to_statement_happy() -> None:
    """Successful conversion of a real bundle to in-toto statement."""
    from attestplane.hashchain import chain_extend, genesis_head
    from attestplane.proof_bundle import ProofBundleBuilder

    head = genesis_head()
    ts = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    draft = EventDraft(event_type="eval_event", actor="a", payload={})
    event = chain_extend(head, draft, now=ts, event_id="00000000-0000-7000-8000-000000000001")
    builder = ProofBundleBuilder(chain_id="c", producer_runtime="t")
    builder.extend([event])
    bundle = builder.build()

    stmt = proof_bundle_to_in_toto_statement(bundle)
    assert stmt["_type"] == "https://in-toto.io/Statement/v1"
    assert stmt["subject"][0]["name"] == "c"


def test_dsse_pae_encoding() -> None:
    """Lines 160-161: dsse_pae produces correct PAE bytes."""
    pt = "application/vnd.in-toto+json"
    payload = b"hello"
    pae = dsse_pae(pt, payload)
    assert pae.startswith(b"DSSEv1 ")
    assert b"hello" in pae


# ---------------------------------------------------------------------------
# attestplane.adapters.langfuse missing: 119, 136, 140, 153, 162->166, 173, 180, 210, 212, 217-219, 223
# ---------------------------------------------------------------------------


def test_langfuse_truncate_long_string() -> None:
    """Line 119: _truncate trims strings > 200 chars."""
    long_msg = "x" * 300
    obs = LangFuseObservation(
        id="obs-trunc",
        trace_id="t",
        type="GENERATION",
        level="ERROR",
        status_message=long_msg,
    )
    draft = LangFuseAdapter().translate(obs)
    assert draft.payload["error_code"].endswith("...")
    assert len(draft.payload["error_code"]) == 200


def test_langfuse_truncate_short_string_returned_as_is() -> None:
    """Line 118: _truncate with short string (≤ 200 chars) → returned unchanged."""
    short = "short message"
    assert _lf_truncate(short) == short


def test_langfuse_translate_wrong_type() -> None:
    """Line 136: translate called with non-LangFuseObservation."""
    with pytest.raises(AdapterTranslationError, match="expected LangFuseObservation"):
        LangFuseAdapter().translate("not-an-observation")  # type: ignore[arg-type]


def test_langfuse_unknown_type_maps_to_unknown() -> None:
    """Line 140: obs.type not in known set → kind='unknown'."""
    obs = LangFuseObservation(id="x", trace_id="t", type="CUSTOM_TYPE")
    draft = LangFuseAdapter().translate(obs)
    assert draft.payload["kind"] == "unknown"


def test_langfuse_translate_with_non_none_input_uses_real_hash() -> None:
    """Line 153: obs.input is not None → arguments_hash = _hash_json(obs.input)."""
    obs = LangFuseObservation(id="x", trace_id="t", type="SPAN", input={"prompt": "hello"})
    draft = LangFuseAdapter().translate(obs)
    expected_hash = hashlib.sha256(
        json.dumps(
            {"prompt": "hello"}, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()
    assert draft.payload["arguments_hash"] == expected_hash


def test_langfuse_translate_with_input_none_uses_empty_hash() -> None:
    """Line 155-158: input is None → arguments_hash is hash of {}."""
    obs = LangFuseObservation(id="x", trace_id="t", type="SPAN", input=None)
    draft = LangFuseAdapter().translate(obs)
    empty_hash = hashlib.sha256(
        json.dumps({}, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert draft.payload["arguments_hash"] == empty_hash


def test_langfuse_translate_with_output_sets_result_hash() -> None:
    """Line 160: output is not None → result_hash set."""
    obs = LangFuseObservation(id="x", trace_id="t", type="SPAN", output={"k": "v"})
    draft = LangFuseAdapter().translate(obs)
    assert "result_hash" in draft.payload


def test_langfuse_no_output_no_result_hash() -> None:
    """Line 157-160: output is None → no result_hash in payload."""
    obs = LangFuseObservation(id="x", trace_id="t", type="SPAN", output=None)
    draft = LangFuseAdapter().translate(obs)
    assert "result_hash" not in draft.payload


def test_langfuse_translate_with_start_and_end_time_sets_latency() -> None:
    """Lines 162-164: both start_time and end_time → latency_ms set."""
    obs = LangFuseObservation(
        id="x",
        trace_id="t",
        type="SPAN",
        start_time=_NOW,
        end_time=_NOW + timedelta(milliseconds=500),
    )
    draft = LangFuseAdapter().translate(obs)
    assert draft.payload.get("latency_ms") == 500


def test_langfuse_no_start_end_time_no_latency() -> None:
    """Lines 162-164: start_time or end_time is None → no latency_ms."""
    obs = LangFuseObservation(id="x", trace_id="t", type="SPAN", start_time=None, end_time=None)
    draft = LangFuseAdapter().translate(obs)
    assert "latency_ms" not in draft.payload


def test_langfuse_status_message_not_error_level_skipped() -> None:
    """Line 166-167: status_message present but result_status != ERROR → no error_code."""
    obs = LangFuseObservation(id="x", trace_id="t", type="SPAN", level="DEFAULT", status_message="fine")
    draft = LangFuseAdapter().translate(obs)
    assert "error_code" not in draft.payload


def test_langfuse_translate_model_sets_tool_version() -> None:
    """Line 173: model → tool_version."""
    obs = LangFuseObservation(id="x", trace_id="t", type="GENERATION", model="gpt-4o")
    draft = LangFuseAdapter().translate(obs)
    assert draft.payload["tool_version"] == "gpt-4o"


def test_langfuse_level_default_not_in_payload() -> None:
    """Line 175-177: level='DEFAULT' → not emitted in payload."""
    obs = LangFuseObservation(id="x", trace_id="t", type="SPAN", level="DEFAULT")
    draft = LangFuseAdapter().translate(obs)
    assert "level" not in draft.payload


def test_langfuse_level_warning_in_payload() -> None:
    """level='WARNING' (non-DEFAULT) → emitted in payload."""
    obs = LangFuseObservation(id="x", trace_id="t", type="SPAN", level="WARNING")
    draft = LangFuseAdapter().translate(obs)
    assert draft.payload.get("level") == "WARNING"


def test_langfuse_translate_user_id_sets_subject_ref() -> None:
    """Line 180: user_id → SubjectRef."""
    obs = LangFuseObservation(id="x", trace_id="t", type="SPAN", user_id="user-42")
    draft = LangFuseAdapter().translate(obs)
    assert draft.subject_ref is not None
    assert draft.subject_ref.value == "user-42"


def test_langfuse_no_user_id_no_subject_ref() -> None:
    """Lines 178-180: user_id is None → subject_ref is None."""
    obs = LangFuseObservation(id="x", trace_id="t", type="SPAN", user_id=None)
    draft = LangFuseAdapter().translate(obs)
    assert draft.subject_ref is None


def test_langfuse_from_dict_missing_fields() -> None:
    """Line 206: missing required fields in from_dict."""
    with pytest.raises(AdapterTranslationError, match="missing required fields"):
        LangFuseAdapter.from_dict({"id": "x"})


def test_langfuse_from_dict_start_time_as_datetime() -> None:
    """Line 212: parse_dt with datetime object (already datetime)."""
    obs = LangFuseAdapter.from_dict(
        {
            "id": "x",
            "trace_id": "t",
            "type": "SPAN",
            "start_time": _NOW,
            "end_time": _NOW,
        }
    )
    assert obs.start_time == _NOW


def test_langfuse_from_dict_start_time_none() -> None:
    """start_time absent → None (guarded by if raw.get(...))."""
    obs = LangFuseAdapter.from_dict({"id": "x", "trace_id": "t", "type": "SPAN"})
    assert obs.start_time is None


def test_langfuse_from_dict_parse_dt_none_returns_none() -> None:
    """end_time=None explicitly → obs.end_time is None."""
    obs = LangFuseAdapter.from_dict(
        {"id": "x", "trace_id": "t", "type": "SPAN", "end_time": None}
    )
    assert obs.end_time is None


def test_langfuse_from_dict_invalid_datetime_string() -> None:
    """Line 217-218: unparsable datetime string."""
    with pytest.raises(AdapterTranslationError, match="unparsable datetime"):
        LangFuseAdapter.from_dict(
            {"id": "x", "trace_id": "t", "type": "SPAN", "start_time": "not-a-date"}
        )


def test_langfuse_from_dict_datetime_wrong_type() -> None:
    """Line 219: datetime field is wrong type (int)."""
    with pytest.raises(AdapterTranslationError, match="datetime field has type"):
        LangFuseAdapter.from_dict(
            {"id": "x", "trace_id": "t", "type": "SPAN", "start_time": 12345}
        )


def test_langfuse_from_dict_metadata_not_dict() -> None:
    """Line 223: metadata is not a dict."""
    with pytest.raises(AdapterTranslationError, match="metadata must be a dict"):
        LangFuseAdapter.from_dict(
            {"id": "x", "trace_id": "t", "type": "SPAN", "metadata": "bad"}
        )


# ---------------------------------------------------------------------------
# attestplane.adapters.langsmith missing: 122, 133, 203, 209-211, 217, 221
# ---------------------------------------------------------------------------


def test_langsmith_truncate_long_error() -> None:
    """Line 122: _truncate on error > 200 chars."""
    long_err = "e" * 300
    run = LangSmithRun(id="r1", name="tool", run_type="tool", start_time=_NOW, error=long_err)
    draft = LangSmithAdapter().translate(run)
    assert draft.payload["error_code"].endswith("...")
    assert len(draft.payload["error_code"]) == 200


def test_langsmith_truncate_short_string_returned_as_is() -> None:
    """Line 121: _truncate with short string → returned unchanged."""
    short = "short"
    assert _ls_truncate(short) == short


def test_langsmith_translate_wrong_type() -> None:
    """Line 133: translate called with non-LangSmithRun."""
    with pytest.raises(AdapterTranslationError, match="expected LangSmithRun"):
        LangSmithAdapter().translate("not-a-run")  # type: ignore[arg-type]


def test_langsmith_from_dict_missing_fields() -> None:
    """Line 203: missing required fields in from_dict."""
    with pytest.raises(AdapterTranslationError, match="missing required fields"):
        LangSmithAdapter.from_dict({"id": "x"})


def test_langsmith_from_dict_datetime_is_datetime_obj() -> None:
    """Line 202-203: parse_dt with already-datetime object."""
    obs = LangSmithAdapter.from_dict(
        {"id": "x", "name": "tool", "run_type": "tool", "start_time": _NOW}
    )
    assert obs.start_time == _NOW


def test_langsmith_from_dict_invalid_datetime_string() -> None:
    """Lines 209-210: unparsable datetime string."""
    with pytest.raises(AdapterTranslationError, match="unparsable datetime"):
        LangSmithAdapter.from_dict(
            {"id": "x", "name": "tool", "run_type": "tool", "start_time": "not-a-date"}
        )


def test_langsmith_from_dict_datetime_wrong_type() -> None:
    """Line 211-213: datetime field is wrong type."""
    with pytest.raises(AdapterTranslationError, match="datetime field has type"):
        LangSmithAdapter.from_dict(
            {"id": "x", "name": "tool", "run_type": "tool", "start_time": 999}
        )


def test_langsmith_from_dict_metadata_not_dict() -> None:
    """Line 217: metadata must be a dict."""
    with pytest.raises(AdapterTranslationError, match="metadata must be a dict"):
        LangSmithAdapter.from_dict(
            {
                "id": "x",
                "name": "tool",
                "run_type": "tool",
                "start_time": _NOW.isoformat(),
                "metadata": "bad",
            }
        )


def test_langsmith_from_dict_tags_not_list() -> None:
    """Line 221: tags must be list or tuple."""
    with pytest.raises(AdapterTranslationError, match="tags must be a list"):
        LangSmithAdapter.from_dict(
            {
                "id": "x",
                "name": "tool",
                "run_type": "tool",
                "start_time": _NOW.isoformat(),
                "tags": "not-a-list",
            }
        )


def test_langsmith_translate_no_error_with_end_time_sets_latency() -> None:
    """Lines 144-145, 157-160: no error + end_time → result_status=OK, latency_ms set."""
    run = LangSmithRun(
        id="r1",
        name="tool",
        run_type="tool",
        start_time=_NOW,
        end_time=_NOW + timedelta(milliseconds=100),
        outputs={"out": 1},
    )
    draft = LangSmithAdapter().translate(run)
    assert draft.payload["result_status"] == "OK"
    assert draft.payload.get("latency_ms") == 100
    assert "result_hash" in draft.payload


def test_langsmith_translate_in_progress_no_end_time() -> None:
    """Lines 139-143: end_time=None + status='in_progress' → OK."""
    run = LangSmithRun(
        id="r2",
        name="tool",
        run_type="tool",
        start_time=_NOW,
        end_time=None,
        status="in_progress",
    )
    draft = LangSmithAdapter().translate(run)
    assert draft.payload["result_status"] == "OK"
    assert "latency_ms" not in draft.payload


def test_langsmith_translate_with_tags() -> None:
    """Line 163-164: run.tags → payload.tags."""
    run = LangSmithRun(
        id="r3",
        name="tool",
        run_type="tool",
        start_time=_NOW,
        tags=("tag1", "tag2"),
    )
    draft = LangSmithAdapter().translate(run)
    assert draft.payload["tags"] == ["tag1", "tag2"]


def test_langsmith_translate_unknown_run_type() -> None:
    """Line 147: unknown run_type maps to 'unknown'."""
    run = LangSmithRun(id="r4", name="tool", run_type="custom_type", start_time=_NOW)
    draft = LangSmithAdapter().translate(run)
    assert draft.payload["kind"] == "unknown"


def test_langsmith_translate_end_user_id_sets_subject_ref() -> None:
    """Line 167-173: end_user_id → SubjectRef."""
    run = LangSmithRun(
        id="r5", name="tool", run_type="tool", start_time=_NOW, end_user_id="uid-42"
    )
    draft = LangSmithAdapter().translate(run)
    assert draft.subject_ref is not None
    assert draft.subject_ref.value == "uid-42"


def test_langsmith_translate_no_trace_id_uses_run_id_as_session() -> None:
    """Line 177: trace_id is None → session_id = run.id."""
    run = LangSmithRun(id="r6", name="tool", run_type="tool", start_time=_NOW, trace_id=None)
    draft = LangSmithAdapter().translate(run)
    assert draft.session_id == "r6"


# ---------------------------------------------------------------------------
# attestplane.canonical missing: line 146
# ---------------------------------------------------------------------------


def test_canonical_duplicate_key_in_dict() -> None:
    """Line 146: duplicate key detected inside _emit_object via custom dict subclass."""

    class _DuplicateKeyDict(dict):
        """Returns duplicate keys via iteration to trigger the defensive guard."""

        def keys(self) -> list[str]:  # type: ignore[override]
            return ["a", "a", "b"]

        def __iter__(self):  # type: ignore[override]
            return iter(["a", "a", "b"])

        def __getitem__(self, key: str) -> int:  # type: ignore[override]
            return 1

    out: list[str] = []
    with pytest.raises(CanonicalizationError, match="duplicate object key"):
        _emit_object(_DuplicateKeyDict(), out, path="$")


def test_canonical_object_with_many_keys() -> None:
    result = canonicalize({"z": 1, "a": 2, "m": 3})
    parsed = json.loads(result)
    assert parsed == {"z": 1, "a": 2, "m": 3}
    assert result == b'{"a":2,"m":3,"z":1}'


def test_canonical_non_string_key_raises() -> None:
    """_emit_object raises for non-string key."""
    with pytest.raises(CanonicalizationError, match="object keys must be strings"):
        canonicalize({1: "a"})  # type: ignore[dict-item]


def test_canonical_null() -> None:
    assert canonicalize(None) == b"null"


def test_canonical_bool() -> None:
    assert canonicalize(True) == b"true"
    assert canonicalize(False) == b"false"


def test_canonical_int_overflow_raises() -> None:
    with pytest.raises(CanonicalizationError, match="outside signed 64-bit range"):
        canonicalize(2**63)


def test_canonical_float_raises() -> None:
    with pytest.raises(CanonicalizationError, match="float values are forbidden"):
        canonicalize(1.5)


def test_canonical_bytes() -> None:
    result = canonicalize(b"\x00\x01\x02")
    assert result  # base64url encoded


def test_canonical_datetime_utc() -> None:
    dt = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    result = canonicalize(dt)
    assert b"2026-05-17" in result


def test_canonical_datetime_naive_raises() -> None:
    from datetime import datetime as dt_naive

    with pytest.raises(CanonicalizationError, match="timezone-aware"):
        canonicalize(dt_naive(2026, 5, 17, 12, 0, 0))


def test_canonical_datetime_non_utc_raises() -> None:
    tz_plus1 = timezone(timedelta(hours=1))
    with pytest.raises(CanonicalizationError, match="UTC"):
        canonicalize(datetime(2026, 5, 17, 12, 0, 0, tzinfo=tz_plus1))


def test_canonical_string_with_special_escapes() -> None:
    """_emit_string: various escape sequences."""
    assert b"\\b" in canonicalize("\x08")
    assert b"\\f" in canonicalize("\x0c")
    assert b"\\r" in canonicalize("\r")


def test_canonical_string_with_low_control_char() -> None:
    """_emit_string: low-control char uses \\uXXXX."""
    result = canonicalize("\x01")
    assert b"\\u0001" in result


def test_canonical_list() -> None:
    result = canonicalize([1, 2, 3])
    assert result == b"[1,2,3]"


def test_canonical_tuple() -> None:
    result = canonicalize((1, 2))
    assert result == b"[1,2]"


def test_canonical_dataclass() -> None:
    """_emit_object via dataclass."""

    @dataclass
    class _Simple:
        x: int
        y: str

    result = canonicalize(_Simple(x=1, y="hello"))
    parsed = json.loads(result)
    assert parsed["x"] == 1
    assert parsed["y"] == "hello"


def test_canonical_unsupported_type_raises() -> None:
    with pytest.raises(CanonicalizationError, match="unsupported type"):
        canonicalize(object())  # type: ignore[arg-type]


def test_canonical_nfc_violation_raises() -> None:
    # e (U+0065) + combining acute accent (U+0301) = NFD form
    nfd = "\u0065\u0301"
    with pytest.raises(CanonicalizationError, match="NFC"):
        canonicalize(nfd)


def test_canonical_surrogate_raises() -> None:
    with pytest.raises(CanonicalizationError, match="surrogate"):
        canonicalize("\ud800")


# ---------------------------------------------------------------------------
# attestplane.adapters.base missing: 143, 168
# ---------------------------------------------------------------------------


def test_base_forbidden_method_raises_on_subclass_definition() -> None:
    """Line 143: __init_subclass__ raises TypeError for forbidden method names."""
    with pytest.raises(TypeError, match="forbidden authority/execution method"):

        class _BadAdapter(GenericRuntimeAdapter[str]):  # type: ignore[type-abstract]
            runtime_name = "bad"
            schema_version = 1

            def translate(self, runtime_event: str) -> EventDraft:  # type: ignore[override]
                return EventDraft(event_type="e", actor="a", payload={})

            def execute(self) -> None:  # forbidden method!
                pass


def test_base_abstract_translate_not_implemented() -> None:
    """Line 168: the abstract translate raises NotImplementedError."""

    class _ConcreteAdapter(GenericRuntimeAdapter[str]):
        runtime_name = "concrete"
        schema_version = 1

        def translate(self, runtime_event: str) -> EventDraft:
            return super().translate(runtime_event)  # type: ignore[misc]

    adapter = _ConcreteAdapter()
    with pytest.raises(NotImplementedError):
        adapter.translate("x")


# ---------------------------------------------------------------------------
# attestplane.obligations.registry missing: 127-130, 134, 137, 143, 154, 167, 204, 244, 260
# ---------------------------------------------------------------------------


def test_registry_by_id_found() -> None:
    """Lines 127-128: by_id returns the matching entry."""
    reg = load_eu_ai_act_article_12()
    first = reg.entries[0]
    found = reg.by_id(first.obligation_id)
    assert found.obligation_id == first.obligation_id


def test_registry_by_id_not_found() -> None:
    """Lines 129-130: by_id raises KeyError for missing id."""
    reg = load_eu_ai_act_article_12()
    with pytest.raises(KeyError, match="no obligation entry"):
        reg.by_id("does.not.exist")


def test_registry_by_event_type() -> None:
    """Line 134: by_event_type returns tuple."""
    reg = load_eu_ai_act_article_12()
    result = reg.by_event_type("eval_event")
    assert isinstance(result, tuple)


def test_registry_by_implementation_status() -> None:
    """Line 137: by_implementation_status filter."""
    reg = load_eu_ai_act_article_12()
    result = reg.by_implementation_status("mapping_target")
    assert isinstance(result, tuple)


def test_validate_entry_invalid_implementation_status() -> None:
    """Line 143: invalid implementation_status raises InvalidImplementationStatusError."""
    with pytest.raises(InvalidImplementationStatusError, match="implementation_status"):
        _validate_entry(
            {
                "framework": "EU AI Act",
                "article": "12",
                "paragraph": "1",
                "obligation_id": "test.1",
                "regulatory_text": "text",
                "required_evidence_fields": [],
                "optional_evidence_fields": [],
                "event_type_mapping": [],
                "verifier_expectation": "exp",
                "implementation_status": "bad_status",
                "legal_disclaimer": "disc",
                "source_citation": "cite",
            }
        )


def test_validate_entry_unknown_event_type() -> None:
    """Line 154: unknown event_type in event_type_mapping."""
    with pytest.raises(UnknownEventTypeError, match="not a v1 taxonomy member"):
        _validate_entry(
            {
                "framework": "EU AI Act",
                "article": "12",
                "paragraph": "1",
                "obligation_id": "test.2",
                "regulatory_text": "text",
                "required_evidence_fields": [],
                "optional_evidence_fields": [],
                "event_type_mapping": ["nonexistent_event_type_xyz"],
                "verifier_expectation": "exp",
                "implementation_status": "mapping_target",
                "legal_disclaimer": "disc",
                "source_citation": "cite",
            }
        )


def test_validate_entry_unknown_evidence_field() -> None:
    """Line 167: unknown evidence field raises UnknownEvidenceFieldError."""
    with pytest.raises(UnknownEvidenceFieldError, match="not a known EventDraft"):
        _validate_entry(
            {
                "framework": "EU AI Act",
                "article": "12",
                "paragraph": "1",
                "obligation_id": "test.3",
                "regulatory_text": "text",
                "required_evidence_fields": ["nonexistent_field_xyz"],
                "optional_evidence_fields": [],
                "event_type_mapping": [],
                "verifier_expectation": "exp",
                "implementation_status": "mapping_target",
                "legal_disclaimer": "disc",
                "source_citation": "cite",
            }
        )


def test_load_from_resource_duplicate_obligation_id() -> None:
    """Line 204: duplicate obligation_id raises DuplicateObligationIdError."""
    entry = {
        "framework": "EU AI Act",
        "article": "12",
        "paragraph": "1",
        "obligation_id": "dup.id",
        "regulatory_text": "text",
        "required_evidence_fields": [],
        "optional_evidence_fields": [],
        "event_type_mapping": [],
        "verifier_expectation": "exp",
        "implementation_status": "mapping_target",
        "legal_disclaimer": "disc",
        "source_citation": "cite",
    }
    data = {
        "framework": "EU AI Act",
        "framework_source": "OJ",
        "registry_version": 1,
        "last_reviewed": "2026-01-01",
        "entries": [entry, dict(entry)],  # duplicate
    }
    fake_bytes = json.dumps(data).encode("utf-8")

    mock_resource = MagicMock()
    mock_resource.read_bytes.return_value = fake_bytes
    mock_files = MagicMock()
    mock_files.return_value.joinpath.return_value = mock_resource

    with (
        patch("attestplane.obligations.registry.resources.files", mock_files),
        pytest.raises(DuplicateObligationIdError, match=r"dup\.id"),
    ):
        _load_from_resource("fake_file.json")


def test_load_dora_article_8() -> None:
    """Line 244: load_dora_article_8 returns a Registry."""
    reg = load_dora_article_8()
    assert isinstance(reg, Registry)
    assert len(reg.entries) > 0


def test_load_all_registries() -> None:
    """Line 260: load_all_registries returns tuple of two registries."""
    regs = load_all_registries()
    assert len(regs) == 2
    frameworks = {r.framework for r in regs}
    assert len(frameworks) >= 1
