from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts/release/stale_autodev_issue_cleanup.py"

spec = importlib.util.spec_from_file_location("stale_autodev_issue_cleanup", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
cleanup = importlib.util.module_from_spec(spec)
sys.modules["stale_autodev_issue_cleanup"] = cleanup
spec.loader.exec_module(cleanup)


def test_classifies_release_train_issue_as_stale_support_only() -> None:
    issue = cleanup.Issue(
        number=10,
        title="Improve release-cd train workflow logging",
        labels=["planned-task"],
        url="https://example.test/10",
        body="Daily plan for npm dist-tag and SLSA workflow visibility.",
    )

    assert cleanup.classify_issue(issue) == "stale_support_only_autodev"


def test_keeps_product_targeted_autodev_issue() -> None:
    issue = cleanup.Issue(
        number=11,
        title="Add verifier negative conformance fixtures",
        labels=["planned-task"],
        url="https://example.test/11",
        body="Expand proof bundle canonical verifier failures.",
    )

    assert cleanup.classify_issue(issue) == "keep_product_targeted"


def test_non_autodev_issue_is_not_candidate() -> None:
    issue = cleanup.Issue(
        number=12,
        title="Release workflow",
        labels=["bug"],
        url="https://example.test/12",
        body="CI release workflow issue.",
    )

    assert cleanup.classify_issue(issue) == "not_autodev"
