# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Conformance coverage for verifier reason-code taxonomy completeness.

Verifies that every code in ``ALL_VERIFY_REASON_CODES_V1`` has a matching
description, remediation, and matching format constraint.  Also spot-checks
that the ``--explain`` output for at least 6 negative conflict paths contains
the expected three-part ``code · short · remediation`` format.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from attestplane.verify_reason_codes import (
    ALL_VERIFY_REASON_CODES_V1,
    VERIFY_REASON_CODE_DESCRIPTIONS,
    VERIFY_REASON_CODE_REMEDIATIONS,
    verify_reason_code_explanation,
    verify_reason_code_matches_format,
    verify_reason_code_remediation,
)

ROOT = Path(__file__).resolve().parents[2]


def test_all_reason_codes_have_descriptions() -> None:
    """Every code in ALL_VERIFY_REASON_CODES_V1 must have a description."""
    for code in ALL_VERIFY_REASON_CODES_V1:
        desc = VERIFY_REASON_CODE_DESCRIPTIONS.get(code)
        assert desc is not None, f"{code} is missing a description"
        assert len(desc) > 0, f"{code} description is empty"
        assert verify_reason_code_explanation(code) == desc


def test_all_reason_codes_have_remediations() -> None:
    """Every code in ALL_VERIFY_REASON_CODES_V1 must have a remediation."""
    for code in ALL_VERIFY_REASON_CODES_V1:
        remediation = VERIFY_REASON_CODE_REMEDIATIONS.get(code)
        assert remediation is not None, f"{code} is missing a remediation"
        assert len(remediation) > 0, f"{code} remediation is empty"
        assert verify_reason_code_remediation(code) == remediation


def test_all_reason_codes_match_format() -> None:
    """Every code must match the att.verify.* format pattern."""
    for code in ALL_VERIFY_REASON_CODES_V1:
        assert verify_reason_code_matches_format(code), f"{code} does not match expected format"


def test_no_unknown_or_misc_fallback() -> None:
    """There must be no bare catch-all codes in the taxonomy.

    Compound codes like ``schema_unknown`` are specific findings (an
    unknown schema was detected), not catch-all fallbacks. The
    prohibition is against a bare ``unknown`` or ``misc`` identifier
    as the entire code suffix.
    """
    for code in ALL_VERIFY_REASON_CODES_V1:
        suffix = code.split(".")[-1]
        assert suffix not in ("unknown", "misc"), f"{code} is a bare fallback code"


def test_descriptions_and_remediations_have_same_keys() -> None:
    """The descriptions and remediations mappings must cover exactly the same codes."""
    assert set(VERIFY_REASON_CODE_DESCRIPTIONS) == set(VERIFY_REASON_CODE_REMEDIATIONS)
    assert set(VERIFY_REASON_CODE_DESCRIPTIONS) == set(ALL_VERIFY_REASON_CODES_V1)


def test_reason_code_count_is_stable() -> None:
    """The v1 taxonomy must contain exactly 10 codes."""
    assert len(ALL_VERIFY_REASON_CODES_V1) == 10


@pytest.mark.parametrize(
    ("fixture_rel", "expected_rc", "expected_code_prefix", "expected_pointer_substring", "extra_flags"),
    [
        ("fixtures/reject/canonicalization-edge.json", 1, "att.verify.canonical_mismatch", "/events/0/event/payload/artifact_ref", []),
        ("tests/fixtures/unknown_schema_version.json", 2, "att.verify.schema_version_unsupported", "/chain_metadata/schema_version", []),
        ("tests/fixtures/bundles/missing_signatures.json", 2, "att.verify.signature_missing", "/signatures", ["--strict-schema"]),
        ("fixtures/anchoring/quarantine_timeout.att", 2, "att.verify.schema_unknown", "/chain_metadata/critical_future_field", []),
        ("tests/fixtures/bundles/malformed_signature.json", 2, "att.verify.signature_invalid", "/signatures", ["--strict-schema"]),
        ("tests/fixtures/bundles/signature_digest_mismatch.json", 2, "att.verify.signature_invalid", "/signatures", ["--strict-schema"]),
    ],
)
def test_verify_explain_negative_path_contains_code_short_remediation(
    fixture_rel: str,
    expected_rc: int,
    expected_code_prefix: str,
    expected_pointer_substring: str,
    extra_flags: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Each of 6 negative paths emits a stderr line with code·short·remediation."""
    from attestplane.cli.main import main as cli_main

    fixture_path = ROOT / fixture_rel
    argv = ["verify", "--explain"] + extra_flags + [str(fixture_path)]
    rc = cli_main(argv)
    captured = capsys.readouterr()
    stderr_lines = captured.err.splitlines()

    assert rc == expected_rc, f"Expected rc={expected_rc}, got {rc} for {fixture_rel}"
    assert len(stderr_lines) >= 1, f"No stderr output for {fixture_rel}"
    first_line = stderr_lines[-1] if len(stderr_lines) > 1 else stderr_lines[0]

    assert first_line.startswith(f"{expected_code_prefix} · "), (
        f"Missing code·short·remediation format in: {first_line[:120]}"
    )
    assert expected_pointer_substring in first_line, (
        f"Expected pointer {expected_pointer_substring} not found in: {first_line[:200]}"
    )
