from scripts.local_codex_runner.ci_watch import classify_checks, wait_for_ci
from scripts.local_codex_runner.github_cli import CheckStatus, RunnerCommandError


def test_ci_pass_direct_success() -> None:
    checks = [
        CheckStatus("ci", "SUCCESS", "pass", None),
        CheckStatus("skip", "SKIPPED", "skipping", None),
    ]

    assert classify_checks(checks) == "PASS"


def test_ci_fail_classification() -> None:
    checks = [CheckStatus("ci", "FAILURE", "fail", "https://example")]

    assert classify_checks(checks) == "FAIL"


def test_ci_wait_rechecks_single_failure_before_returning_fail(monkeypatch) -> None:
    class FakeGH:
        def __init__(self) -> None:
            self.calls = 0

        def pr_checks(self, repo, branch):
            self.calls += 1
            if self.calls == 1:
                return [CheckStatus("ci", "FAILURE", "fail", "https://example")]
            return [CheckStatus("ci", "SUCCESS", "pass", "https://example")]

    monkeypatch.setattr("time.sleep", lambda _: None)
    fake = FakeGH()

    result = wait_for_ci(
        fake, repo="o/r", pr_number_or_branch="b", timeout_seconds=30, poll_seconds=1
    )

    assert result.status == "PASS"
    assert fake.calls == 2


def test_ci_wait_returns_repeated_failure(monkeypatch) -> None:
    class FakeGH:
        def pr_checks(self, repo, branch):
            return [CheckStatus("ci", "FAILURE", "fail", "https://example")]

    monkeypatch.setattr("time.sleep", lambda _: None)

    result = wait_for_ci(
        FakeGH(),
        repo="o/r",
        pr_number_or_branch="b",
        timeout_seconds=30,
        poll_seconds=1,
    )

    assert result.status == "FAIL"


def test_ci_pending_timeout(monkeypatch) -> None:
    class FakeGH:
        def pr_checks(self, repo, branch):
            return [CheckStatus("ci", "PENDING", "pending", None)]

    monkeypatch.setattr("time.sleep", lambda _: None)

    result = wait_for_ci(
        FakeGH(), repo="o/r", pr_number_or_branch="b", timeout_seconds=0, poll_seconds=0
    )

    assert result.status == "TIMEOUT"


def test_ci_no_checks_reported_is_pending(monkeypatch) -> None:
    class FakeGH:
        def pr_checks(self, repo, branch):
            raise RunnerCommandError(
                ["gh", "pr", "checks", branch],
                1,
                "no checks reported on the 'branch' branch",
            )

    monkeypatch.setattr("time.sleep", lambda _: None)

    result = wait_for_ci(
        FakeGH(),
        repo="o/r",
        pr_number_or_branch="branch",
        timeout_seconds=0,
        poll_seconds=0,
    )

    assert result.status == "TIMEOUT"
    assert result.summary == "No checks returned by gh pr checks."
