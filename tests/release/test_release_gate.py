from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "release" / "release_gate.py"

spec = importlib.util.spec_from_file_location("release_gate", MODULE_PATH)
assert spec is not None
release_gate = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["release_gate"] = release_gate
spec.loader.exec_module(release_gate)


def test_support_only_files_are_allowed_without_a_bypass() -> None:
    result = release_gate.classify_product_delta(
        [
            "sdk/python/tests/test_issue209_schema_version_ci_coverage.py",
            "docs/validation/local_codex_runner/issue-280/runner_result.md",
        ],
        labels=[],
        env=os.environ,
    )

    assert result.allowed is True
    assert result.reason == "product_support_delta"
    assert (
        "sdk/python/tests/test_issue209_schema_version_ci_coverage.py"
        in result.product_support_files
    )
    assert (
        "docs/validation/local_codex_runner/issue-280/runner_result.md"
        in result.support_only_files
    )


def test_support_only_files_are_allowed_without_product_changes() -> None:
    result = release_gate.classify_product_delta(
        [
            "docs/validation/local_codex_runner/issue-280/runner_result.md",
            "scripts/local_codex_runner/run_issue.py",
        ],
        labels=[],
        env=os.environ,
    )

    assert result.allowed is True
    assert result.reason == "support_only_delta"
    assert result.product_files == []
    assert result.product_support_files == []
    assert result.support_only_files == [
        "docs/validation/local_codex_runner/issue-280/runner_result.md",
        "scripts/local_codex_runner/run_issue.py",
    ]
