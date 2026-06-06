# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coverage tests for attestplane.cli.main — targets all uncovered branches."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from attestplane.cli.main import (
    _collect_nested_reserved_reasons,
    _explain_reserved_reasons,
    _reason_entries,
    _verify_human_summary,
    _write_verify_explanations,
    main,
)
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.proof_bundle import ProofBundleBuilder
from attestplane.storage.jsonl import JsonlStorageBackend
from attestplane.types import ChainHead, EventDraft
from attestplane.verify_reason_codes import (
    VERIFY_REASON_CANONICAL_MISMATCH,
    VERIFY_REASON_SIGNATURE_MISSING,
    VERIFY_REASON_STRUCTURE_INVALID,
)

ROOT = Path(__file__).resolve().parents[3]
QUARANTINE_FIXTURE = (
    Path(__file__).resolve().parent / "conformance" / "free_tsa_quarantined_bundle.json"
)


def _seed_chain(path: Path, n: int = 2) -> None:
    backend = JsonlStorageBackend(path)
    head = genesis_head()
    ts = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    for i in range(n):
        draft = EventDraft(
            event_type="eval_event",
            actor=f"agent://test/{i}",
            payload={"index": i},
        )
        event = chain_extend(
            head, draft, now=ts, event_id=f"00000000-0000-7000-8000-{i:012d}"
        )
        backend.append(event)
        head = ChainHead(seq=event.seq, event_hash=event.event_hash)
    backend.close()


def _build_bundle(tmp_path: Path, n: int = 2) -> Path:
    chain_path = tmp_path / "chain.jsonl"
    bundle_path = tmp_path / "bundle.json"
    _seed_chain(chain_path, n=n)
    main(["export", str(chain_path), "--out", str(bundle_path)])
    return bundle_path


# ---------------------------------------------------------------------------
# _verify_human_summary branches (lines 248-260)
# ---------------------------------------------------------------------------


class _FakeResult:
    ok: bool = False
    anchoring_quarantined: bool = False
    anchoring_status: str = "absent"
    primary_reason: str | None = None
    secondary_reasons: tuple[str, ...] = ()
    metadata_ok: bool = True
    metadata_reason: str | None = None
    signed_attestation_schema_ok: bool = True
    signed_attestation_schema_reason: str | None = None
    policy_trace_refs_ok: bool = True
    policy_trace_refs_reason: str | None = None
    retention_proofs_ok: bool = True
    retention_proofs_reason: str | None = None

    def __init__(self, **kw: Any) -> None:
        for k, v in kw.items():
            setattr(self, k, v)

    class chain_result:
        ok: bool = True
        first_bad_index: int = -1
        reason: str | None = None


def test_verify_human_summary_none_args() -> None:
    assert _verify_human_summary(None, status="OK") == "OK"
    assert _verify_human_summary(None, bundle=None, status="FAIL") == "FAIL"


def test_verify_human_summary_no_chain_metadata() -> None:
    result = _FakeResult()
    bundle: dict[str, Any] = {"not_chain_metadata": True}
    summary = _verify_human_summary(result, bundle=bundle, status="FAIL")
    assert "anchor=unknown" in summary


def test_verify_human_summary_anchor_absent() -> None:
    result = _FakeResult()
    bundle: dict[str, Any] = {"chain_metadata": {}}
    summary = _verify_human_summary(result, bundle=bundle, status="FAIL")
    assert "anchor=absent" in summary


def test_verify_human_summary_anchor_present() -> None:
    result = _FakeResult()
    bundle: dict[str, Any] = {"chain_metadata": {"anchor_ref": "https://example.com/anchor"}}
    summary = _verify_human_summary(result, bundle=bundle, status="FAIL")
    assert "anchor=present" in summary


def test_verify_human_summary_anchoring_quarantined_with_reason() -> None:
    result = _FakeResult(
        anchoring_quarantined=True,
        anchoring_status="quarantined",
        primary_reason=VERIFY_REASON_CANONICAL_MISMATCH,
    )
    bundle: dict[str, Any] = {"chain_metadata": {}}
    summary = _verify_human_summary(result, bundle=bundle, status="FAIL")
    assert "anchor=quarantined" in summary
    assert "quarantine_reason=" in summary
    assert VERIFY_REASON_CANONICAL_MISMATCH in summary


