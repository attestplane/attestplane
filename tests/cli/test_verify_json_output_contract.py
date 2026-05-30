# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""CI-gating output-contract tests for ``attestplane verify --json``.

This pins the exact ``verify --json`` field set, ordering, and reason-code
shape that downstream consumers gate on.  Any addition / removal / rename of
a contract field requires a deliberate version bump here and in the golden
fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

from attestplane.cli.main import main
from attestplane.verify_reason_codes import VERIFY_REASON_TAXONOMY_VERSION

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"
VALID_BUNDLE = FIXTURES / "valid_bundle.json"
GOLDEN_FIXTURE = FIXTURES / "verify_json_contract.golden"

# Contract version for the golden fixture.
# Bump this when the --json output shape changes, and update the golden file.
VERIFY_JSON_OUTPUT_CONTRACT_VERSION: str = "1.8.19"


def test_json_output_contract_golden_fixture_match(capsys) -> None:
    """``verify --json`` output must exactly match the golden fixture."""
    golden = GOLDEN_FIXTURE.read_text(encoding="utf-8")
    rc = main(["verify", "--json", str(VALID_BUNDLE)])
    captured = capsys.readouterr()
    actual = captured.out

    assert rc == 0, f"verify --json exited with rc={rc}: {captured.err}"
    assert captured.err == "", f"stderr should be empty: {captured.err}"

    assert json.loads(actual) == json.loads(golden), (
        "verify --json output differs from golden fixture.\n"
        f"  golden  ({GOLDEN_FIXTURE}): {golden.strip()}\n"
        f"  actual                   : {actual.strip()}"
    )
    assert actual == golden, (
        "verify --json output differs from golden fixture (whitespace/ordering).\n"
        f"  golden  ({GOLDEN_FIXTURE}): {golden.strip()}\n"
        f"  actual                   : {actual.strip()}"
    )


def test_json_output_contract_taxonomy_version_drift(capsys) -> None:
    """Golden fixture ``taxonomy_version`` must match the reason-code taxonomy."""
    golden = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    assert golden["taxonomy_version"] == VERIFY_REASON_TAXONOMY_VERSION, (
        f"Golden fixture taxonomy_version ({golden['taxonomy_version']}) "
        f"drifted from VERIFY_REASON_TAXONOMY_VERSION ({VERIFY_REASON_TAXONOMY_VERSION})."
    )


def test_json_output_contract_version_is_explicit() -> None:
    """Contract version constant must be documented and well-formed."""
    assert GOLDEN_FIXTURE.exists(), f"Golden fixture not found: {GOLDEN_FIXTURE}"
    assert isinstance(VERIFY_JSON_OUTPUT_CONTRACT_VERSION, str)
    assert VERIFY_JSON_OUTPUT_CONTRACT_VERSION.count(".") == 2
