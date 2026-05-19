from __future__ import annotations

import importlib.util
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
    report = alpha_release_train.write_pipeline_report(
        advisory_plan=plan,
        queue=tmp_path / "queue.json",
        candidates=[],
        executed=False,
        reports_dir=tmp_path,
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["schema"] == "attestplane_alpha_release_pipeline_report.v1"
    assert payload["stages"][0]["authority"] == "advisory_only"
    assert payload["stages"][1]["candidate_count"] == 0
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


def test_daily_release_count_defaults_to_zero(tmp_path: Path) -> None:
    assert alpha_release_train.daily_release_count(tmp_path / "missing-state.json") == 0


def test_next_alpha_release_from_notes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    docs = tmp_path / "docs" / "release-notes"
    docs.mkdir(parents=True)
    (docs / "v0.0.9-alpha.draft.md").write_text("# v0.0.9-alpha\n", encoding="utf-8")
    (docs / "v0.0.10-alpha.draft.md").write_text("# v0.0.10-alpha\n", encoding="utf-8")
    monkeypatch.setattr(alpha_release_train, "ROOT", tmp_path)
    assert alpha_release_train.next_alpha_release() == "v0.0.11-alpha"


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