def test_verify_human_summary_anchoring_quarantined_no_primary_reason() -> None:
    result = _FakeResult(
        anchoring_quarantined=True,
        anchoring_status="quarantined",
        primary_reason=None,
    )
    bundle: dict[str, Any] = {"chain_metadata": {}}
    summary = _verify_human_summary(result, bundle=bundle, status="FAIL")
    assert "quarantine_reason=unknown" in summary


# ---------------------------------------------------------------------------
# _write_verify_explanations (lines 264-269)
# ---------------------------------------------------------------------------


def test_write_verify_explanations_with_reason(capsys: pytest.CaptureFixture[str]) -> None:
    entries: list[dict[str, Any]] = [
        {"primary_reason": "att.verify.schema_invalid", "pointer": "/foo", "message": "bad field"},
        {"primary_reason": None, "pointer": "/", "message": "ok message"},
        {"pointer": "/bar", "message": "no primary_reason key"},
    ]
    _write_verify_explanations(entries)
    err = capsys.readouterr().err
    assert "att.verify.schema_invalid /foo: bad field" in err
    assert "ok /: ok message" in err
    assert "/bar:" in err


# ---------------------------------------------------------------------------
# _reason_entries (lines 233-238)
# ---------------------------------------------------------------------------


def test_reason_entries_with_secondary_reasons() -> None:
    result = _FakeResult(
        primary_reason=VERIFY_REASON_CANONICAL_MISMATCH,
        secondary_reasons=(VERIFY_REASON_STRUCTURE_INVALID,),
    )
    entries = _reason_entries(result)
    codes = [e["code"] for e in entries]
    assert VERIFY_REASON_CANONICAL_MISMATCH in codes
    assert VERIFY_REASON_STRUCTURE_INVALID in codes


def test_reason_entries_explain_with_reserved_fields() -> None:
    result = _FakeResult(ok=True, primary_reason=None, secondary_reasons=())
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    bundle["extra_top_level"] = True
    entries = _reason_entries(result, bundle=bundle, explain=True)
    assert any(e.get("severity") == "reserved" for e in entries)


def test_reason_entries_no_explain_no_reserved() -> None:
    result = _FakeResult(ok=True, primary_reason=None, secondary_reasons=())
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    bundle["extra_top_level"] = True
    entries = _reason_entries(result, bundle=bundle, explain=False)
    assert entries == []


# ---------------------------------------------------------------------------
# _explain_reserved_reasons edge cases (lines 357-413)
# ---------------------------------------------------------------------------


def test_explain_reserved_reasons_non_dict_framework_mapping() -> None:
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    bundle["framework_mappings"] = ["not_a_dict"]  # non-dict entry
    reasons = _explain_reserved_reasons(bundle)
    # Non-dict entries are skipped; no crash
    assert isinstance(reasons, list)


def test_explain_reserved_reasons_non_dict_event_item() -> None:
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    bundle["events"] = ["not_a_dict"]
    reasons = _explain_reserved_reasons(bundle)
    assert isinstance(reasons, list)


def test_explain_reserved_reasons_event_without_nested_event() -> None:
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    bundle["events"] = [{"seq": 0, "prev_hash_hex": "0" * 64}]
    reasons = _explain_reserved_reasons(bundle)
    assert isinstance(reasons, list)


def test_explain_reserved_reasons_non_dict_signature_item() -> None:
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    bundle["signatures"] = ["not_a_dict"]
    reasons = _explain_reserved_reasons(bundle)
    assert isinstance(reasons, list)


def test_explain_reserved_reasons_non_dict_retention_proof() -> None:
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    bundle["retention_proofs"] = ["not_a_dict"]
    reasons = _explain_reserved_reasons(bundle)
    assert isinstance(reasons, list)


