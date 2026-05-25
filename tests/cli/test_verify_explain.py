# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Snapshot-style coverage for ``attestplane verify --explain``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

from attestplane.cli.main import main
from attestplane.proof_bundle import ProofBundleBuilder
from attestplane.verify_reason_codes import (
    VERIFY_REASON_CODE_DESCRIPTIONS,
    VERIFY_REASON_CANONICAL_MISMATCH,
    VERIFY_REASON_REQUIRED_FIELD_MISSING,
    VERIFY_REASON_SCHEMA_INVALID,
    VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
    VERIFY_REASON_SIGNATURE_MISSING,
    VERIFY_REASON_STRUCTURE_INVALID,
)
from attestplane.verify_errors import VERIFY_BUNDLE_SCHEMA_INCOMPLETE, VERIFY_REQUIRED_FIELDS_MISSING

ROOT = Path(__file__).resolve().parents[2]
CANONICAL_FIXTURE = ROOT / "fixtures" / "reject" / "canonicalization-edge.json"
MALFORMED_FIXTURE = ROOT / "tests" / "fixtures" / "proofbundle" / "malformed.json"
SIGNED_FIXTURE = ROOT / "tests" / "fixtures" / "v1.7.0_signed.json"
MISSING_SIGNATURES_FIXTURE = ROOT / "tests" / "fixtures" / "bundles" / "missing_signatures.json"

CaseBuilder = Callable[[Path], tuple[list[str], int, list[str], list[str]]]


def _write_bundle(tmp_path: Path, bundle: dict[str, object], *, name: str) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _case_canonical_mismatch(_: Path) -> tuple[list[str], int, list[str], list[str]]:
    return (
        ["verify", "--explain", str(CANONICAL_FIXTURE)],
        1,
        [VERIFY_REASON_CANONICAL_MISMATCH],
        [
            f"{VERIFY_REASON_CANONICAL_MISMATCH}: "
            f"{VERIFY_REASON_CODE_DESCRIPTIONS[VERIFY_REASON_CANONICAL_MISMATCH]}"
        ],
    )


def _case_schema_invalid(_: Path) -> tuple[list[str], int, list[str], list[str]]:
    return (
        ["verify", "--explain", str(MALFORMED_FIXTURE)],
        2,
        [VERIFY_REASON_SCHEMA_INVALID],
        [
            f"{VERIFY_REASON_SCHEMA_INVALID}: "
            f"{VERIFY_REASON_CODE_DESCRIPTIONS[VERIFY_REASON_SCHEMA_INVALID]}"
        ],
    )


def _case_required_field_missing(tmp_path: Path) -> tuple[list[str], int, list[str], list[str]]:
    bundle = ProofBundleBuilder(chain_id="empty", producer_runtime="test").build()
    path = _write_bundle(tmp_path, bundle, name="empty.json")
    return (
        ["verify", "--require-events", "--explain", str(path)],
        2,
        [VERIFY_REASON_REQUIRED_FIELD_MISSING],
        [
            VERIFY_REQUIRED_FIELDS_MISSING,
            f"{VERIFY_REASON_REQUIRED_FIELD_MISSING}: "
            f"{VERIFY_REASON_CODE_DESCRIPTIONS[VERIFY_REASON_REQUIRED_FIELD_MISSING]}",
            f"{VERIFY_REASON_STRUCTURE_INVALID}: "
            f"{VERIFY_REASON_CODE_DESCRIPTIONS[VERIFY_REASON_STRUCTURE_INVALID]}",
        ],
    )


def _case_signature_missing(_: Path) -> tuple[list[str], int, list[str], list[str]]:
    return (
        ["verify", "--bundle", str(MISSING_SIGNATURES_FIXTURE), "--explain"],
        2,
        [VERIFY_REASON_SIGNATURE_MISSING],
        [
            VERIFY_BUNDLE_SCHEMA_INCOMPLETE,
            f"{VERIFY_REASON_SIGNATURE_MISSING}: "
            f"{VERIFY_REASON_CODE_DESCRIPTIONS[VERIFY_REASON_SIGNATURE_MISSING]}",
        ],
    )


def _case_schema_version_unsupported(tmp_path: Path) -> tuple[list[str], int, list[str], list[str]]:
    bundle = json.loads(SIGNED_FIXTURE.read_text(encoding="utf-8"))
    chain_metadata = bundle["chain_metadata"]
    assert isinstance(chain_metadata, dict)
    chain_metadata["schema_version"] = 2
    path = _write_bundle(tmp_path, bundle, name="unsupported-version.json")
    return (
        ["verify", "--explain", str(path)],
        1,
        [VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED],
        [
            f"{VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED}: "
            f"{VERIFY_REASON_CODE_DESCRIPTIONS[VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED]}"
        ],
    )


