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
    assert valid["result"] == "accept"
    assert valid["ok"] is True
    assert valid["require_non_empty"] is ("--require-non-empty" in flags)
    assert valid["strict_schema"] is ("--strict-schema" in flags)

    rc = main(["verify", str(EMPTY_BUNDLE), *flags, "--json"])
    captured = capsys.readouterr()
    invalid = json.loads(captured.out)

    assert rc == invalid_rc
    assert invalid["event_count"] == 0
    if invalid_code is None:
        assert invalid["result"] == "accept"
        assert invalid["ok"] is True
        assert captured.err == ""
    else:
        assert invalid["result"] == "reject"
        assert invalid["ok"] is False
        assert invalid["error_code"] == invalid_code
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
    assert "--explain" in out
    assert "proof-bundle contract" in out
    assert "0 success" in out
    assert "2 proof-bundle contract schema/non-empty violation" in out
    assert "1 cryptographic" in out
