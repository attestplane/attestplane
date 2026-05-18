# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ``attestplane`` CLI entry-point."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.storage.jsonl import JsonlStorageBackend
from attestplane.types import ChainHead, EventDraft


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
        event = chain_extend(head, draft, now=ts,
                             event_id=f"00000000-0000-7000-8000-{i:012d}")
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


def test_export_then_verify_roundtrip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    chain_path = tmp_path / "chain.jsonl"
    bundle_path = tmp_path / "bundle.json"
    _seed_jsonl_chain(chain_path, n=3)

    rc = main(["export", str(chain_path), "--out", str(bundle_path),
               "--chain-id", "demo", "--producer-runtime", "demo-runtime"])
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


def test_export_then_verify_json_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    chain_path = tmp_path / "chain.jsonl"
    bundle_path = tmp_path / "bundle.json"
    _seed_jsonl_chain(chain_path, n=2)

    main(["export", str(chain_path), "--out", str(bundle_path)])
    capsys.readouterr()

    rc = main(["verify", str(bundle_path), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["event_count"] == 2
    assert payload["verification_scope"] == "chain_report_only"
    assert payload["full_proof_bundle_verification"] is False
    assert payload["proof_bundle_metadata_closure_performed"] is True
    assert payload["policy_trace_refs_verification_performed"] is True
    assert payload["signature_verification_performed"] is False
    assert payload["anchor_verification_performed"] is False
    assert payload["compliance_certification"] is False
    assert "not a full verifier" in payload["warning"]


def test_verify_detects_tampered_bundle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
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


def test_verify_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["verify", str(tmp_path / "missing.json")])
    assert rc == 1
    out = capsys.readouterr().out
    assert "FAIL" in out


def test_verify_malformed_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    rc = main(["verify", str(bad)])
    assert rc == 1


def test_inspect_command(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    chain_path = tmp_path / "chain.jsonl"
    _seed_jsonl_chain(chain_path, n=4)

    rc = main(["inspect", str(chain_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "event_count: 4" in out
    assert "verify: OK" in out


def test_inspect_command_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    chain_path = tmp_path / "chain.jsonl"
    _seed_jsonl_chain(chain_path, n=2)

    rc = main(["inspect", str(chain_path), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["event_count"] == 2
    assert payload["ok"] is True
    assert payload["event_type_histogram"] == {"eval_event": 2}


def test_inspect_malformed_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.jsonl"
    bad.write_text("not valid json\n", encoding="utf-8")
    rc = main(["inspect", str(bad)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "FAIL" in out


def test_export_command_emits_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    chain_path = tmp_path / "chain.jsonl"
    bundle_path = tmp_path / "out" / "bundle.json"  # nested path triggers mkdir
    _seed_jsonl_chain(chain_path, n=2)

    rc = main(["export", str(chain_path), "--out", str(bundle_path)])
    assert rc == 0
    assert bundle_path.exists()
    out = capsys.readouterr().out
    assert "wrote" in out
    assert "2 events" in out