def test_explain_reserved_reasons_empty_extras() -> None:
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    assert _explain_reserved_reasons(bundle) == []


def test_explain_reserved_reasons_non_dict_chain_metadata_skips() -> None:
    """Branch 357->360: chain_metadata is not a dict → skip chain_metadata loop."""
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    bundle["chain_metadata"] = "not_a_dict"
    # Should not crash; chain_metadata loop body is skipped
    reasons = _explain_reserved_reasons(bundle)
    assert isinstance(reasons, list)


def test_explain_reserved_reasons_non_dict_verification_report_skips() -> None:
    """Branch 361->364: verification_report is not a dict → skip verification_report loop."""
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    bundle["verification_report"] = "not_a_dict"
    reasons = _explain_reserved_reasons(bundle)
    assert isinstance(reasons, list)


def test_explain_reserved_reasons_non_list_framework_mappings_skips() -> None:
    """Branch 365->371: framework_mappings is not a list → skip loop."""
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    bundle["framework_mappings"] = {"not": "a_list"}
    reasons = _explain_reserved_reasons(bundle)
    assert isinstance(reasons, list)


def test_explain_reserved_reasons_non_list_events_skips() -> None:
    """Branch 372->386: events is not a list → skip loop."""
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    bundle["events"] = {"not": "a_list"}
    reasons = _explain_reserved_reasons(bundle)
    assert isinstance(reasons, list)


def test_explain_reserved_reasons_all_sections_with_extra_fields() -> None:
    """Covers all loop bodies in _explain_reserved_reasons (lines 359,363,369-370,377,390,400)."""
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    # Add extra fields to every known section to exercise each loop body
    bundle["chain_metadata"]["extra_chain_field"] = True  # line 359
    bundle["verification_report"]["extra_report_field"] = True  # line 363
    bundle["framework_mappings"] = [  # line 369-370
        {
            "obligation_id": "obl",
            "evidence_event_indexes": [],
            "implementation_status_at_bundle_time": "implemented",
            "extra_mapping_field": True,
        }
    ]
    bundle["events"] = [  # line 377
        {
            "seq": 0,
            "prev_hash_hex": "0" * 64,
            "event_hash_hex": "1" * 64,
            "extra_event_item_field": True,
        }
    ]
    bundle["signatures"] = [{"signature_schema_version": 1, "extra_sig_field": True}]  # line 390
    bundle["retention_proofs"] = [  # line 400
        {
            "retention_proof_schema_version": 1,
            "proof_id": "p",
            "action": "delete",
            "target_event_hash_hex": "2" * 64,
            "commit_event_hash_hex": "3" * 64,
            "reason": "r",
            "redacted_event_hash_hex": "4" * 64,
            "extra_retention_field": True,
        }
    ]

    reasons = _explain_reserved_reasons(bundle)
    assert reasons
    detail = reasons[0]["detail"]
    assert "chain_metadata.extra_chain_field" in detail
    assert "verification_report.extra_report_field" in detail
    assert "framework_mappings[0].extra_mapping_field" in detail
    assert "events[0].extra_event_item_field" in detail
    assert "signatures[0].extra_sig_field" in detail
    assert "retention_proofs[0].extra_retention_field" in detail


# ---------------------------------------------------------------------------
# _collect_nested_reserved_reasons (lines 418-439)
# ---------------------------------------------------------------------------


def test_collect_nested_reserved_reasons_with_subject_ref() -> None:
    obj = {
        "schema_version": 1,
        "event_id": "x",
        "timestamp": "t",
        "event_type": "t",
        "actor": "a",
        "payload": {},
        "subject_ref": {"scheme": "s", "value": "v", "extra_subject": True},
        "extra_event_field": True,
    }
    extras: list[str] = []
    from attestplane.cli.main import _KNOWN_AUDIT_EVENT_FIELDS
    _collect_nested_reserved_reasons(obj, "events[0].event", _KNOWN_AUDIT_EVENT_FIELDS, extras)
    assert any("extra_event_field" in e for e in extras)
    assert any("extra_subject" in e for e in extras)


