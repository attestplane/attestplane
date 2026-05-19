from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "release" / "alpha_release_train.py"


spec = importlib.util.spec_from_file_location("alpha_release_train", MODULE_PATH)
assert spec is not None
alpha_release_train = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["alpha_release_train"] = alpha_release_train
spec.loader.exec_module(alpha_release_train)


def write_queue(tmp_path: Path, candidates: list[dict[str, object]]) -> Path:
    path = tmp_path / "queue.json"
    path.write_text(json.dumps({"schema": "attestplane_alpha_release_train_queue.v1", "candidates": candidates}))
    return path


def candidate(release: str = "v0.0.6-alpha") -> dict[str, object]:
    return {
        "release": release,
        "python_version": "0.0.6a0",
        "npm_version": "0.0.6-alpha",
    }


def test_empty_queue_is_noop_success(tmp_path: Path) -> None:
    path = write_queue(tmp_path, [])
    assert alpha_release_train.load_queue(path) == []


def test_queue_requires_alpha_release_shape(tmp_path: Path) -> None:
    path = write_queue(tmp_path, [candidate("v0.0.6")])
    with pytest.raises(ValueError, match="alpha release names"):
        alpha_release_train.load_queue(path)


def test_queue_rejects_duplicate_release_entries(tmp_path: Path) -> None:
    path = write_queue(tmp_path, [candidate(), candidate()])
    with pytest.raises(ValueError, match="duplicate alpha release"):
        alpha_release_train.load_queue(path)


def test_queue_rejects_non_alpha_npm_version(tmp_path: Path) -> None:
    item = candidate()
    item["npm_version"] = "0.0.6"
    path = write_queue(tmp_path, [item])
    with pytest.raises(ValueError, match="npm alpha versions"):
        alpha_release_train.load_queue(path)


