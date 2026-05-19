from pathlib import Path

from scripts.local_codex_runner.review_guard import run_review_guard


def test_release_blocking_false_is_blocked(tmp_path: Path) -> None:
    report = run_review_guard(
        diff="- release_blocking: true\n+ release_blocking: false\n",
        codex_review_report="PASS",
        issue_labels=[],
        changed_files=["docs/policy/claims_policy.md"],
        evidence_dir=tmp_path,
    )

    assert report.status == "FAIL"


def test_secret_pattern_is_blocked(tmp_path: Path) -> None:
    report = run_review_guard(
        diff="+ GITHUB_TOKEN=github_pat_abc123\n",
        codex_review_report="PASS",
        issue_labels=[],
        changed_files=["x"],
        evidence_dir=tmp_path,
    )

    assert report.status == "FAIL"


def test_publish_workflow_requires_label(tmp_path: Path) -> None:
    report = run_review_guard(
        diff="+ name: publish\n",
        codex_review_report="PASS",
        issue_labels=[],
        changed_files=[".github/workflows/publish-python.yml"],
        evidence_dir=tmp_path,
    )

    assert report.status == "FAIL"


def test_claim_safety_requires_test_or_evidence(tmp_path: Path) -> None:
    report = run_review_guard(
        diff="+ claim wording\n",
        codex_review_report="PASS",
        issue_labels=["claim-safety"],
        changed_files=["README.md"],
        evidence_dir=tmp_path,
    )

    assert report.status == "FAIL"