def test_collect_nested_reserved_reasons_with_human_verifier() -> None:
    obj = {
        "schema_version": 1,
        "human_verifier": {"scheme": "mailto", "value": "x@y.z", "extra_human": True},
    }
    extras: list[str] = []
    from attestplane.cli.main import _KNOWN_AUDIT_EVENT_FIELDS
    _collect_nested_reserved_reasons(obj, "events[0].event", _KNOWN_AUDIT_EVENT_FIELDS, extras)
    assert any("extra_human" in e for e in extras)


# ---------------------------------------------------------------------------
# cmd_verify — no bundle path (line 452-453)
# ---------------------------------------------------------------------------


def test_verify_no_bundle_path_returns_2(capsys: pytest.CaptureFixture[str]) -> None:
    # Pass no positional bundle and no --bundle option to reach the None check
    # We need to bypass argparse, call cmd_verify directly with a fake namespace
    import argparse  # noqa: PLC0415

    from attestplane.cli.main import cmd_verify  # noqa: PLC0415

    args = argparse.Namespace(
        bundle=None,
        bundle_option=None,
        json_output=False,
        require_events=False,
        require_non_empty=False,
        strict_schema=False,
        require_taxonomy_version=None,
        strict_anchoring=False,
        explain=False,
    )
    rc = cmd_verify(args)
    assert rc == 2
    err = capsys.readouterr().err
    assert "bundle path is required" in err


# ---------------------------------------------------------------------------
# cmd_verify --json with strict_anchoring on quarantined bundle (lines 469-473)
# ---------------------------------------------------------------------------


def test_verify_json_strict_anchoring_upgrades_exit_code(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["verify", "--json", "--strict-anchoring", str(QUARANTINE_FIXTURE)])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 1  # upgraded from 2
    assert payload["exit_code"] == 1


# ---------------------------------------------------------------------------
# cmd_verify non-JSON error paths with explain=True
# ---------------------------------------------------------------------------


def test_verify_explain_file_not_found_writes_to_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "no_such_file.json"
    rc = main(["verify", "--explain", str(missing)])
    assert rc == 3
    captured = capsys.readouterr()
    assert "FAIL" in captured.out
    assert "att.verify.schema_invalid" in captured.err
    assert str(missing) in captured.err


def test_verify_no_explain_file_not_found_includes_scope_notice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "no_such_file.json"
    rc = main(["verify", str(missing)])
    assert rc == 3
    out = capsys.readouterr().out
    assert "MODE:" in out


def test_verify_explain_bad_json_writes_to_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    rc = main(["verify", "--explain", str(bad)])
    assert rc == 3
    captured = capsys.readouterr()
    assert "FAIL" in captured.out
    assert "att.verify.schema_invalid" in captured.err


def test_verify_no_explain_bad_json_includes_scope_notice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    rc = main(["verify", str(bad)])
    assert rc == 3
    out = capsys.readouterr().out
    assert "MODE:" in out


def test_verify_explain_bundle_schema_error_human_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    bundle["forbidden_fields"] = ["bad_field"]
    path = tmp_path / "bad_forbidden.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    rc = main(["verify", "--explain", str(path)])
    assert rc == 2
    captured = capsys.readouterr()
    assert "quarantine_reason=" in captured.out
    assert "att.verify" in captured.err


