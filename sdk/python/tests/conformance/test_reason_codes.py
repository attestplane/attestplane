# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Conformance coverage for verify reason codes and ``--explain`` output.

Exercises:
- Every known reason code maps to a stable explanation.
- Unknown / future reason codes degrade to a forward-compatible fallback.
- ``verify --explain`` output is deterministic and safe for golden-file diffing.
- ``verify --explain`` on an accepted bundle exits 0 with a stable summary.
"""

from __future__ import annotations

from pathlib import Path

from attestplane.cli.main import main
from attestplane.verify_reason_codes import (
    ALL_VERIFY_REASON_CODES_V1,
    UNKNOWN_REASON_CODE,
    VERIFY_REASON_TAXONOMY,
    VERIFY_REASON_TAXONOMY_VERSION,
    format_verify_taxonomy_version,
    is_known_verify_reason_code,
    resolve_verify_taxonomy_version,
    verify_reason_code_explanation,
    verify_reason_code_explanation_safe,
    verify_reason_code_matches_format,
)

ROOT = Path(__file__).resolve().parents[2]
ACCEPTED_FIXTURE = ROOT / "tests" / "fixtures" / "bundles" / "accepted" / "minimal.json"
REJECTED_DIR = ROOT / "tests" / "fixtures" / "bundles" / "rejected"
GOLDEN_DIR = ROOT / "tests" / "fixtures" / "golden" / "verify_explain"


def test_every_known_reason_code_has_explanation() -> None:
    """Every code in ALL_VERIFY_REASON_CODES_V1 must have a non-empty taxonomy entry."""
    for code in ALL_VERIFY_REASON_CODES_V1:
        explanation = verify_reason_code_explanation_safe(code)
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        assert code in VERIFY_REASON_TAXONOMY


def test_unknown_reason_code_degradation() -> None:
    """An unrecognised reason code degrades to the fallback message."""
    unknown_code = "att.verify.future_feature_v2"
    fallback = verify_reason_code_explanation_safe(unknown_code)
    assert "Unknown reason code" in fallback
    assert unknown_code in fallback


def test_malformed_reason_code_degradation() -> None:
    """A malformed code string also degrades gracefully."""
    malformed = "not_a_valid_code"
    fallback = verify_reason_code_explanation_safe(malformed)
    assert "Unknown reason code" in fallback
    assert malformed in fallback


def test_unknown_reason_code_constant_defined() -> None:
    """The constant UNKNOWN_REASON_CODE is defined and non-empty."""
    assert isinstance(UNKNOWN_REASON_CODE, str)
    assert len(UNKNOWN_REASON_CODE) > 0
    assert UNKNOWN_REASON_CODE == "unknown_reason_code"


def test_verify_explain_accepted_exits_zero() -> None:
    """``verify --explain`` on an accepted bundle exits 0."""
    rc = main(["verify", "--explain", str(ACCEPTED_FIXTURE)])
    assert rc == 0


def test_verify_explain_accepted_stable_output() -> None:
    """``verify --explain`` on an accepted bundle produces a stable summary line."""
    import sys
    from io import StringIO

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        rc = main(["verify", "--explain", str(ACCEPTED_FIXTURE)])
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    assert rc == 0
    assert output.startswith("OK signer_subject=")
    assert "schema_version=" in output
    assert "taxonomy_version=" in output


def test_verify_explain_rejected_golden_files() -> None:
    """Every rejected bundle with a golden file produces matching stdout."""
    for golden_path in sorted(GOLDEN_DIR.iterdir()):
        if golden_path.suffix != ".txt":
            continue
        fixture_name = golden_path.stem
        fixture_path = REJECTED_DIR / f"{fixture_name}.json"
        if not fixture_path.exists():
            continue

        import sys
        from io import StringIO

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = StringIO()
        sys.stderr = StringIO()
        try:
            rc = main(["verify", "--explain", str(fixture_path)])
            stdout = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        expected = golden_path.read_text(encoding="utf-8")
        assert stdout == expected, (
            f"Mismatch for {fixture_name}:\n  stdout:  {stdout!r}\n  golden:  {expected!r}\n  exit:    {rc}"
        )


def test_verify_explain_stderr_contains_reason_code_and_pointer() -> None:
    """Each rejected bundle explains reasons to stderr with code + pointer."""
    for fixture_path in sorted(REJECTED_DIR.iterdir()):
        if fixture_path.suffix != ".json":
            continue

        import sys
        from io import StringIO

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = StringIO()
        sys.stderr = StringIO()
        try:
            rc = main(["verify", "--explain", str(fixture_path)])
            stderr = sys.stderr.getvalue()
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        # Accepted bundles have no stderr; rejected ones should have explanations
        if rc != 0 and stderr:
            for line in stderr.splitlines():
                # Each rationale line should match: <reason_code> <pointer>: <message>
                assert " " in line, f"Missing space separator in: {line}"
                assert ": " in line, f"Missing ': ' separator in: {line}"


def test_is_known_verify_reason_code_returns_true_for_known() -> None:
    """Known reason codes return True."""
    for code in ALL_VERIFY_REASON_CODES_V1:
        assert is_known_verify_reason_code(code)


def test_is_known_verify_reason_code_returns_false_for_unknown() -> None:
    """Unknown reason code strings return False."""
    assert not is_known_verify_reason_code("att.verify.nonexistent")
    assert not is_known_verify_reason_code("")
    assert not is_known_verify_reason_code("totally_bogus")


def test_verify_reason_code_matches_format_positive() -> None:
    """Valid att.verify.* format strings match."""
    assert verify_reason_code_matches_format("att.verify.schema_invalid")
    assert verify_reason_code_matches_format("att.verify.anchor_invalid")


def test_verify_reason_code_matches_format_negative() -> None:
    """Invalid format strings do not match."""
    assert not verify_reason_code_matches_format("invalid")
    assert not verify_reason_code_matches_format("att.verify.123")
    assert not verify_reason_code_matches_format("")
    assert not verify_reason_code_matches_format("att.verify.UPPERCASE")


def test_verify_reason_code_explanation_returns_stable_message() -> None:
    """verify_reason_code_explanation returns the expected description."""
    desc = verify_reason_code_explanation(ALL_VERIFY_REASON_CODES_V1[0])
    assert isinstance(desc, str)
    assert len(desc) > 0


def test_resolve_verify_taxonomy_version_returns_one() -> None:
    """resolve_verify_taxonomy_version returns the current taxonomy version."""
    assert resolve_verify_taxonomy_version() == VERIFY_REASON_TAXONOMY_VERSION


def test_format_verify_taxonomy_version_defaults_to_current() -> None:
    """format_verify_taxonomy_version with no arg returns current version."""
    result = format_verify_taxonomy_version()
    assert result == str(VERIFY_REASON_TAXONOMY_VERSION)


def test_format_verify_taxonomy_version_with_explicit_value() -> None:
    """format_verify_taxonomy_version with an int returns its string form."""
    assert format_verify_taxonomy_version(42) == "42"
    assert format_verify_taxonomy_version(0) == "0"
    assert format_verify_taxonomy_version(None) == str(VERIFY_REASON_TAXONOMY_VERSION)
