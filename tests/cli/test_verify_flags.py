# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Issue #138 integration tests for ``attestplane verify`` strict flags."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.cli.verify_json import VERIFY_EXIT_CODE_PINNING_MISMATCH
from attestplane.verify_reason_codes import (
    VERIFY_REASON_CANONICAL_MISMATCH,
    VERIFY_REASON_SCHEMA_INVALID,
    VERIFY_REASON_SCHEMA_UNKNOWN,
)
from attestplane.verify_errors import (
    VERIFY_BUNDLE_SCHEMA_INCOMPLETE,
    VERIFY_REQUIRED_FIELDS_MISSING,
)
from attestplane.verify_reason_codes import (
    VERIFY_REASON_SCHEMA_VERSION_MISSING,
    VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"
VALID_SIGNED = FIXTURES / "v1.7.0_signed.json"
EMPTY_BUNDLE = FIXTURES / "empty_bundle.json"
SIGNED_BUNDLE = (
    ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"
)
PASS_FIXTURE = ROOT / "fixtures" / "valid_bundle.att"
FAIL_FIXTURE = ROOT / "fixtures" / "reject" / "canonicalization-edge.json"
QUARANTINE_FIXTURE = ROOT / "fixtures" / "anchoring" / "quarantine_timeout.att"


@pytest.mark.parametrize(
    ("flags", "valid_rc", "invalid_rc", "invalid_code"),
    [
        ([], 0, 0, None),
        (["--require-non-empty"], 0, 2, VERIFY_REQUIRED_FIELDS_MISSING),
        (["--strict-schema"], 0, 2, VERIFY_BUNDLE_SCHEMA_INCOMPLETE),
        (
            ["--require-non-empty", "--strict-schema"],
            0,
            2,
            VERIFY_REQUIRED_FIELDS_MISSING,
        ),
    ],
)
def test_verify_strict_flag_combinations(
    flags: list[str],
    valid_rc: int,
    invalid_rc: int,
    invalid_code: str | None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(["verify", str(VALID_SIGNED), *flags, "--json"])
    valid = json.loads(capsys.readouterr().out)

    assert rc == valid_rc
    assert valid["schema_version"] == 1
    assert valid["result"] == ("pass" if valid_rc == 0 else "fail")
    assert valid["exit_code"] == valid_rc
    assert valid["bundle"]["schema_version"] == 1

    rc = main(["verify", str(EMPTY_BUNDLE), *flags, "--json"])
    captured = capsys.readouterr()
    invalid = json.loads(captured.out)

    assert rc == invalid_rc
    assert invalid["schema_version"] == 1
    assert invalid["exit_code"] == invalid_rc
    if invalid_code is None:
        assert invalid["result"] == "pass"
        assert invalid["reasons"] == []
        assert captured.err == ""
    else:
        assert invalid["result"] == "fail"
        assert invalid["reasons"]
        assert captured.err == f"{invalid_code}\n"


def test_verify_help_lists_strict_flags_and_exit_codes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["verify", "--help"])

    assert exc_info.value.code == 0
    out = " ".join(capsys.readouterr().out.split())
    assert "--require-non-empty" in out
    assert "--strict-schema" in out
    assert "--require-taxonomy-version" in out
    assert "--explain" in out
    assert "proof-bundle contract" in out
    assert "0 success" in out
    assert "1 verification failure" in out
    assert "2 quarantine" in out
    assert "3 usage" in out
    assert "4 taxonomy pin mismatch" in out


@pytest.mark.parametrize(
    ("case_id", "argv", "expected_rc", "expected_exit_code", "expected_reason_code"),
    [
        pytest.param(
            "pass",
            ["verify", "--json", str(PASS_FIXTURE)],
            0,
            0,
            None,
            id="pass",
        ),
        pytest.param(
            "canonical_mismatch",
            ["verify", "--json", str(FAIL_FIXTURE)],
            1,
            1,
            VERIFY_REASON_CANONICAL_MISMATCH,
            id="canonical_mismatch",
        ),
        pytest.param(
            "quarantine",
            ["verify", "--json", str(QUARANTINE_FIXTURE)],
            2,
            2,
            VERIFY_REASON_SCHEMA_UNKNOWN,
            id="quarantine",
        ),
        pytest.param(
            "taxonomy_pinning_mismatch",
            [
                "verify",
                "--json",
                str(PASS_FIXTURE),
                "--require-taxonomy-version",
                "2",
            ],
            VERIFY_EXIT_CODE_PINNING_MISMATCH,
            VERIFY_EXIT_CODE_PINNING_MISMATCH,
            VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
            id="taxonomy_pinning_mismatch",
        ),
        pytest.param(
            "usage_error",
            ["verify", "--json", str(FIXTURES / "missing-bundle.json")],
            3,
            3,
            VERIFY_REASON_SCHEMA_INVALID,
            id="usage_error",
        ),
    ],
)
def test_verify_json_exit_code_contract_table(
    case_id: str,
    argv: list[str],
    expected_rc: int,
    expected_exit_code: int,
    expected_reason_code: str | None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(argv)
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == expected_rc
    assert payload["schema_version"] == 1
    assert payload["exit_code"] == expected_exit_code
    assert payload["result"] == ("pass" if expected_exit_code == 0 else "fail")
    if case_id == "quarantine":
        assert payload["anchoring"] == {"status": "quarantined", "quarantined": True}
    if expected_reason_code is None:
        assert payload["reason_code"] is None
    else:
        assert payload["reason_code"] == expected_reason_code


@pytest.mark.parametrize(
    ("taxonomy_version", "mutate", "expected_rc", "expected_reason"),
    [
        (1, None, 0, None),
        (
            2,
            None,
            VERIFY_EXIT_CODE_PINNING_MISMATCH,
            VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
        ),
        (
            1,
            "remove",
            VERIFY_EXIT_CODE_PINNING_MISMATCH,
            VERIFY_REASON_SCHEMA_VERSION_MISSING,
        ),
    ],
)
def test_verify_require_taxonomy_version_pin(
    taxonomy_version: int,
    mutate: str | None,
    expected_rc: int,
    expected_reason: str | None,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = json.loads(VALID_SIGNED.read_text(encoding="utf-8"))
    if mutate == "remove":
        del bundle["chain_metadata"]["evidence_taxonomy_version"]
    path = tmp_path / "taxonomy-version.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    rc = main(
        [
            "verify",
            str(path),
            "--require-taxonomy-version",
            str(taxonomy_version),
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == expected_rc
    assert payload["schema_version"] == 1
    assert payload["exit_code"] == expected_rc
    assert payload["taxonomy_version"] == 1
    assert payload["result"] == ("pass" if expected_rc == 0 else "fail")
    if expected_reason is None:
        assert payload["reason_code"] is None
        assert payload["reasons"] == []
    else:
        assert payload["reason_code"] == expected_reason
        assert payload["reasons"][0]["code"] == expected_reason
        assert (
            payload["reasons"][0]["path"] == "/chain_metadata/evidence_taxonomy_version"
        )
    assert captured.err == ""


def test_verify_explain_surfaces_reserved_reason_for_additive_fields(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = json.loads(SIGNED_BUNDLE.read_text(encoding="utf-8"))
    bundle["future_bundle_field"] = {"preserved": True}
    bundle["chain_metadata"]["future_metadata_field"] = "kept"
    bundle["verification_report"]["future_report_field"] = "ignored"
    bundle["events"][0]["event"]["future_event_field"] = "kept"
    bundle["signatures"][0]["future_signature_field"] = "kept"
    path = tmp_path / "additive.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    rc = main(["verify", "--json", "--explain", str(path)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert payload["schema_version"] == 1
    assert payload["result"] == "pass"
    assert payload["reason_code"] is None
    assert payload["taxonomy_version"] == 1
    assert payload["reasons"] == []
    assert payload["bundle"]["schema_version"] == 1
