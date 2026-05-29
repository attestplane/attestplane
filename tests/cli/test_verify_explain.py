# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Snapshot-style coverage for ``attestplane verify --explain``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.proof_bundle import ProofBundleBuilder
from attestplane.verify_errors import (
    VERIFY_BUNDLE_SCHEMA_INCOMPLETE,
    VERIFY_REQUIRED_FIELDS_MISSING,
)
from attestplane.verify_reason_codes import (
    VERIFY_REASON_CANONICAL_MISMATCH,
    VERIFY_REASON_REQUIRED_FIELD_MISSING,
    VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
    VERIFY_REASON_SIGNATURE_MISSING,
    VERIFY_REASON_STRUCTURE_INVALID,
)

ROOT = Path(__file__).resolve().parents[2]
PASS_FIXTURE = ROOT / "fixtures" / "positive" / "minimal.json"
CANONICAL_FIXTURE = ROOT / "fixtures" / "reject" / "canonicalization-edge.json"
SIGNED_FIXTURE = ROOT / "tests" / "fixtures" / "v1.7.0_signed.json"
MISSING_SIGNATURES_FIXTURE = (
    ROOT / "tests" / "fixtures" / "bundles" / "missing_signatures.json"
)

FIXED_SIGNER_SUBJECT = "key_id:4bf5122f344554c53bde2ebb8cd2b7e3"


