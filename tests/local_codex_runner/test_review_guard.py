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


def test_removed_test_reference_in_comment_is_not_test_deletion(tmp_path: Path) -> None:
    report = run_review_guard(
        diff="-# TS replays sdk/typescript/test/conformance.test.ts\n",
        codex_review_report="PASS",
        issue_labels=[],
        changed_files=["scripts/check-fixture-hashes.sh"],
        evidence_dir=tmp_path,
    )

    assert report.status == "PASS"


def test_pass_review_with_no_blocking_findings_is_not_blocked(tmp_path: Path) -> None:
    report = run_review_guard(
        diff="+ product code\n",
        codex_review_report="# Local Codex Review Report\n\nStatus: **PASS**\n\nNo blocking findings.\n",
        issue_labels=[],
        changed_files=["README.md"],
        evidence_dir=tmp_path,
    )

    assert report.status == "PASS"


def test_fail_review_status_is_blocked(tmp_path: Path) -> None:
    report = run_review_guard(
        diff="+ product code\n",
        codex_review_report="# Local Codex Review Report\n\nStatus: **FAIL**\n\nblocking_reasons: issue\n",
        issue_labels=[],
        changed_files=["README.md"],
        evidence_dir=tmp_path,
    )

    assert report.status == "FAIL"
    assert "Codex self-review reported a blocking failure" in report.blocking_reasons
