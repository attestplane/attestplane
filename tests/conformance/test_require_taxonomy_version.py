# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.verify_reason_codes import (
    VERIFY_REASON_TAXONOMY_VERSION_UNSUPPORTED,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "conformance" / "taxonomy_v1_bundle.json"


def _run_verify(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, dict[str, object], str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, json.loads(captured.out), captured.err


def test_taxonomy_pinning_is_inert_when_absent_or_matching(
    capsys: pytest.CaptureFixture[str],
) -> None:
    base_rc, base_payload, base_stderr = _run_verify(["verify", "--json", str(FIXTURE)], capsys)
    matched_rc, matched_payload, matched_stderr = _run_verify(
        ["verify", "--json", "--require-taxonomy-version", "v1", str(FIXTURE)],
        capsys,
    )

    assert base_rc == 0
    assert matched_rc == 0
    assert base_stderr == ""
    assert matched_stderr == ""
    assert base_payload == matched_payload
    assert matched_payload["result"] == "pass"
    assert matched_payload["exit_code"] == 0
    assert matched_payload["reason_code"] is None
    assert matched_payload["taxonomy_version"] == 1


def test_taxonomy_pinning_rejects_mismatch_with_structured_reason(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, stderr = _run_verify(
        ["verify", "--json", "--require-taxonomy-version", "v2", str(FIXTURE)],
        capsys,
    )

    assert rc == 1
    assert stderr == ""
    assert payload["schema_version"] == 1
    assert payload["result"] == "fail"
    assert payload["exit_code"] == 1
    assert payload["reason_code"] == VERIFY_REASON_TAXONOMY_VERSION_UNSUPPORTED
    assert payload["taxonomy_version"] == 1
    assert payload["reasons"] == [
        {
            "code": VERIFY_REASON_TAXONOMY_VERSION_UNSUPPORTED,
            "path": "/",
            "message": (
                "required taxonomy_version='v2' does not match "
                "supported taxonomy_version=v1"
            ),
        }
    ]


def test_taxonomy_pinning_explain_surfaces_the_same_rejection(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, stderr = _run_verify(
        ["verify", "--json", "--explain", "--require-taxonomy-version", "v2", str(FIXTURE)],
        capsys,
    )

    assert rc == 1
    assert stderr == ""
    assert payload["result"] == "fail"
    assert payload["reason_code"] == VERIFY_REASON_TAXONOMY_VERSION_UNSUPPORTED
    assert payload["explanation"] == [
        {
            "primary_reason": VERIFY_REASON_TAXONOMY_VERSION_UNSUPPORTED,
            "pointer": "/",
            "message": (
                "required taxonomy_version='v2' does not match "
                "supported taxonomy_version=v1"
            ),
        }
    ]
