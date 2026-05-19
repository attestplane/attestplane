from scripts.local_codex_runner.ci_watch import classify_checks, wait_for_ci
from scripts.local_codex_runner.github_cli import CheckStatus


def test_ci_pass_direct_success() -> None:
    checks = [CheckStatus("ci", "SUCCESS", "pass", None), CheckStatus("skip", "SKIPPED", "skipping", None)]

    assert classify_checks(checks) == "PASS"


def test_ci_fail_classification() -> None:
    checks = [CheckStatus("ci", "FAILURE", "fail", "https://example")]

    assert classify_checks(checks) == "FAIL"


def test_ci_pending_timeout(monkeypatch) -> None:
    class FakeGH:
        def pr_checks(self, repo, branch):
            return [CheckStatus("ci", "PENDING", "pending", None)]

    monkeypatch.setattr("time.sleep", lambda _: None)

    result = wait_for_ci(FakeGH(), repo="o/r", pr_number_or_branch="b", timeout_seconds=0, poll_seconds=0)

    assert result.status == "TIMEOUT"

