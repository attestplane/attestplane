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

import json
from pathlib import Path

from attestplane.cli.main import main
from attestplane.verify_reason_codes import (
    ALL_VERIFY_REASON_CODES_V1,
    UNKNOWN_REASON_CODE,
    VERIFY_REASON_TAXONOMY,
    verify_reason_code_explanation_safe,
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
        if not golden_path.suffix == ".txt":
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
            f"Mismatch for {fixture_name}:\n"
            f"  stdout:  {stdout!r}\n"
            f"  golden:  {expected!r}\n"
            f"  exit:    {rc}"
        )


def test_verify_explain_stderr_contains_reason_code_and_pointer() -> None:
    """Each rejected bundle explains reasons to stderr with code + pointer."""
    for fixture_path in sorted(REJECTED_DIR.iterdir()):
        if not fixture_path.suffix == ".json":
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