def test_verify_no_explain_bundle_schema_error_adds_scope(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    bundle["forbidden_fields"] = ["bad_field"]
    path = tmp_path / "bad_forbidden.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    rc = main(["verify", str(path)])
    assert rc == 2
    out = capsys.readouterr().out
    assert "MODE:" in out


def test_verify_no_explain_canonicalization_error_adds_scope(capsys: pytest.CaptureFixture[str]) -> None:
    fixture = ROOT / "fixtures" / "reject" / "canonicalization-edge.json"
    rc = main(["verify", str(fixture)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "MODE:" in out


def test_verify_explain_canonicalization_error_writes_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    fixture = ROOT / "fixtures" / "reject" / "canonicalization-edge.json"
    rc = main(["verify", "--explain", str(fixture)])
    assert rc == 1
    captured = capsys.readouterr()
    assert "FAIL" in captured.out
    assert "att.verify.canonical_mismatch" in captured.err


# ---------------------------------------------------------------------------
# cmd_verify non-JSON — taxonomy version failure paths (lines 486-514)
# ---------------------------------------------------------------------------


def test_verify_taxonomy_failure_no_explain_adds_scope(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    rc = main(["verify", "--require-taxonomy-version", "2", str(path)])
    assert rc == 2
    out = capsys.readouterr().out
    assert "taxonomy version pin rejected" in out
    assert "MODE:" in out


def test_verify_taxonomy_failure_explain_writes_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    rc = main(["verify", "--explain", "--require-taxonomy-version", "2", str(path)])
    assert rc == 2
    captured = capsys.readouterr()
    assert "att.verify" in captured.err


def test_verify_taxonomy_failure_chain_metadata_not_dict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad_bundle: dict[str, Any] = {
        "bundle_version": 1,
        "chain_metadata": "not_a_dict",
        "events": [],
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad_bundle), encoding="utf-8")

    rc = main(["verify", "--require-taxonomy-version", "1", str(path)])
    assert rc == 2
    out = capsys.readouterr().out
    assert "taxonomy version pin rejected" in out


def test_verify_taxonomy_failure_non_integer_value(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = ProofBundleBuilder(chain_id="test", producer_runtime="test").build()
    bundle["chain_metadata"]["evidence_taxonomy_version"] = "v1"  # non-integer
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    rc = main(["verify", "--json", "--require-taxonomy-version", "1", str(path)])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["reason_code"] == "att.verify.schema_invalid"


# ---------------------------------------------------------------------------
# cmd_verify non-JSON — result path with explain / error_code stderr
# ---------------------------------------------------------------------------


def test_verify_result_explain_ok_prints_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle_path = _build_bundle(tmp_path, n=2)
    capsys.readouterr()
    rc = main(["verify", "--explain", str(bundle_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "signer_subject=" in out
    assert "schema_version=" in out


def test_verify_result_no_explain_adds_scope(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle_path = _build_bundle(tmp_path, n=2)
    capsys.readouterr()
    rc = main(["verify", str(bundle_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "MODE:" in out


def test_verify_result_fail_explain_writes_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle_path = _build_bundle(tmp_path, n=2)
    # Tamper
    bundle = json.loads(bundle_path.read_text())
    bundle["events"][0]["event"]["payload"] = {"tampered": True}
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    capsys.readouterr()

    rc = main(["verify", "--explain", str(bundle_path)])
    assert rc == 1
    captured = capsys.readouterr()
    assert "FAIL" in captured.out
    assert captured.err != ""


def test_verify_result_require_events_prints_error_code_to_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Empty bundle triggers VERIFY_REQUIRED_FIELDS_MISSING → stderr
    empty_bundle = ProofBundleBuilder(chain_id="empty", producer_runtime="test").build()
    path = tmp_path / "empty.json"
    path.write_text(json.dumps(empty_bundle), encoding="utf-8")
    capsys.readouterr()

    rc = main(["verify", "--require-events", str(path)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "VERIFY_REQUIRED_FIELDS_MISSING" in err


def test_verify_result_strict_anchoring_upgrades_exit_code_non_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(["verify", "--strict-anchoring", str(QUARANTINE_FIXTURE)])
    assert rc == 1  # upgraded from 2
    capsys.readouterr()


# ---------------------------------------------------------------------------
# cmd_verify_proofbundle (lines 690-699)
# ---------------------------------------------------------------------------


def test_verify_proofbundle_basic(capsys: pytest.CaptureFixture[str]) -> None:
    fixture = ROOT / "tests" / "fixtures" / "proofbundle" / "valid_minimal.json"
    rc = main(["verify-proofbundle", str(fixture)])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert "exit_code" in payload
    assert rc == payload["exit_code"]


def test_verify_proofbundle_with_flags(capsys: pytest.CaptureFixture[str]) -> None:
    fixture = ROOT / "tests" / "fixtures" / "proofbundle" / "valid_minimal.json"
    rc = main(["verify-proofbundle", "--verify-signature", "--verify-anchor", str(fixture)])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert "exit_code" in payload
    assert rc == payload["exit_code"]


# ---------------------------------------------------------------------------
# cmd_inspect — JSON output and corrupt chain paths
# ---------------------------------------------------------------------------


def test_inspect_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chain_path = tmp_path / "chain.jsonl"
    _seed_chain(chain_path, n=3)
    rc = main(["inspect", "--json", str(chain_path)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["event_count"] == 3
    assert payload["storage_health"] == "ok"


def test_inspect_json_corrupt_chain(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chain_path = tmp_path / "corrupt.jsonl"
    chain_path.write_text(
        '{"seq": 0, "prev_hash_hex": "' + "0" * 64 + '", "event_hash_hex": "' + "0" * 64 + '", "event": {}}\n'
        "CORRUPT LINE\n",
        encoding="utf-8",
    )
    rc = main(["inspect", "--json", str(chain_path)])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert "issue" in payload


def test_inspect_human_corrupt_chain(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chain_path = tmp_path / "corrupt.jsonl"
    chain_path.write_text(
        '{"seq": 0, "prev_hash_hex": "' + "0" * 64 + '", "event_hash_hex": "' + "0" * 64 + '", "event": {}}\n'
        "CORRUPT LINE\n",
        encoding="utf-8",
    )
    rc = main(["inspect", str(chain_path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "storage corruption" in out


def test_inspect_empty_chain(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chain_path = tmp_path / "empty.jsonl"
    chain_path.write_text("", encoding="utf-8")
    rc = main(["inspect", "--json", str(chain_path)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["head_seq"] == -1
    assert payload["head_hash_hex"] == "0" * 64


def test_inspect_non_json_ok_chain(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Covers the non-JSON human text output path in cmd_inspect (lines 753-762)."""
    chain_path = tmp_path / "chain.jsonl"
    _seed_chain(chain_path, n=2)
    rc = main(["inspect", str(chain_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "path:" in out
    assert "event_count: 2" in out
    assert "head_seq:" in out
    assert "head_hash_hex:" in out
    assert "event_type_histogram:" in out
    assert "verify: OK" in out


def test_inspect_non_json_failed_chain(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Covers the FAIL branch in the non-JSON inspect output (line 759 else branch)."""
    chain_path = tmp_path / "chain.jsonl"
    _seed_chain(chain_path, n=2)
    # Tamper event to break hash chain
    import json as _json
    lines_list = chain_path.read_text(encoding="utf-8").splitlines()
    event = _json.loads(lines_list[0])
    event["event"]["payload"] = {"tampered": True}
    chain_path.write_text("\n".join([_json.dumps(event), lines_list[1]]) + "\n", encoding="utf-8")
    rc = main(["inspect", str(chain_path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "verify: FAIL" in out


# ---------------------------------------------------------------------------
# cmd_export — JSON output and corrupt chain paths
# ---------------------------------------------------------------------------


def test_export_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chain_path = tmp_path / "chain.jsonl"
    bundle_path = tmp_path / "bundle.json"
    _seed_chain(chain_path, n=2)
    rc = main(["export", "--json", str(chain_path), "--out", str(bundle_path)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["event_count"] == 2


def test_export_corrupt_chain_returns_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chain_path = tmp_path / "corrupt.jsonl"
    chain_path.write_text(
        '{"seq": 0, "prev_hash_hex": "' + "0" * 64 + '", "event_hash_hex": "' + "0" * 64 + '", "event": {}}\n'
        "CORRUPT LINE\n",
        encoding="utf-8",
    )
    bundle_path = tmp_path / "out.json"
    rc = main(["export", str(chain_path), "--out", str(bundle_path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "corrupt" in out


def test_export_corrupt_chain_json_mode(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chain_path = tmp_path / "corrupt.jsonl"
    chain_path.write_text(
        '{"seq": 0, "prev_hash_hex": "' + "0" * 64 + '", "event_hash_hex": "' + "0" * 64 + '", "event": {}}\n'
        "CORRUPT LINE\n",
        encoding="utf-8",
    )
    bundle_path = tmp_path / "out.json"
    rc = main(["export", "--json", str(chain_path), "--out", str(bundle_path)])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["storage_health"] == "corrupt"


# ---------------------------------------------------------------------------
# cmd_doctor — ImportError path (lines 858-861)
# ---------------------------------------------------------------------------


def test_doctor_import_error_path(capsys: pytest.CaptureFixture[str]) -> None:
    """Simulate ImportError in the attestplane import block (lines 858-861)."""
    import argparse  # noqa: PLC0415

    from attestplane.cli.main import cmd_doctor  # noqa: PLC0415

    args = argparse.Namespace(json_output=True)

    with mock.patch.dict(
        sys.modules,
        {"attestplane.adapters": None},
    ):
        # With None in sys.modules, "import attestplane.adapters" raises ImportError
        rc = cmd_doctor(args)
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert rc == 1
        assert payload["ok"] is False
        assert payload["imports"] == "failed"
        assert "error" in payload


def test_doctor_eu_ai_act_exception_path(capsys: pytest.CaptureFixture[str]) -> None:
    """Simulate exception in EU AI Act registry load (lines 869-872) — non-JSON path."""
    import argparse  # noqa: PLC0415

    from attestplane.cli.main import cmd_doctor  # noqa: PLC0415

    args = argparse.Namespace(json_output=False)

    with mock.patch(
        "attestplane.obligations.load_eu_ai_act_article_12",
        side_effect=RuntimeError("registry failure"),
    ):
        rc = cmd_doctor(args)
        out = capsys.readouterr().out
        assert rc == 1
        assert "eu_ai_act_art12_entries" in out


def test_doctor_eu_ai_act_real_exception(capsys: pytest.CaptureFixture[str]) -> None:
    """Call cmd_doctor with a patched eu_ai_act load that raises."""
    import argparse  # noqa: PLC0415

    from attestplane.cli.main import cmd_doctor  # noqa: PLC0415

    args = argparse.Namespace(json_output=True)

    with mock.patch(
        "attestplane.cli.main.cmd_doctor",
        wraps=cmd_doctor,
    ), mock.patch(
        "attestplane.obligations.load_eu_ai_act_article_12",
        side_effect=RuntimeError("registry failure"),
    ):
        rc = cmd_doctor(args)
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert rc == 1
        assert payload["ok"] is False
        assert payload["eu_ai_act_art12_entries"] == "failed"
        assert "registry_error" in payload


def test_doctor_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["doctor", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True


def test_doctor_human_output(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["doctor"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "python_version" in out
    assert "attestplane_version" in out


# ---------------------------------------------------------------------------
# Remaining verify sub-flag combinations
# ---------------------------------------------------------------------------


def test_verify_require_non_empty_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    empty_bundle = ProofBundleBuilder(chain_id="empty", producer_runtime="test").build()
    path = tmp_path / "empty.json"
    path.write_text(json.dumps(empty_bundle), encoding="utf-8")
    capsys.readouterr()

    rc = main(["verify", "--require-non-empty", "--json", str(path)])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == "fail"


def test_verify_strict_schema_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bundle_path = _build_bundle(tmp_path, n=1)
    capsys.readouterr()

    rc = main(["verify", "--strict-schema", "--json", str(bundle_path)])
    assert rc == 2  # no signed attestation present
    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == "fail"
    assert payload["reason_code"] == VERIFY_REASON_SIGNATURE_MISSING


def test_verify_both_bundle_positional_and_option(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--bundle option takes precedence over positional bundle argument."""
    bundle_path = _build_bundle(tmp_path, n=1)
    capsys.readouterr()

    # both positional and --bundle given; --bundle triggers strict_bundle_mode
    rc = main(["verify", "--bundle", str(bundle_path), str(bundle_path), "--json"])
    # Should fail due to no signed attestation (strict mode)
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == "fail"
