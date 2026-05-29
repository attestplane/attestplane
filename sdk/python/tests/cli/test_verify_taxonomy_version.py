# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""CLI taxonomy-version pinning tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verify_errors import VERIFY_TAXONOMY_VERSION_UNSUPPORTED
from attestplane.verify_reason_codes import VERIFY_REASON_TAXONOMY_VERSION_UNSUPPORTED

ROOT = Path(__file__).resolve().parents[4]
TAXONOMY_V1_FIXTURE = ROOT / "fixtures" / "conformance" / "taxonomy_v1.att"


@pytest.mark.parametrize(
    ("required_taxonomy_version", "expected_exit_code", "expected_reason_code", "expected_stderr"),
    [
        (1, 0, None, ""),
        (
            2,
            2,
            VERIFY_REASON_TAXONOMY_VERSION_UNSUPPORTED,
            f"{VERIFY_TAXONOMY_VERSION_UNSUPPORTED}\n",
        ),
    ],
)
def test_verify_require_taxonomy_version_pins_the_output_contract(
    required_taxonomy_version: int,
    expected_exit_code: int,
    expected_reason_code: str | None,
    expected_stderr: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(
        [
            "verify",
            "--json",
            "--require-taxonomy-version",
            str(required_taxonomy_version),
            str(TAXONOMY_V1_FIXTURE),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == expected_exit_code
    assert payload["schema_version"] == 1
    assert payload["result"] == ("pass" if expected_exit_code == 0 else "fail")
    assert payload["exit_code"] == expected_exit_code
    assert payload["reason_code"] == expected_reason_code
    assert payload["taxonomy_version"] == 1
    if expected_reason_code is None:
        assert payload["reasons"] == []
    else:
        assert payload["reasons"][0]["code"] == expected_reason_code
    assert captured.err == expected_stderr