def _case_structure_invalid(tmp_path: Path) -> tuple[list[str], int, list[str], list[str]]:
    bundle = json.loads(SIGNED_FIXTURE.read_text(encoding="utf-8"))
    bundle["policy_trace_refs"] = []
    path = _write_bundle(tmp_path, bundle, name="structure-invalid.json")
    return (
        ["verify", "--explain", str(path)],
        1,
        [VERIFY_REASON_STRUCTURE_INVALID],
        [
            f"{VERIFY_REASON_STRUCTURE_INVALID}: "
            f"{VERIFY_REASON_CODE_DESCRIPTIONS[VERIFY_REASON_STRUCTURE_INVALID]}"
        ],
    )


def _case_multi_reason_order(tmp_path: Path) -> tuple[list[str], int, list[str], list[str]]:
    bundle = json.loads(SIGNED_FIXTURE.read_text(encoding="utf-8"))
    events = bundle["events"]
    assert isinstance(events, list)
    events[0]["event_hash_hex"] = "f" * 64  # type: ignore[index]
    bundle["policy_trace_refs"] = []
    path = _write_bundle(tmp_path, bundle, name="multi-reason.json")
    return (
        ["verify", "--bundle", str(path), "--explain"],
        1,
        [
            VERIFY_REASON_CANONICAL_MISMATCH,
            VERIFY_REASON_STRUCTURE_INVALID,
            VERIFY_REASON_STRUCTURE_INVALID,
        ],
        [
            f"{VERIFY_REASON_CANONICAL_MISMATCH}: "
            f"{VERIFY_REASON_CODE_DESCRIPTIONS[VERIFY_REASON_CANONICAL_MISMATCH]}",
            f"{VERIFY_REASON_STRUCTURE_INVALID}: "
            f"{VERIFY_REASON_CODE_DESCRIPTIONS[VERIFY_REASON_STRUCTURE_INVALID]}",
            f"{VERIFY_REASON_STRUCTURE_INVALID}: "
            f"{VERIFY_REASON_CODE_DESCRIPTIONS[VERIFY_REASON_STRUCTURE_INVALID]}",
        ],
    )


HUMAN_CASES: list[tuple[str, CaseBuilder]] = [
    ("canonical mismatch", _case_canonical_mismatch),
    ("schema invalid", _case_schema_invalid),
    ("required field missing", _case_required_field_missing),
    ("signature missing", _case_signature_missing),
    ("schema version unsupported", _case_schema_version_unsupported),
    ("structure invalid", _case_structure_invalid),
]


def _run_verify(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


@pytest.mark.parametrize("case_name, case_builder", HUMAN_CASES, ids=[name for name, _ in HUMAN_CASES])
def test_verify_explain_writes_rationale_lines_to_stderr(
    case_name: str,
    case_builder: CaseBuilder,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv, expected_rc, _, expected_stderr_lines = case_builder(tmp_path)

    rc, stdout, stderr = _run_verify(argv, capsys)

    assert rc == expected_rc, case_name
    assert stdout.startswith("FAIL") or stdout.startswith("OK")
    assert stderr.splitlines() == expected_stderr_lines


def test_verify_explain_embeds_reason_explanations_in_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv, expected_rc, expected_codes, expected_stderr_lines = _case_multi_reason_order(tmp_path)
    argv = argv[:]
    argv.insert(1, "--json")

    rc, stdout, stderr = _run_verify(argv, capsys)
    payload = json.loads(stdout)

    assert rc == expected_rc
    assert stderr == ""
    assert payload["reason_code"] == expected_codes[0]
    assert payload["taxonomy_version"] == 1
    assert [reason["code"] for reason in payload["reasons"]] == expected_codes
    assert [reason["explanation"] for reason in payload["reasons"]] == [
        line.split(": ", 1)[1] for line in expected_stderr_lines
    ]


def test_verify_json_and_explain_share_primary_reason_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    json_rc, json_stdout, json_stderr = _run_verify(["verify", "--json", str(CANONICAL_FIXTURE)], capsys)
    json_payload = json.loads(json_stdout)

    assert json_rc == 1
    assert json_stderr == ""
    assert json_payload["reason_code"] == VERIFY_REASON_CANONICAL_MISMATCH
    assert json_payload["taxonomy_version"] == 1

    explain_rc, explain_stdout, explain_stderr = _run_verify(
        ["verify", "--explain", str(CANONICAL_FIXTURE)],
        capsys,
    )

    assert explain_rc == 1
    assert explain_stdout.startswith("FAIL")
    assert explain_stderr.splitlines()[0] == (
        f"{json_payload['reason_code']}: "
        f"{VERIFY_REASON_CODE_DESCRIPTIONS[VERIFY_REASON_CANONICAL_MISMATCH]}"
    )
