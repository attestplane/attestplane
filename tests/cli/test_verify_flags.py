# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Issue #138 integration tests for ``attestplane verify`` strict flags."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verify_errors import (
    VERIFY_BUNDLE_SCHEMA_INCOMPLETE,
    VERIFY_REQUIRED_FIELDS_MISSING,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"
VALID_SIGNED = FIXTURES / "v1.7.0_signed.json"
EMPTY_BUNDLE = FIXTURES / "empty_bundle.json"


@pytest.mark.parametrize(
    ("flags", "valid_rc", "invalid_rc", "invalid_reason", "stderr_code"),
    [
        ([], 0, 0, None, None),
        (
            ["--require-non-empty"],
            0,
            2,
            (
                (
                    "REASON_REQUIRED_FIELD_MISSING",
                    "/events",
                    "events must contain at least one event",
                ),
                (
                    "REASON_STRUCTURE_INVALID",
                    "/chain_metadata",
                    "events must contain at least one event when require_non_empty=True",
                ),
            ),
            VERIFY_REQUIRED_FIELDS_MISSING,
        ),
        (
            ["--strict-schema"],
            0,
            2,
            (
                ("REASON_REQUIRED_FIELD_MISSING", "/events", "events must contain at least one event"),
            ),
            VERIFY_BUNDLE_SCHEMA_INCOMPLETE,
        ),
        (
            ["--require-non-empty", "--strict-schema"],
            0,
            2,
            (
                (
                    "REASON_REQUIRED_FIELD_MISSING",
                    "/events",
                    "events must contain at least one event",
                ),
                (
                    "REASON_STRUCTURE_INVALID",
                    "/chain_metadata",
                    "events must contain at least one event when require_non_empty=True",
                ),
            ),
            VERIFY_REQUIRED_FIELDS_MISSING,
        ),
    ],
)
def test_verify_strict_flag_combinations(
    flags: list[str],
    valid_rc: int,
    invalid_rc: int,
    invalid_reason: tuple[tuple[str, str, str], ...] | None,
    stderr_code: str | None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(["verify", str(VALID_SIGNED), *flags, "--json"])
    valid = json.loads(capsys.readouterr().out)

    assert rc == valid_rc
    assert valid["schema_version"] == "1"
    assert valid["bundle_schema_version"] == 1
    assert valid["ok"] is True
    assert valid["reasons"] == []

    rc = main(["verify", str(EMPTY_BUNDLE), *flags, "--json"])
    captured = capsys.readouterr()
    invalid = json.loads(captured.out)

    assert rc == invalid_rc
    if invalid_reason is None:
        assert invalid["ok"] is True
        assert invalid["reasons"] == []
        assert captured.err == ""
    else:
        assert invalid["ok"] is False
        assert invalid["reasons"] == [
            {"code": code, "field": field, "message": message}
            for code, field, message in invalid_reason
        ]
        assert captured.err == f"{stderr_code}\n"


def test_verify_help_lists_strict_flags_and_exit_codes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["verify", "--help"])

    assert exc_info.value.code == 0
    out = " ".join(capsys.readouterr().out.split())
    assert "--require-non-empty" in out
    assert "--strict-schema" in out
    assert "proof-bundle contract" in out
    assert "0 success" in out
    assert "2 proof-bundle contract schema/non-empty violation" in out
    assert "1 cryptographic" in out