def test_advisory_release_input_is_rejected(tmp_path: Path) -> None:
    advisory = tmp_path / "advisory.md"
    advisory.write_text("STATUS: ADVISORY\nAUTHORITY: NOT_AUTHORIZED_FOR_PUBLISH\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="advisory planning output"):
        alpha_release_train.reject_advisory_release_input(advisory)


def test_advisory_plan_strips_forbidden_commands(tmp_path: Path) -> None:
    output = alpha_release_train.write_advisory_plan(
        "Issue A\nRun npm publish now\nRun git push origin main\nIssue B\n",
        prompt="plan",
        proposals_dir=tmp_path,
    )
    text = output.read_text(encoding="utf-8")
    assert "STATUS: ADVISORY" in text
    assert "NOT_AUTHORIZED_FOR_PUBLISH" in text
    assert "REMOVED_FORBIDDEN_COMMAND_LINES: 2" in text
    assert "npm publish" not in text
    assert "git push" not in text
    assert "Issue A" in text
    assert "Issue B" in text


def test_advisory_planning_failure_writes_limitation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ATTESTPLANE_ALPHA_PLAN_FAKE_RESPONSE", raising=False)

    def fail_run(*args: object, **kwargs: object) -> object:
        return alpha_release_train.subprocess.CompletedProcess(["ask_opus.sh"], 1, "", "")

    monkeypatch.setattr(alpha_release_train.subprocess, "run", fail_run)
    output = alpha_release_train.plan_next_alpha_issues(
        dry_run=False,
        timeout_seconds=1,
        proposals_dir=tmp_path,
    )

    assert output is not None
    text = output.read_text(encoding="utf-8")
    assert "STATUS: ADVISORY" in text
    assert "status: failed" in text
    assert "deterministic release queue processing continues" in text


def test_pipeline_report_keeps_opus_non_authoritative(tmp_path: Path) -> None:
    plan = tmp_path / "next-alpha.md"
    plan.write_text("STATUS: ADVISORY\n", encoding="utf-8")
    state_file = tmp_path / "state.json"
    candidate_value = alpha_release_train.AlphaCandidate.from_json(candidate("v0.0.8-alpha"))
    alpha_release_train.mark_stage(state_file, candidate_value, "registry_verified", "done")
    report = alpha_release_train.write_pipeline_report(
        advisory_plan=plan,
        queue=tmp_path / "queue.json",
        candidates=[candidate_value],
        executed=True,
        reports_dir=tmp_path,
        state_path=state_file,
        retired_prepared=[{"release": "v0.0.7-alpha", "reason": "older_than_latest_alpha:v0.0.8-alpha"}],
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["schema"] == "attestplane_alpha_release_pipeline_report.v1"
    assert payload["executed"] is True
    assert payload["candidate_releases"] == ["v0.0.8-alpha"]
    assert payload["state_backend"] == "sqlite"
    assert payload["retired_prepared_releases"][0]["release"] == "v0.0.7-alpha"
    assert payload["release_stage_summary"]["v0.0.8-alpha"]["registry_verified"] == "done"
    assert payload["stages"][0]["authority"] == "advisory_only"
    assert payload["stages"][1]["candidate_count"] == 1
    assert payload["explicit_non_claims"]["opus_authorized_publish"] is False
    assert payload["explicit_non_claims"]["unbounded_loop_without_queue"] is False


def test_continuous_state_filters_processed_releases(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    alpha_release_train.save_continuous_state(
        state_file,
        {
            "schema": "attestplane_alpha_continuous_state.v1",
            "processed_releases": ["v0.0.6-alpha"],
        },
    )
    remaining = alpha_release_train.unprocessed_candidates(
        [
            alpha_release_train.AlphaCandidate.from_json(candidate("v0.0.6-alpha")),
            alpha_release_train.AlphaCandidate.from_json(
                {
                    "release": "v0.0.7-alpha",
                    "python_version": "0.0.7a0",
                    "npm_version": "0.0.7-alpha",
                }
            ),
        ],
        state_file,
    )
    assert [item.release for item in remaining] == ["v0.0.7-alpha"]


def test_bootstrap_repo_root_adds_repo_root_to_sys_path(monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = str(REPO_ROOT)
    monkeypatch.setattr(alpha_release_train.sys, "path", [p for p in alpha_release_train.sys.path if p != repo_root])
    alpha_release_train.bootstrap_repo_root()
    assert alpha_release_train.sys.path[0] == repo_root


def test_continuous_state_uses_sqlite_with_json_snapshot(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    candidate_value = alpha_release_train.AlphaCandidate.from_json(candidate("v0.0.8-alpha"))

    alpha_release_train.mark_prepared(state_file, candidate_value, dry_run=False)
    alpha_release_train.mark_processed(state_file, candidate_value, dry_run=False)
    alpha_release_train.mark_processed(state_file, candidate_value, dry_run=False)

    state = alpha_release_train.load_continuous_state(state_file)
    snapshot = json.loads(state_file.read_text(encoding="utf-8"))

    assert state["state_backend"] == "sqlite"
    assert state["processed_releases"] == ["v0.0.8-alpha"]
    assert snapshot["processed_releases"] == ["v0.0.8-alpha"]
    assert sum(state["release_count_by_day"].values()) == 1
    assert (tmp_path / "state.sqlite").is_file()


def test_sqlite_state_can_import_legacy_json(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "schema": "attestplane_alpha_continuous_state.v1",
                "prepared_releases": ["v0.0.7-alpha"],
                "processed_releases": ["v0.0.8-alpha"],
                "prepare_count_by_day": {"2026-05-19": 1},
                "release_count_by_day": {"2026-05-19": 1},
            }
        ),
        encoding="utf-8",
    )

    state = alpha_release_train.load_continuous_state(state_file)

    assert state["state_backend"] == "sqlite"
    assert state["prepared_releases"] == ["v0.0.7-alpha"]
    assert state["processed_releases"] == ["v0.0.8-alpha"]
    assert (tmp_path / "state.sqlite").is_file()


def test_retire_obsolete_prepared_release_marks_stale_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "state.json"
    stale = alpha_release_train.AlphaCandidate.from_json(candidate("v0.0.7-alpha"))
    released = alpha_release_train.AlphaCandidate.from_json(candidate("v0.1.3-alpha"))

    alpha_release_train.mark_prepared(state_file, stale, dry_run=False)
    alpha_release_train.mark_processed(state_file, released, dry_run=False)
    monkeypatch.setattr(alpha_release_train, "latest_alpha_release_from_notes", lambda: "v0.1.3-alpha")
    monkeypatch.setattr(alpha_release_train, "alpha_release_exists", lambda release: False)

    retired = alpha_release_train.retire_obsolete_prepared_releases(
        state_file,
        active_candidates=[],
        dry_run=False,
    )
    state = alpha_release_train.load_continuous_state(state_file)

    assert retired == [{"release": "v0.0.7-alpha", "reason": "older_than_latest_alpha:v0.1.3-alpha"}]
    assert "v0.0.7-alpha" not in state["prepared_releases"]
    assert state["retired_releases"] == ["v0.0.7-alpha"]


def test_retire_obsolete_prepared_keeps_active_candidate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "state.json"
    stale = alpha_release_train.AlphaCandidate.from_json(candidate("v0.0.7-alpha"))

    alpha_release_train.mark_prepared(state_file, stale, dry_run=False)
    monkeypatch.setattr(alpha_release_train, "latest_alpha_release_from_notes", lambda: "v0.1.3-alpha")
    monkeypatch.setattr(alpha_release_train, "alpha_release_exists", lambda release: True)

    retired = alpha_release_train.retire_obsolete_prepared_releases(
        state_file,
        active_candidates=[stale],
        dry_run=False,
    )

    assert retired == []
    assert alpha_release_train.load_continuous_state(state_file)["prepared_releases"] == ["v0.0.7-alpha"]


def test_retire_obsolete_prepared_dry_run_does_not_report_actual_retirement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "state.json"
    stale = alpha_release_train.AlphaCandidate.from_json(candidate("v0.0.7-alpha"))
    released = alpha_release_train.AlphaCandidate.from_json(candidate("v0.1.3-alpha"))

    alpha_release_train.mark_prepared(state_file, stale, dry_run=False)
    alpha_release_train.mark_processed(state_file, released, dry_run=False)
    monkeypatch.setattr(alpha_release_train, "latest_alpha_release_from_notes", lambda: "v0.1.3-alpha")
    monkeypatch.setattr(alpha_release_train, "alpha_release_exists", lambda release: False)

    retired = alpha_release_train.retire_obsolete_prepared_releases(
        state_file,
        active_candidates=[],
        dry_run=True,
    )

    assert retired == []
    assert alpha_release_train.load_continuous_state(state_file)["prepared_releases"] == ["v0.0.7-alpha"]


def test_retire_obsolete_prepared_handles_empty_release_floor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "state.json"

    monkeypatch.setattr(alpha_release_train, "latest_alpha_release_from_notes", lambda: "v0.0.0-alpha")

    assert alpha_release_train.retire_obsolete_prepared_releases(
        state_file,
        active_candidates=[],
        dry_run=True,
    ) == []


def test_auto_promote_merge_is_dry_run_safe(tmp_path: Path) -> None:
    queue = write_queue(tmp_path, [])
    promoted = alpha_release_train.AlphaCandidate.from_json(
        {
            "release": "v0.0.8-alpha",
            "python_version": "0.0.8a0",
            "npm_version": "0.0.8-alpha",
        }
    )

    merged = alpha_release_train.merge_prepared_candidates(queue, [promoted], dry_run=True)

    assert [item.release for item in merged] == ["v0.0.8-alpha"]
    assert json.loads(queue.read_text(encoding="utf-8"))["candidates"] == []


def test_auto_promote_merge_persists_when_executing(tmp_path: Path) -> None:
    queue = write_queue(tmp_path, [])
    promoted = alpha_release_train.AlphaCandidate.from_json(
        {
            "release": "v0.0.8-alpha",
            "python_version": "0.0.8a0",
            "npm_version": "0.0.8-alpha",
        }
    )

    alpha_release_train.merge_prepared_candidates(queue, [promoted], dry_run=False)

    payload = json.loads(queue.read_text(encoding="utf-8"))
    assert payload["candidates"][0]["release"] == "v0.0.8-alpha"


def test_auto_promote_merge_can_stay_in_memory_for_full_auto(tmp_path: Path) -> None:
    queue = write_queue(tmp_path, [])
    promoted = alpha_release_train.AlphaCandidate.from_json(
        {
            "release": "v0.0.8-alpha",
            "python_version": "0.0.8a0",
            "npm_version": "0.0.8-alpha",
        }
    )

    merged = alpha_release_train.merge_prepared_candidates(queue, [promoted], dry_run=True)

    assert [candidate.release for candidate in merged] == ["v0.0.8-alpha"]
    assert json.loads(queue.read_text(encoding="utf-8"))["candidates"] == []


def test_stop_file_requests_clean_exit(tmp_path: Path) -> None:
    stop_file = tmp_path / "STOP"
    assert alpha_release_train.stop_requested(stop_file) is False
    stop_file.write_text("stop\n", encoding="utf-8")
    assert alpha_release_train.stop_requested(stop_file) is True


def test_request_stop_writes_reason(tmp_path: Path) -> None:
    stop_file = tmp_path / "STOP"
    alpha_release_train.request_stop(stop_file, "fail-closed test")
    assert alpha_release_train.stop_requested(stop_file) is True
    assert "fail-closed test" in stop_file.read_text(encoding="utf-8")


def test_git_push_retries_transient_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(
        argv: list[str],
        **kwargs: object,
    ) -> alpha_release_train.subprocess.CompletedProcess[str]:
        calls.append(argv)
        assert kwargs["timeout"] == alpha_release_train.REMOTE_PUSH_TIMEOUT_SECONDS
        if len(calls) == 1:
            raise alpha_release_train.subprocess.CalledProcessError(128, argv)
        return alpha_release_train.subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(alpha_release_train.subprocess, "run", fake_run)
    monkeypatch.setattr(alpha_release_train, "git_push_remote_converged", lambda argv: False)
    monkeypatch.setattr(alpha_release_train.time, "sleep", lambda seconds: None)

    result = alpha_release_train.run_git_push(["git", "push", "origin", "main"], dry_run=False)

    assert result.returncode == 0
    assert calls == [["git", "push", "origin", "main"], ["git", "push", "origin", "main"]]


def test_git_push_retry_remains_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(
        argv: list[str],
        **kwargs: object,
    ) -> alpha_release_train.subprocess.CompletedProcess[str]:
        calls.append(argv)
        raise alpha_release_train.subprocess.CalledProcessError(128, argv)

    monkeypatch.setattr(alpha_release_train.subprocess, "run", fake_run)
    monkeypatch.setattr(alpha_release_train, "git_push_remote_converged", lambda argv: False)
    monkeypatch.setattr(alpha_release_train.time, "sleep", lambda seconds: None)

    with pytest.raises(alpha_release_train.subprocess.CalledProcessError):
        alpha_release_train.run_git_push(["git", "push", "origin", "main"], dry_run=False)

    assert len(calls) == alpha_release_train.REMOTE_PUSH_ATTEMPTS


def test_git_push_retries_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(
        argv: list[str],
        **kwargs: object,
    ) -> alpha_release_train.subprocess.CompletedProcess[str]:
        calls.append(argv)
        if len(calls) == 1:
            raise alpha_release_train.subprocess.TimeoutExpired(argv, timeout=alpha_release_train.REMOTE_PUSH_TIMEOUT_SECONDS)
        return alpha_release_train.subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(alpha_release_train.subprocess, "run", fake_run)
    monkeypatch.setattr(alpha_release_train, "git_push_remote_converged", lambda argv: False)
    monkeypatch.setattr(alpha_release_train.time, "sleep", lambda seconds: None)

    result = alpha_release_train.run_git_push(["git", "push", "origin", "main"], dry_run=False)

    assert result.returncode == 0
    assert len(calls) == 2


def test_git_push_failure_reason_classifies_network_errors() -> None:
    exc = alpha_release_train.subprocess.CalledProcessError(
        128,
        ["git", "push", "origin", "main"],
        stderr="fatal: unable to access 'https://github.com/attestplane/attestplane.git/': Failed to connect to github.com port 443 after 75003 ms: Couldn't connect to server",
    )

    assert alpha_release_train.classify_git_push_failure(exc) == "git_push_network_unavailable"


def test_git_push_failure_reason_classifies_timeouts() -> None:
    exc = alpha_release_train.subprocess.TimeoutExpired(
        ["git", "push", "origin", "main"],
        timeout=alpha_release_train.REMOTE_PUSH_TIMEOUT_SECONDS,
    )

    assert alpha_release_train.classify_git_push_failure(exc) == "git_push_timeout"


def test_ensure_main_pushed_enqueues_task_without_blocking(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    candidate_value = alpha_release_train.AlphaCandidate.from_json(candidate("v0.0.8-alpha"))
    state_file = tmp_path / "state.json"
    queue_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(alpha_release_train, "stage_done", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        alpha_release_train,
        "enqueue_git_push_task",
        lambda path, candidate, ref, *, dry_run: queue_calls.append((candidate.release, ref)),
    )
    monkeypatch.setattr(
        alpha_release_train,
        "mark_stage",
        lambda path, candidate, stage, status, detail=None: stage_calls.append((stage, status)),
    )
    monkeypatch.setattr(alpha_release_train, "run_git_push", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("run_git_push should not run")))

    alpha_release_train.ensure_main_pushed(candidate_value, dry_run=False, state_path=state_file)

    assert queue_calls == [("v0.0.8-alpha", "main")]
    assert stage_calls == [("main_pushed", "queued")]


def test_create_tag_and_release_enqueues_tag_push_without_blocking(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    candidate_value = alpha_release_train.AlphaCandidate.from_json({**candidate("v0.0.8-alpha"), "create_github_release": False})
    state_file = tmp_path / "state.json"
    queue_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []
    run_calls: list[list[str]] = []

    monkeypatch.setattr(alpha_release_train, "stage_done", lambda *args, **kwargs: False)
    monkeypatch.setattr(alpha_release_train, "local_tag_points_at_head", lambda release: True)
    monkeypatch.setattr(
        alpha_release_train,
        "enqueue_git_push_task",
        lambda path, candidate, ref, *, dry_run: queue_calls.append((candidate.release, ref)),
    )
    monkeypatch.setattr(
        alpha_release_train,
        "mark_stage",
        lambda path, candidate, stage, status, detail=None: stage_calls.append((stage, status)),
    )
    monkeypatch.setattr(
        alpha_release_train,
        "run",
        lambda argv, *, dry_run, env=None: run_calls.append(argv) or alpha_release_train.subprocess.CompletedProcess(argv, 0, "", ""),
    )

    alpha_release_train.create_tag_and_release(candidate_value, dry_run=False, state_path=state_file)

    assert queue_calls == [("v0.0.8-alpha", "v0.0.8-alpha")]
    assert stage_calls == [("tag_pushed", "queued")]
    assert ["git", "push", "origin", "v0.0.8-alpha"] not in run_calls


def test_git_push_timeout_continues_when_main_reached_remote(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    remote_checks = 0

    def fake_run(
        argv: list[str],
        **kwargs: object,
    ) -> alpha_release_train.subprocess.CompletedProcess[str]:
        calls.append(argv)
        raise alpha_release_train.subprocess.TimeoutExpired(argv, timeout=alpha_release_train.REMOTE_PUSH_TIMEOUT_SECONDS)

    def fake_capture(argv: list[str], timeout: int | None = None) -> str:
        nonlocal remote_checks
        if argv == ["git", "rev-parse", "--verify", "refs/remotes/origin/main"]:
            return "old123"
        if argv == ["git", "ls-remote", "origin", "refs/heads/main"]:
            remote_checks += 1
            if remote_checks == 1:
                return "old123\trefs/heads/main"
            return "abc123\trefs/heads/main"
        if argv == ["git", "rev-parse", "HEAD"]:
            return "abc123"
        raise AssertionError(argv)

    monkeypatch.setattr(alpha_release_train.subprocess, "run", fake_run)
    monkeypatch.setattr(alpha_release_train, "capture", fake_capture)

    result = alpha_release_train.run_git_push(["git", "push", "origin", "main"], dry_run=False)

    assert result.returncode == 0
    assert len(calls) == 1


def test_git_push_timeout_continues_when_tag_reached_remote(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    remote_checks = 0

    def fake_run(
        argv: list[str],
        **kwargs: object,
    ) -> alpha_release_train.subprocess.CompletedProcess[str]:
        calls.append(argv)
        raise alpha_release_train.subprocess.TimeoutExpired(argv, timeout=alpha_release_train.REMOTE_PUSH_TIMEOUT_SECONDS)

    def fake_capture(argv: list[str], timeout: int | None = None) -> str:
        nonlocal remote_checks
        if argv == ["git", "ls-remote", "origin", "refs/tags/v0.1.1-alpha"]:
            remote_checks += 1
            if remote_checks == 1:
                return ""
            return "abc123\trefs/tags/v0.1.1-alpha"
        raise AssertionError(argv)

    monkeypatch.setattr(alpha_release_train.subprocess, "run", fake_run)
    monkeypatch.setattr(alpha_release_train, "capture", fake_capture)

    result = alpha_release_train.run_git_push(["git", "push", "origin", "v0.1.1-alpha"], dry_run=False)

    assert result.returncode == 0
    assert len(calls) == 1


def test_git_push_skips_when_main_already_reached_remote(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(
        argv: list[str],
        **kwargs: object,
    ) -> alpha_release_train.subprocess.CompletedProcess[str]:
        calls.append(argv)
        return alpha_release_train.subprocess.CompletedProcess(argv, 0, "", "")

    def fake_capture(argv: list[str], timeout: int | None = None) -> str:
        if argv == ["git", "rev-parse", "--verify", "refs/remotes/origin/main"]:
            return "abc123"
        if argv == ["git", "rev-parse", "HEAD"]:
            return "abc123"
        raise AssertionError(argv)

    monkeypatch.setattr(alpha_release_train.subprocess, "run", fake_run)
    monkeypatch.setattr(alpha_release_train, "capture", fake_capture)

    result = alpha_release_train.run_git_push(["git", "push", "origin", "main"], dry_run=False)

    assert result.returncode == 0
    assert calls == []


def test_git_push_skips_main_using_local_tracking_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(
        argv: list[str],
        **kwargs: object,
    ) -> alpha_release_train.subprocess.CompletedProcess[str]:
        calls.append(argv)
        return alpha_release_train.subprocess.CompletedProcess(argv, 0, "", "")

    def fake_capture(argv: list[str], timeout: int | None = None) -> str:
        if argv == ["git", "rev-parse", "--verify", "refs/remotes/origin/main"]:
            return "abc123"
        if argv == ["git", "rev-parse", "HEAD"]:
            return "abc123"
        if argv == ["git", "ls-remote", "origin", "refs/heads/main"]:
            raise AssertionError("network probe should not run when local tracking is converged")
        raise AssertionError(argv)

    monkeypatch.setattr(alpha_release_train.subprocess, "run", fake_run)
    monkeypatch.setattr(alpha_release_train, "capture", fake_capture)

    result = alpha_release_train.run_git_push(["git", "push", "origin", "main"], dry_run=False)

    assert result.returncode == 0
    assert calls == []


def test_daily_release_count_defaults_to_zero(tmp_path: Path) -> None:
    assert alpha_release_train.daily_release_count(tmp_path / "missing-state.json") == 0


def test_next_alpha_release_from_notes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    docs = tmp_path / "docs" / "release-notes"
    docs.mkdir(parents=True)
    (docs / "v0.0.9-alpha.draft.md").write_text("# v0.0.9-alpha\n", encoding="utf-8")
    (docs / "v0.0.10-alpha.draft.md").write_text("# v0.0.10-alpha\n", encoding="utf-8")
    monkeypatch.setattr(alpha_release_train, "ROOT", tmp_path)
    assert alpha_release_train.next_alpha_release() == "v0.1.0-alpha"


def test_next_alpha_release_after_milestone_uses_patch_one(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    docs = tmp_path / "docs" / "release-notes"
    docs.mkdir(parents=True)
    (docs / "v0.1.0-alpha.draft.md").write_text("# v0.1.0-alpha\n", encoding="utf-8")
    monkeypatch.setattr(alpha_release_train, "ROOT", tmp_path)
    assert alpha_release_train.next_alpha_release() == "v0.1.1-alpha"


def test_next_alpha_release_rolls_minor_after_ten_patch_alphas(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    docs = tmp_path / "docs" / "release-notes"
    docs.mkdir(parents=True)
    (docs / "v0.1.10-alpha.draft.md").write_text("# v0.1.10-alpha\n", encoding="utf-8")
    monkeypatch.setattr(alpha_release_train, "ROOT", tmp_path)
    assert alpha_release_train.next_alpha_release() == "v0.2.0-alpha"


def test_explicit_next_alpha_release_override_is_validated() -> None:
    assert alpha_release_train.resolve_next_alpha_release("v0.1.0-alpha") == "v0.1.0-alpha"
    with pytest.raises(ValueError, match="invalid alpha release"):
        alpha_release_train.resolve_next_alpha_release("0.1.0-alpha")


def test_milestone_alpha_requires_version_evaluation() -> None:
    assert alpha_release_train.requires_version_evaluation("v0.1.0-alpha") is True
    assert alpha_release_train.requires_version_evaluation("v0.2.0-alpha") is True
    assert alpha_release_train.requires_version_evaluation("v0.1.1-alpha") is False
    assert alpha_release_train.requires_version_evaluation("v0.1.10-alpha") is False


def test_version_evaluation_advisory_is_non_authoritative(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ATTESTPLANE_ALPHA_VERSION_EVAL_FAKE_RESPONSE", "Version number looks appropriate.")

    output = alpha_release_train.plan_alpha_version_evaluation(
        release="v0.1.0-alpha",
        dry_run=False,
        timeout_seconds=1,
        proposals_dir=tmp_path,
    )

    assert output is not None
    assert output.name.startswith("version-evaluation-")
    text = output.read_text(encoding="utf-8")
    assert "STATUS: ADVISORY" in text
    assert "AUTHORITY: NOT_AUTHORIZED_FOR_PUBLISH" in text
    assert "SCOPE: VERSION_NUMBER_EVALUATION_ONLY" in text
    assert "Version number looks appropriate." in text


def test_non_milestone_version_evaluation_is_skipped(tmp_path: Path) -> None:
    output = alpha_release_train.plan_alpha_version_evaluation(
        release="v0.1.1-alpha",
        dry_run=False,
        timeout_seconds=1,
        proposals_dir=tmp_path,
    )

    assert output is None
    assert list(tmp_path.iterdir()) == []


def test_opus_can_select_milestone_alpha_version(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    docs = tmp_path / "docs" / "release-notes"
    docs.mkdir(parents=True)
    (docs / "v0.1.10-alpha.draft.md").write_text("# v0.1.10-alpha\n", encoding="utf-8")
    monkeypatch.setattr(alpha_release_train, "ROOT", tmp_path)
    monkeypatch.setenv(
        "ATTESTPLANE_ALPHA_VERSION_EVAL_FAKE_RESPONSE",
        "verdict: appropriate\nSELECTED_VERSION: v0.2.0-alpha\n",
    )

    selected, advisory = alpha_release_train.resolve_opus_decided_alpha_release(
        release_override=None,
        dry_run=False,
        timeout_seconds=1,
        proposals_dir=tmp_path / "proposals",
    )

    assert selected == "v0.2.0-alpha"
    assert advisory is not None
    assert "SELECTED_VERSION: v0.2.0-alpha" in advisory.read_text(encoding="utf-8")


def test_opus_version_decision_rejects_non_alpha_version(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    docs = tmp_path / "docs" / "release-notes"
    docs.mkdir(parents=True)
    (docs / "v0.1.10-alpha.draft.md").write_text("# v0.1.10-alpha\n", encoding="utf-8")
    monkeypatch.setattr(alpha_release_train, "ROOT", tmp_path)
    monkeypatch.setenv("ATTESTPLANE_ALPHA_VERSION_EVAL_FAKE_RESPONSE", "SELECTED_VERSION: v1.0.0\n")

    with pytest.raises(ValueError, match="invalid alpha release"):
        alpha_release_train.resolve_opus_decided_alpha_release(
            release_override=None,
            dry_run=False,
            timeout_seconds=1,
            proposals_dir=tmp_path / "proposals",
        )


def test_opus_version_decision_rejects_non_increasing_version(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    docs = tmp_path / "docs" / "release-notes"
    docs.mkdir(parents=True)
    (docs / "v0.1.10-alpha.draft.md").write_text("# v0.1.10-alpha\n", encoding="utf-8")
    monkeypatch.setattr(alpha_release_train, "ROOT", tmp_path)
    monkeypatch.setenv("ATTESTPLANE_ALPHA_VERSION_EVAL_FAKE_RESPONSE", "SELECTED_VERSION: v0.1.10-alpha\n")

    with pytest.raises(ValueError, match="must be greater than latest"):
        alpha_release_train.resolve_opus_decided_alpha_release(
            release_override=None,
            dry_run=False,
            timeout_seconds=1,
            proposals_dir=tmp_path / "proposals",
        )


def test_draft_candidate_bundle_is_not_release_queue_entry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(alpha_release_train, "ROOT", tmp_path)
    monkeypatch.setattr(alpha_release_train, "capture", lambda argv: "abc123")
    candidate = alpha_release_train.AlphaCandidate.from_json(
        {
            "release": "v0.0.8-alpha",
            "python_version": "0.0.8a0",
            "npm_version": "0.0.8-alpha",
        }
    )

    prepared_dir = alpha_release_train.write_draft_candidate_bundle(
        candidate,
        advisory_plan=None,
        prepared_root=tmp_path / "prepared",
    )

    manifest = json.loads((prepared_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "attestplane_alpha_prepared_candidate_draft.v1"
    assert manifest["status"] == "draft_unverified_not_queued"
    assert manifest["explicit_non_actions"]["package_version_bump"] == "not performed"
    assert "not release-ready" in (prepared_dir / "READY").read_text(encoding="utf-8")


def test_full_auto_alpha_sets_safe_explicit_release_train_flags() -> None:
    args = alpha_release_train.parse_args(["--full-auto-alpha"])

    assert args.pipeline is True
    assert args.continuous is True
    assert args.auto_promote_prepared is True
    assert args.auto_finalize_next_alpha is True
    assert args.execute is True
    assert args.max_count == 1
    assert args.max_releases_per_day == 0
    assert args.max_prepares_per_day == 0


def test_full_auto_alpha_keeps_stop_file_guard() -> None:
    args = alpha_release_train.parse_args(["--full-auto-alpha"])

    assert args.stop_file == alpha_release_train.DEFAULT_STOP_FILE


def test_continuous_remote_push_failure_cooldowns_without_stop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    queue = write_queue(tmp_path, [candidate("v0.0.8-alpha"), candidate("v0.0.9-alpha")])
    stop_file = tmp_path / "STOP"
    state_file = tmp_path / "state.json"
    calls: list[str] = []
    sleeps: list[int] = []

    def fail_remote_push(
        candidate: alpha_release_train.AlphaCandidate,
        *,
        dry_run: bool,
        state_path: Path | None = None,
    ) -> None:
        calls.append(candidate.release)
        if candidate.release == "v0.0.8-alpha":
            raise alpha_release_train.subprocess.CalledProcessError(
                128,
                ["git", "push", "origin", "main"],
                stderr="fatal: unable to access 'https://github.com/attestplane/attestplane.git/': Failed to connect to github.com port 443 after 75003 ms: Couldn't connect to server",
            )

    monkeypatch.setattr(alpha_release_train, "run_candidate", fail_remote_push)
    monkeypatch.setattr(alpha_release_train.time, "sleep", lambda seconds: sleeps.append(seconds))

    args = alpha_release_train.parse_args(
        [
            "--continuous",
            "--execute",
            "--queue",
            str(queue),
            "--state-file",
            str(state_file),
            "--stop-file",
            str(stop_file),
            "--max-count",
            "2",
            "--idle-exit-after",
            "1",
            "--remote-push-cooldown-seconds",
            "7",
        ]
    )

    assert alpha_release_train.run_continuous_pipeline(args) == 0

    assert calls == ["v0.0.8-alpha", "v0.0.9-alpha"]
    assert sleeps == []
    assert not stop_file.exists()
    assert alpha_release_train.load_continuous_state(state_file)["processed_releases"] == [
        "v0.0.8-alpha",
        "v0.0.9-alpha",
    ]


def test_create_tag_and_release_recovers_existing_head_tag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []
    queue_calls: list[tuple[str, str]] = []
    stage_calls: list[tuple[str, str]] = []
    candidate_value = alpha_release_train.AlphaCandidate.from_json(
        {
            "release": "v0.0.8-alpha",
            "python_version": "0.0.8a0",
            "npm_version": "0.0.8-alpha",
            "create_github_release": False,
        }
    )

    monkeypatch.setattr(alpha_release_train, "local_tag_points_at_head", lambda release: True)
    monkeypatch.setattr(alpha_release_train, "run", lambda argv, *, dry_run, env=None: commands.append(argv))
    monkeypatch.setattr(
        alpha_release_train,
        "enqueue_git_push_task",
        lambda path, candidate, ref, *, dry_run: queue_calls.append((candidate.release, ref)),
    )
    monkeypatch.setattr(
        alpha_release_train,
        "mark_stage",
        lambda path, candidate, stage, status, detail=None: stage_calls.append((stage, status)),
    )

    alpha_release_train.create_tag_and_release(candidate_value, dry_run=False, state_path=tmp_path / "state.json")

    assert ["git", "tag", "-a", "v0.0.8-alpha", "-m", "v0.0.8-alpha"] not in commands
    assert queue_calls == [("v0.0.8-alpha", "v0.0.8-alpha")]
    assert stage_calls == [("tag_pushed", "queued")]


def test_local_tag_points_at_head_suppresses_missing_tag_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(*args: object, **kwargs: object) -> object:
        calls.append({"argv": args[0], "stderr": kwargs.get("stderr")})
        return alpha_release_train.subprocess.CompletedProcess(args[0], 128, "", "fatal: missing tag")

    monkeypatch.setattr(alpha_release_train.subprocess, "run", fake_run)

    assert alpha_release_train.local_tag_points_at_head("v0.1.4-alpha") is False
    assert calls[0]["argv"] == ["git", "rev-list", "-n", "1", "refs/tags/v0.1.4-alpha"]
    assert calls[0]["stderr"] is alpha_release_train.subprocess.DEVNULL


def test_external_stage_ledger_skips_completed_publish_steps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "state.json"
    candidate_value = alpha_release_train.AlphaCandidate.from_json(
        {
            "release": "v0.0.8-alpha",
            "python_version": "0.0.8a0",
            "npm_version": "0.0.8-alpha",
        }
    )
    commands: list[list[str]] = []

    alpha_release_train.mark_stage(state_file, candidate_value, "pypi_published", "done")
    alpha_release_train.mark_stage(state_file, candidate_value, "npm_published", "done")
    alpha_release_train.mark_stage(state_file, candidate_value, "dist_tag_synced", "done")
    monkeypatch.setattr(alpha_release_train, "run", lambda argv, *, dry_run, env=None: commands.append(argv))

    alpha_release_train.publish_platforms(candidate_value, dry_run=False, state_path=state_file)

    assert commands == []
    state = alpha_release_train.load_continuous_state(state_file)
    assert state["release_stages"]["v0.0.8-alpha"]["pypi_published"] == "done"
    assert state["release_stages"]["v0.0.8-alpha"]["npm_published"] == "done"
    assert state["release_stages"]["v0.0.8-alpha"]["dist_tag_synced"] == "done"


def test_registry_verified_stage_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "state.json"
    candidate_value = alpha_release_train.AlphaCandidate.from_json(candidate("v0.0.8-alpha"))

    alpha_release_train.mark_stage(state_file, candidate_value, "registry_verified", "done")
    monkeypatch.setattr(alpha_release_train, "pypi_version_exists", lambda version: (_ for _ in ()).throw(AssertionError))

    alpha_release_train.verify_registries(candidate_value, dry_run=False, state_path=state_file)


def test_finalize_next_alpha_verifies_prebuilt_release_artifacts(monkeypatch: pytest.MonkeyPatch) -> None:
    observed_envs: list[dict[str, str]] = []

    monkeypatch.setattr(alpha_release_train, "assert_clean_tree", lambda: None)
    monkeypatch.setattr(alpha_release_train, "next_alpha_release", lambda: "v0.0.8-alpha")
    monkeypatch.setattr(alpha_release_train, "alpha_release_exists", lambda release: False)
    monkeypatch.setattr(alpha_release_train, "sync_version_state", lambda candidate: None)
    monkeypatch.setattr(alpha_release_train, "write_release_notes", lambda candidate, advisory_plan: None)
    monkeypatch.setattr(alpha_release_train, "build_release_artifacts", lambda candidate: None)
    monkeypatch.setattr(alpha_release_train, "write_release_metadata", lambda candidate: None)
    monkeypatch.setattr(alpha_release_train, "commit_release_prep", lambda candidate: None)

    def fake_run(
        argv: list[str],
        *,
        dry_run: bool,
        env: dict[str, str] | None = None,
    ) -> alpha_release_train.subprocess.CompletedProcess[str]:
        if argv == ["scripts/check-release-assets-prep.sh"] and env is not None:
            observed_envs.append(env)
        return alpha_release_train.subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(alpha_release_train, "run", fake_run)

    candidate = alpha_release_train.finalize_next_alpha(advisory_plan=None)

    assert candidate is not None
    assert candidate.release == "v0.0.8-alpha"
    assert observed_envs[0]["ATTESTPLANE_RELEASE_ASSETS_PREBUILT"] == "1"


def test_finalize_next_alpha_syncs_python_lock_before_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(alpha_release_train, "assert_clean_tree", lambda: calls.append("clean"))
    monkeypatch.setattr(alpha_release_train, "next_alpha_release", lambda: "v0.0.8-alpha")
    monkeypatch.setattr(alpha_release_train, "alpha_release_exists", lambda release: False)
    monkeypatch.setattr(alpha_release_train, "sync_version_state", lambda candidate: calls.extend(["pyproject", "runtime", "uv-lock", "npm", "readme"]))
    monkeypatch.setattr(alpha_release_train, "write_release_notes", lambda candidate, advisory_plan: calls.append("notes"))
    monkeypatch.setattr(alpha_release_train, "build_release_artifacts", lambda candidate: calls.append("artifacts"))
    monkeypatch.setattr(alpha_release_train, "write_release_metadata", lambda candidate: calls.append("metadata"))
    monkeypatch.setattr(alpha_release_train, "commit_release_prep", lambda candidate: calls.append("commit"))

    def fake_run(
        argv: list[str],
        *,
        dry_run: bool,
        env: dict[str, str] | None = None,
    ) -> alpha_release_train.subprocess.CompletedProcess[str]:
        if argv == ["git", "diff", "--check"]:
            calls.append("diff-check")
        elif argv == ["scripts/check-release-assets-prep.sh"]:
            calls.append("prep-gate")
        return alpha_release_train.subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(alpha_release_train, "run", fake_run)

    alpha_release_train.finalize_next_alpha(advisory_plan=None)

    assert calls.index("pyproject") < calls.index("uv-lock") < calls.index("commit")
    assert calls.index("uv-lock") < calls.index("artifacts")


def test_local_gates_verify_prebuilt_release_artifacts(monkeypatch: pytest.MonkeyPatch) -> None:
    observed_envs: list[dict[str, str]] = []
    candidate = alpha_release_train.AlphaCandidate.from_json(
        {
            "release": "v0.0.8-alpha",
            "python_version": "0.0.8a0",
            "npm_version": "0.0.8-alpha",
        }
    )

    def fake_run(
        argv: list[str],
        *,
        dry_run: bool,
        env: dict[str, str] | None = None,
    ) -> alpha_release_train.subprocess.CompletedProcess[str]:
        if argv == ["scripts/check-release-assets-prep.sh"] and env is not None:
            observed_envs.append(env)
        return alpha_release_train.subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(alpha_release_train, "run", fake_run)

    alpha_release_train.run_local_gates(candidate, dry_run=False)

    assert observed_envs[0]["ATTESTPLANE_RELEASE_ASSETS_PREBUILT"] == "1"


def test_release_prep_commit_includes_python_lockfile(monkeypatch: pytest.MonkeyPatch) -> None:
    staged: list[str] = []
    candidate = alpha_release_train.prepared_candidate_from_release("v0.0.8-alpha")

    def fake_run(
        argv: list[str],
        *,
        dry_run: bool,
        env: dict[str, str] | None = None,
    ) -> alpha_release_train.subprocess.CompletedProcess[str]:
        if argv[:2] == ["git", "add"]:
            staged.extend(argv[2:])
        return alpha_release_train.subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(alpha_release_train, "run", fake_run)

    alpha_release_train.commit_release_prep(candidate)

    assert "sdk/python/uv.lock" in staged
    assert "sdk/python/src/attestplane/__init__.py" in staged
    assert "sdk/python/tests/test_import_surface.py" in staged
    assert "sdk/typescript/src/index_version.ts" in staged
    assert "README.md" in staged


def test_sync_version_state_updates_import_surface_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "sdk" / "python" / "src" / "attestplane").mkdir(parents=True)
    (tmp_path / "sdk" / "python" / "tests").mkdir(parents=True)
    (tmp_path / "sdk" / "typescript" / "src").mkdir(parents=True)
    (tmp_path / "sdk" / "python" / "pyproject.toml").write_text(
        'version = "0.1.0a0"\n"Development Status :: 3 - Alpha"\n',
        encoding="utf-8",
    )
    (tmp_path / "sdk" / "python" / "src" / "attestplane" / "__init__.py").write_text(
        '__version__ = "0.1.0a0"\n',
        encoding="utf-8",
    )
    import_surface = tmp_path / "sdk" / "python" / "tests" / "test_import_surface.py"
    import_surface.write_text(
        'def test_import_attestplane_smoke() -> None:\n'
        '    assert attestplane.__version__ == "0.1.0a0"\n',
        encoding="utf-8",
    )
    (tmp_path / "sdk" / "typescript" / "package.json").write_text('{"version": "0.1.0-alpha"}\n', encoding="utf-8")
    (tmp_path / "sdk" / "typescript" / "package-lock.json").write_text(
        '{"version": "0.1.0-alpha", "packages": {"": {"version": "0.1.0-alpha"}}}\n',
        encoding="utf-8",
    )
    (tmp_path / "sdk" / "typescript" / "src" / "index_version.ts").write_text(
        "export const VERSION = '0.1.0-alpha';\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("README placeholder\n", encoding="utf-8")
    candidate = alpha_release_train.prepared_candidate_from_release("v0.1.1-alpha")

    monkeypatch.setattr(alpha_release_train, "ROOT", tmp_path)
    monkeypatch.setattr(alpha_release_train, "sync_python_lockfile", lambda: None)
    monkeypatch.setattr(alpha_release_train, "update_readme_release_state", lambda candidate: None)

    alpha_release_train.sync_version_state(candidate)

    assert 'attestplane.__version__ == "0.1.1a0"' in import_surface.read_text(encoding="utf-8")


def test_parse_args_accepts_explicit_next_alpha_release() -> None:
    args = alpha_release_train.parse_args(["--next-alpha-release", "v0.1.0-alpha"])

    assert args.next_alpha_release == "v0.1.0-alpha"


def test_remote_tag_timeout_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(alpha_release_train, "capture", lambda argv, timeout=None: "https://github.com/attestplane/attestplane.git")

    def fake_run(*args: object, **kwargs: object) -> object:
        argv = args[0]
        if isinstance(argv, list) and argv[:4] == ["git", "rev-parse", "-q", "--verify"]:
            return alpha_release_train.subprocess.CompletedProcess(argv, 1, "", "")
        raise alpha_release_train.subprocess.TimeoutExpired(cmd=argv, timeout=45)

    monkeypatch.setattr(alpha_release_train.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="remote tag check timed out"):
        alpha_release_train.alpha_release_exists("v0.0.8-alpha")


def test_remote_tag_check_uses_github_api(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(alpha_release_train, "capture", lambda argv, timeout=None: "https://github.com/attestplane/attestplane.git")

    def fake_run(*args: object, **kwargs: object) -> object:
        argv = args[0]
        calls.append(argv)
        return alpha_release_train.subprocess.CompletedProcess(argv, 1, "", "")

    monkeypatch.setattr(alpha_release_train.subprocess, "run", fake_run)

    assert alpha_release_train.remote_tag_exists("v0.0.8-alpha") is False
    assert calls[0][:3] == ["gh", "api", "repos/attestplane/attestplane/git/ref/tags/v0.0.8-alpha"]


def test_continuous_unhandled_exception_writes_stop_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    stop_file = tmp_path / "STOP"

    def fail_continuous(args: object) -> int:
        raise RuntimeError("boom")

    monkeypatch.setattr(alpha_release_train, "run_continuous_pipeline", fail_continuous)

    with pytest.raises(RuntimeError, match="boom"):
        alpha_release_train.main(["--continuous", "--execute", "--stop-file", str(stop_file)])

    assert "fail-closed continuous pipeline: RuntimeError" in stop_file.read_text(encoding="utf-8")


def test_registry_verification_retries_for_propagation(monkeypatch: pytest.MonkeyPatch) -> None:
    candidate = alpha_release_train.AlphaCandidate.from_json(
        {
            "release": "v0.0.8-alpha",
            "python_version": "0.0.8a0",
            "npm_version": "0.0.8-alpha",
        }
    )
    pypi_payloads = [
        {"releases": {}},
        {"releases": {"0.0.8a0": []}},
    ]

    class FakeResponse(io.StringIO):
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(*args: object, **kwargs: object) -> FakeResponse:
        return FakeResponse(json.dumps(pypi_payloads.pop(0)))

    def fake_capture(argv: list[str], *, timeout: int | None = None) -> str:
        return json.dumps({"version": "0.0.8-alpha", "dist-tags": {"alpha": "0.0.8-alpha", "latest": "0.0.8-alpha"}})

    monkeypatch.setattr(alpha_release_train.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(alpha_release_train, "capture", fake_capture)
    monkeypatch.setattr(alpha_release_train.time, "sleep", lambda seconds: None)

    alpha_release_train.verify_registries(candidate, dry_run=False)

    assert pypi_payloads == []


def test_publish_platforms_syncs_npm_latest_after_alpha_publish(monkeypatch: pytest.MonkeyPatch) -> None:
    candidate = alpha_release_train.AlphaCandidate.from_json(
        {
            "release": "v0.0.8-alpha",
            "python_version": "0.0.8a0",
            "npm_version": "0.0.8-alpha",
            "publish_python": False,
        }
    )
    commands: list[list[str]] = []
    run_ids = iter(["npm-run-id", "manage-npm-run-id"])

    def fake_run(
        argv: list[str],
        *,
        dry_run: bool,
        env: dict[str, str] | None = None,
    ) -> alpha_release_train.subprocess.CompletedProcess[str]:
        commands.append(argv)
        return alpha_release_train.subprocess.CompletedProcess(argv, 0, "", "")

    def fake_capture(argv: list[str], *, timeout: int | None = None) -> str:
        if argv[:4] == ["gh", "run", "list", "--workflow"]:
            return next(run_ids)
        return ""

    monkeypatch.setattr(alpha_release_train, "run", fake_run)
    monkeypatch.setattr(alpha_release_train, "capture", fake_capture)
    monkeypatch.setattr(alpha_release_train.time, "sleep", lambda seconds: None)

    alpha_release_train.publish_platforms(candidate, dry_run=False)

    assert [
        "gh",
        "workflow",
        "run",
        "manage-npm.yml",
        "-f",
        "action=dist-tag-set-latest-to-version",
        "-f",
        "version=0.0.8-alpha",
        "--ref",
        "main",
    ] in commands
    assert ["gh", "run", "watch", "manage-npm-run-id", "--exit-status"] in commands


def test_publish_platforms_retries_transient_pypi_watch_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "state.json"
    candidate = alpha_release_train.AlphaCandidate.from_json(
        {
            "release": "v0.0.8-alpha",
            "python_version": "0.0.8a0",
            "npm_version": "0.0.8-alpha",
            "publish_npm": False,
        }
    )
    commands: list[list[str]] = []
    run_ids = iter(["python-run-1", "python-run-2"])
    watch_attempts = 0

    def fake_run(
        argv: list[str],
        *,
        dry_run: bool,
        env: dict[str, str] | None = None,
    ) -> alpha_release_train.subprocess.CompletedProcess[str]:
        nonlocal watch_attempts
        commands.append(argv)
        if argv[:3] == ["gh", "run", "watch"]:
            watch_attempts += 1
            if watch_attempts == 1:
                raise alpha_release_train.subprocess.CalledProcessError(1, argv)
        return alpha_release_train.subprocess.CompletedProcess(argv, 0, "", "")

    def fake_capture(argv: list[str], *, timeout: int | None = None) -> str:
        if argv[:4] == ["gh", "run", "list", "--workflow"] and argv[4] == "publish-python.yml":
            return next(run_ids)
        return ""

    monkeypatch.setattr(alpha_release_train, "run", fake_run)
    monkeypatch.setattr(alpha_release_train, "capture", fake_capture)
    monkeypatch.setattr(alpha_release_train, "pypi_version_exists", lambda version: False)
    monkeypatch.setattr(alpha_release_train.time, "sleep", lambda seconds: None)

    alpha_release_train.publish_platforms(candidate, dry_run=False, state_path=state_file)

    assert commands.count(["gh", "workflow", "run", "publish-python.yml", "-f", "target=pypi", "--ref", "main"]) == 2
    assert commands.count(["gh", "run", "watch", "python-run-1", "--exit-status"]) == 1
    assert commands.count(["gh", "run", "watch", "python-run-2", "--exit-status"]) == 1
    state = alpha_release_train.load_continuous_state(state_file)
    assert state["release_stages"]["v0.0.8-alpha"]["pypi_published"] == "done"