def _write_bundle(tmp_path: Path, bundle: dict[str, object], *, name: str) -> Path:
    path = tmp_path / name
    path.write_text(
        json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def _run_verify(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def _make_empty_bundle(tmp_path: Path) -> Path:
    bundle = ProofBundleBuilder(chain_id="empty", producer_runtime="test").build()
    return _write_bundle(tmp_path, bundle, name="empty.json")


def _make_schema_version_unsupported_bundle(tmp_path: Path) -> Path:
    bundle = json.loads(SIGNED_FIXTURE.read_text(encoding="utf-8"))
    chain_metadata = bundle["chain_metadata"]
    assert isinstance(chain_metadata, dict)
    chain_metadata["schema_version"] = 2
    return _write_bundle(tmp_path, bundle, name="schema-version-unsupported.json")


def _make_policy_trace_refs_empty_bundle(tmp_path: Path) -> Path:
    bundle = json.loads(SIGNED_FIXTURE.read_text(encoding="utf-8"))
    bundle["policy_trace_refs"] = []
    return _write_bundle(tmp_path, bundle, name="policy-trace-refs-empty.json")


def _make_multi_reason_bundle(tmp_path: Path) -> Path:
    bundle = json.loads(SIGNED_FIXTURE.read_text(encoding="utf-8"))
    chain_metadata = bundle["chain_metadata"]
    assert isinstance(chain_metadata, dict)
    chain_metadata["schema_version"] = 999
    bundle["policy_trace_refs"] = []
    return _write_bundle(tmp_path, bundle, name="multi-reason.json")


def _assert_rationale_lines(
    stderr: str,
    *,
    expected_error_code: str | None,
    reason: str,
    pointer: str,
    message_parts: tuple[str, ...],
) -> None:
    lines = stderr.splitlines()
    if expected_error_code is None:
        assert len(lines) >= 1
        rationale_line = lines[0]
    else:
        assert len(lines) >= 2
        assert lines[0] == expected_error_code
        rationale_line = lines[1]
    assert rationale_line.startswith(f"{reason} {pointer}: ")
    for part in message_parts:
        assert part in rationale_line


def _assert_failure_summary(
    stdout: str, *, signer_subject: str, schema_version: str
) -> None:
    assert stdout.strip() == (
        f"FAIL signer_subject={signer_subject} schema_version={schema_version} "
        f"taxonomy_version=1 anchor=absent"
    )


def _assert_pass_summary(stdout: str, *, signer_subject: str) -> None:
    assert stdout.strip() == (
        f"OK signer_subject={signer_subject} schema_version=1 taxonomy_version=1 anchor=absent"
    )


def test_verify_explain_writes_pointer_bearing_rationale_lines(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    empty_bundle = _make_empty_bundle(tmp_path)
    schema_unsupported_bundle = _make_schema_version_unsupported_bundle(tmp_path)
    policy_trace_refs_empty_bundle = _make_policy_trace_refs_empty_bundle(tmp_path)

    cases = [
        (
            ["verify", "--explain", str(CANONICAL_FIXTURE)],
            1,
            FIXED_SIGNER_SUBJECT,
            "1",
            None,
            "generic",
            (
                VERIFY_REASON_CANONICAL_MISMATCH,
                "/events/0/event/payload/artifact_ref",
                ("Unicode-NFC",),
            ),
        ),
        (
            ["verify", "--require-non-empty", "--explain", str(empty_bundle)],
            2,
            "none",
            "1",
            VERIFY_REQUIRED_FIELDS_MISSING,
            "compact",
            (
                VERIFY_REASON_REQUIRED_FIELD_MISSING,
                "/events",
                ("at least one event",),
            ),
        ),
        (
            ["verify", "--strict-schema", "--explain", str(MISSING_SIGNATURES_FIXTURE)],
            2,
            "none",
            "1",
            VERIFY_BUNDLE_SCHEMA_INCOMPLETE,
            "compact",
            (
                VERIFY_REASON_SIGNATURE_MISSING,
                "/signatures",
                ("at least one signed attestation",),
            ),
        ),
        (
            ["verify", "--explain", str(schema_unsupported_bundle)],
            2,
            FIXED_SIGNER_SUBJECT,
            "2",
            None,
            "compact",
            (
                VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
                "/chain_metadata/schema_version",
                ("chain_metadata.schema_version=2", "schema_version values (1,)"),
            ),
        ),
        (
            ["verify", "--explain", str(policy_trace_refs_empty_bundle)],
            1,
            FIXED_SIGNER_SUBJECT,
            "1",
            None,
            "compact",
            (
                VERIFY_REASON_STRUCTURE_INVALID,
                "/policy_trace_refs",
                ("must be absent, not empty",),
            ),
        ),
    ]

    for argv, expected_rc, signer_subject, schema_version, error_code, stdout_kind, (
        reason,
        pointer,
        message_parts,
    ) in cases:
        rc, stdout, stderr = _run_verify(argv, capsys)

        assert rc == expected_rc
        if stdout_kind == "compact":
            _assert_failure_summary(
                stdout, signer_subject=signer_subject, schema_version=schema_version
            )
        else:
            assert stdout.startswith("FAIL: canonicalization error in ")
        _assert_rationale_lines(
            stderr,
            expected_error_code=error_code,
            reason=reason,
            pointer=pointer,
            message_parts=message_parts,
        )


def test_verify_explain_canonicalization_failure_summary_is_generic(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, stdout, stderr = _run_verify(
        ["verify", "--explain", str(CANONICAL_FIXTURE)], capsys
    )

    assert rc == 1
    assert stdout.startswith("FAIL: canonicalization error in ")
    assert stderr.splitlines()[0].startswith(
        f"{VERIFY_REASON_CANONICAL_MISMATCH} /events/0/event/payload/artifact_ref: "
    )


def test_verify_explain_plain_text_emits_all_rejection_rationales(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    multi_reason_bundle = _make_multi_reason_bundle(tmp_path)

    rc_json, stdout_json, stderr_json = _run_verify(
        ["verify", "--json", "--explain", str(multi_reason_bundle)],
        capsys,
    )
    payload = json.loads(stdout_json)
    explanations = payload["explanation"]
    assert rc_json == 2
    assert stderr_json == ""
    assert isinstance(explanations, list)
    assert len(explanations) > 1

    expected_lines = [
        f"{entry['primary_reason'] or 'ok'} {entry['pointer']}: {entry['message']}"
        for entry in explanations
    ]

    rc, stdout, stderr = _run_verify(
        ["verify", "--explain", str(multi_reason_bundle)], capsys
    )

    assert rc == 2
    assert stdout.startswith("FAIL signer_subject=")
    assert "schema_version=999" in stdout
    assert "taxonomy_version=1" in stdout
    assert stderr.splitlines() == expected_lines


def test_verify_explain_compact_success_summary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, stdout, stderr = _run_verify(["verify", "--explain", str(PASS_FIXTURE)], capsys)

    assert rc == 0
    assert stderr == ""
    _assert_pass_summary(stdout, signer_subject=FIXED_SIGNER_SUBJECT)


def test_verify_explain_json_emits_explanation_array_for_success(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, stdout, stderr = _run_verify(
        ["verify", "--json", "--explain", str(PASS_FIXTURE)], capsys
    )
    payload = json.loads(stdout)

    assert rc == 0
    assert stderr == ""
    explanation = payload["explanation"]
    assert isinstance(explanation, list)
    assert len(explanation) == 1
    summary = explanation[0]
    assert summary["primary_reason"] is None
    assert summary["pointer"] == "/"
    assert summary["message"] == (
        f"signer_subject={FIXED_SIGNER_SUBJECT} schema_version=1 taxonomy_version=1 anchor=absent"
    )


def test_verify_explain_remains_orthogonal_to_strict_flags(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    empty_bundle = _make_empty_bundle(tmp_path)
    schema_unsupported_bundle = _make_schema_version_unsupported_bundle(tmp_path)

    rc_non_empty, stdout_non_empty, stderr_non_empty = _run_verify(
        ["verify", "--json", "--explain", "--require-non-empty", str(empty_bundle)],
        capsys,
    )
    payload_non_empty = json.loads(stdout_non_empty)
    assert rc_non_empty == 2
    assert payload_non_empty["reason_code"] == VERIFY_REASON_REQUIRED_FIELD_MISSING
    assert (
        payload_non_empty["explanation"][0]["primary_reason"]
        == VERIFY_REASON_REQUIRED_FIELD_MISSING
    )
    assert payload_non_empty["explanation"][0]["pointer"] == "/events"
    assert stderr_non_empty == f"{VERIFY_REQUIRED_FIELDS_MISSING}\n"

    rc_strict, stdout_strict, stderr_strict = _run_verify(
        [
            "verify",
            "--json",
            "--explain",
            "--strict-schema",
            str(MISSING_SIGNATURES_FIXTURE),
        ],
        capsys,
    )
    payload_strict = json.loads(stdout_strict)
    assert rc_strict == 2
    assert payload_strict["reason_code"] == VERIFY_REASON_SIGNATURE_MISSING
    assert (
        payload_strict["explanation"][0]["primary_reason"]
        == VERIFY_REASON_SIGNATURE_MISSING
    )
    assert payload_strict["explanation"][0]["pointer"] == "/signatures"
    assert stderr_strict == f"{VERIFY_BUNDLE_SCHEMA_INCOMPLETE}\n"

    rc_schema, stdout_schema, stderr_schema = _run_verify(
        ["verify", "--json", "--explain", str(schema_unsupported_bundle)],
        capsys,
    )
    payload_schema = json.loads(stdout_schema)
    assert rc_schema == 2
    assert payload_schema["reason_code"] == VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED
    assert (
        payload_schema["explanation"][0]["primary_reason"]
        == VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED
    )
    assert (
        payload_schema["explanation"][0]["pointer"] == "/chain_metadata/schema_version"
    )
    assert stderr_schema == ""
