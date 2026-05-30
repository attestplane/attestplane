# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ``attestplane`` CLI entry-point."""

from __future__ import annotations

import json
import runpy
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.storage.jsonl import JsonlStorageBackend
from attestplane.types import ChainHead, EventDraft
from attestplane.verify_reason_codes import (
    VERIFY_REASON_REQUIRED_FIELD_MISSING,
    VERIFY_REASON_SCHEMA_VERSION_MISSING,
    VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
    VERIFY_REASON_SIGNATURE_MISSING,
)

ROOT = Path(__file__).resolve().parents[4]


def _seed_jsonl_chain(path: Path, n: int = 3) -> None:
    backend = JsonlStorageBackend(path)
    head = genesis_head()
    ts = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    for i in range(n):
        draft = EventDraft(
            event_type="eval_event",
            actor=f"agent://test/{i}",
            payload={"index": i},
        )
        event = chain_extend(head, draft, now=ts, event_id=f"00000000-0000-7000-8000-{i:012d}")
        backend.append(event)
        head = ChainHead(seq=event.seq, event_hash=event.event_hash)
    backend.close()


def test_no_args_exits_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code != 0


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "attestplane" in out


def test_verify_help_declares_partial_scope(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["verify", "--help"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    normalized = " ".join(out.split())
    assert "chain/report-oriented" in normalized
    assert "not a full verifier" in normalized
    assert "policy_trace_refs closure" in normalized
    assert "signature verification" in normalized
    assert "anchor verification" in normalized
    assert "--require-taxonomy-version" in normalized


def test_doctor_command(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["doctor"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "python_version" in out
    assert "attestplane_version" in out


def test_doctor_command_json(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["doctor", "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["imports"] == "ok"
    assert payload["eu_ai_act_art12_entries"] == 8
    assert payload["storage"]["jsonl_backend_available"] is True
    assert payload["storage"]["multi_writer_safe"] is False
    assert payload["storage"]["concurrent_append_behavior"] == "single_process_thread_lock_only"


def test_export_then_verify_roundtrip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chain_path = tmp_path / "chain.jsonl"
    bundle_path = tmp_path / "bundle.json"
    _seed_jsonl_chain(chain_path, n=3)

    rc = main(
        [
            "export",
            str(chain_path),
            "--out",
            str(bundle_path),
            "--chain-id",
            "demo",
            "--producer-runtime",
            "demo-runtime",
        ]
    )
    assert rc == 0
    assert bundle_path.exists()

    capsys.readouterr()  # clear

    rc = main(["verify", str(bundle_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.startswith("OK")
    assert "'demo'" in out
    assert "MODE: chain/report-oriented, not a full verifier" in out
    assert "policy_trace_refs closure" in out


def test_export_then_verify_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chain_path = tmp_path / "chain.jsonl"
    bundle_path = tmp_path / "bundle.json"
    _seed_jsonl_chain(chain_path, n=2)

    main(["export", str(chain_path), "--out", str(bundle_path)])
    capsys.readouterr()

    rc = main(["verify", str(bundle_path), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == 1
    assert payload["result"] == "pass"
    assert payload["exit_code"] == 0
    assert payload["reason_code"] is None
    assert payload["taxonomy_version"] == 1
    assert payload["reasons"] == []
    assert payload["bundle"]["schema_version"] == 1
    assert payload["bundle"]["digest"]


def test_verify_explain_legacy_bundle_reports_stable_taxonomy_version(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle_path = ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    del payload["chain_metadata"]["evidence_taxonomy_version"]
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    rc = main(["verify", "--explain", str(path)])
    captured = capsys.readouterr()

    assert rc == 0
    assert "taxonomy_version=1" in captured.out
    assert captured.err == ""


def test_verify_require_events_rejects_empty_bundle(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chain_path = tmp_path / "empty.jsonl"
    bundle_path = tmp_path / "empty-bundle.json"
    chain_path.write_text("", encoding="utf-8")

    assert main(["export", str(chain_path), "--out", str(bundle_path)]) == 0
    capsys.readouterr()

    rc = main(["verify", str(bundle_path), "--require-events", "--json"])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == 1
    assert payload["result"] == "fail"
    assert payload["exit_code"] == 2
    assert payload["reason_code"] == VERIFY_REASON_REQUIRED_FIELD_MISSING
    assert payload["taxonomy_version"] == 1
    assert payload["reasons"][0]["code"] == VERIFY_REASON_REQUIRED_FIELD_MISSING


@pytest.mark.parametrize(
    ("taxonomy_version", "mutate", "expected_rc", "expected_reason"),
    [
        (1, None, 0, None),
        (2, None, 2, VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED),
        (1, "remove", 2, VERIFY_REASON_SCHEMA_VERSION_MISSING),
    ],
)
def test_verify_require_taxonomy_version_pins_bundle_taxonomy_version(
    taxonomy_version: int,
    mutate: str | None,
    expected_rc: int,
    expected_reason: str | None,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle_path = ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    if mutate == "remove":
        del payload["chain_metadata"]["evidence_taxonomy_version"]
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    rc = main(
        [
            "verify",
            "--json",
            str(path),
            "--require-taxonomy-version",
            str(taxonomy_version),
        ]
    )
    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert rc == expected_rc
    assert captured.err == ""
    assert result["schema_version"] == 1
    assert result["exit_code"] == expected_rc
    assert result["taxonomy_version"] == 1
    assert result["result"] == ("pass" if expected_rc == 0 else "fail")
    if expected_reason is None:
        assert result["reason_code"] is None
        assert result["reasons"] == []
    else:
        assert result["reason_code"] == expected_reason
        assert result["reasons"][0]["code"] == expected_reason
        assert result["reasons"][0]["path"] == "/chain_metadata/evidence_taxonomy_version"


def test_verify_bundle_option_rejects_unsigned_bundle(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chain_path = tmp_path / "chain.jsonl"
    bundle_path = tmp_path / "bundle.json"
    _seed_jsonl_chain(chain_path, n=1)
    assert main(["export", str(chain_path), "--out", str(bundle_path)]) == 0
    capsys.readouterr()

    rc = main(["verify", "--bundle", str(bundle_path), "--json"])

    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == 1
    assert payload["result"] == "fail"
    assert payload["exit_code"] == 2
    assert payload["reason_code"] == VERIFY_REASON_SIGNATURE_MISSING
    assert payload["taxonomy_version"] == 1
    assert payload["reasons"][0]["code"] == VERIFY_REASON_SIGNATURE_MISSING


def test_module_entrypoint_dispatches_main(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["attestplane.cli", "--version"])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("attestplane.cli", run_name="__main__")

    assert exc_info.value.code == 0


def test_verify_detects_tampered_bundle(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chain_path = tmp_path / "chain.jsonl"
    bundle_path = tmp_path / "bundle.json"
    _seed_jsonl_chain(chain_path, n=3)
    main(["export", str(chain_path), "--out", str(bundle_path)])

    # Tamper with the bundle.
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle["events"][1]["event"]["payload"] = {"index": 999}
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

    capsys.readouterr()
    rc = main(["verify", str(bundle_path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert out.startswith("FAIL")


def test_verify_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["verify", str(tmp_path / "missing.json")])
    assert rc == 3
    out = capsys.readouterr().out
    assert "FAIL" in out


def test_verify_malformed_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    rc = main(["verify", str(bad)])
    assert rc == 3


def test_inspect_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chain_path = tmp_path / "chain.jsonl"
    _seed_jsonl_chain(chain_path, n=4)

    rc = main(["inspect", str(chain_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "event_count: 4" in out
    assert "verify: OK" in out


def test_inspect_command_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chain_path = tmp_path / "chain.jsonl"
    _seed_jsonl_chain(chain_path, n=2)

    rc = main(["inspect", str(chain_path), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["event_count"] == 2
    assert payload["ok"] is True
    assert payload["event_type_histogram"] == {"eval_event": 2}


def test_inspect_malformed_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.jsonl"
    bad.write_text("not valid json\n", encoding="utf-8")
    rc = main(["inspect", str(bad)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "storage corruption" in out


def test_inspect_partial_jsonl_reports_storage_corruption_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    chain_path = tmp_path / "chain.jsonl"
    _seed_jsonl_chain(chain_path, n=1)
    chain_path.write_bytes(chain_path.read_bytes() + b'{"seq":1')

    rc = main(["inspect", str(chain_path), "--json"])

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"] == "storage_corruption"
    assert payload["storage_health"] == "corrupt"
    assert payload["valid_prefix_event_count"] == 1
    assert payload["issue"]["kind"] == "partial_trailing_line"


def test_export_command_emits_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chain_path = tmp_path / "chain.jsonl"
    bundle_path = tmp_path / "out" / "bundle.json"  # nested path triggers mkdir
    _seed_jsonl_chain(chain_path, n=2)

    rc = main(["export", str(chain_path), "--out", str(bundle_path)])
    assert rc == 0
    assert bundle_path.exists()
    out = capsys.readouterr().out
    assert "wrote" in out
    assert "2 events" in out


def test_export_refuses_corrupt_jsonl(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chain_path = tmp_path / "chain.jsonl"
    bundle_path = tmp_path / "bundle.json"
    _seed_jsonl_chain(chain_path, n=1)
    chain_path.write_text(chain_path.read_text(encoding="utf-8") + "not valid json\n", encoding="utf-8")

    rc = main(["export", str(chain_path), "--out", str(bundle_path), "--json"])

    assert rc == 1
    assert not bundle_path.exists()
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"] == "storage_corruption"
    assert payload["valid_prefix_event_count"] == 1
    assert payload["issue"]["kind"] == "malformed_json"
