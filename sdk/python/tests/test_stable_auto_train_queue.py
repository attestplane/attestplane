from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts/release/stable_auto_train.py"

spec = importlib.util.spec_from_file_location("stable_auto_train", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
stable_auto_train = importlib.util.module_from_spec(spec)
sys.modules["stable_auto_train"] = stable_auto_train
spec.loader.exec_module(stable_auto_train)


def test_target_queue_loads_strictly_increasing_stable_targets(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    queue.write_text(
        json.dumps(
            {
                "schema": "attestplane_autodev_train_targets.v2",
                "targets": [
                    {"version": "0.8.6", "status": "queued", "channel": "latest", "min_soak_hours": 0},
                    {"version": "0.9.0", "status": "queued", "channel": "latest", "min_soak_hours": 0},
                ],
            }
        ),
        encoding="utf-8",
    )

    targets = stable_auto_train.load_target_queue(queue)

    assert [target.version.tag for target in targets] == ["v0.8.6", "v0.9.0"]
    assert all(target.channel == "latest" for target in targets)


def test_target_queue_rejects_rc_channel(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    queue.write_text(
        json.dumps(
            {
                "schema": "attestplane_autodev_train_targets.v2",
                "targets": [
                    {"version": "0.8.6", "status": "queued", "channel": "rc", "min_soak_hours": 0},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="unsupported"):
        stable_auto_train.load_target_queue(queue)


def test_target_queue_rejects_non_increasing_versions(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    queue.write_text(
        json.dumps(
            {
                "schema": "attestplane_autodev_train_targets.v2",
                "targets": [
                    {"version": "0.8.7", "status": "queued", "channel": "latest", "min_soak_hours": 0},
                    {"version": "0.8.6", "status": "queued", "channel": "latest", "min_soak_hours": 0},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="strictly increasing"):
        stable_auto_train.load_target_queue(queue)


def test_next_stable_after_advances_patch_until_ten() -> None:
    current = stable_auto_train.StableVersion.parse("0.8.9")

    assert stable_auto_train.next_stable_after(current).tag == "v0.8.10"


def test_next_stable_after_rolls_patch_ten_to_next_minor_zero() -> None:
    current = stable_auto_train.StableVersion.parse("0.8.10")

    assert stable_auto_train.next_stable_after(current).tag == "v0.9.0"


def test_next_stable_after_continues_after_minor_boundary() -> None:
    current = stable_auto_train.StableVersion.parse("0.9.0")

    assert stable_auto_train.next_stable_after(current).tag == "v0.9.1"


def test_next_stable_after_rolls_zero_nine_ten_to_one_zero_zero() -> None:
    current = stable_auto_train.StableVersion.parse("0.9.10")

    assert stable_auto_train.next_stable_after(current).tag == "v1.0.0"


def test_next_stable_after_rolls_post_one_patch_ten_to_next_minor_zero() -> None:
    current = stable_auto_train.StableVersion.parse("1.0.10")

    assert stable_auto_train.next_stable_after(current).tag == "v1.1.0"


def test_select_target_recovers_latest_incomplete_tag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    queue.write_text(
        json.dumps(
            {
                "schema": "attestplane_autodev_train_targets.v2",
                "targets": [
                    {"version": "1.0.7", "status": "queued", "channel": "latest", "min_soak_hours": 0},
                ],
            }
        ),
        encoding="utf-8",
    )
    latest = stable_auto_train.StableVersion.parse("1.0.6")
    monkeypatch.setattr(stable_auto_train, "latest_stable", lambda: latest)
    monkeypatch.setattr(
        stable_auto_train,
        "publication_status",
        lambda version: stable_auto_train.PublicationStatus(
            python_visible=False,
            npm_visible=True,
            npm_latest=True,
            github_release=False,
        ),
    )

    target = stable_auto_train.select_target(queue)

    assert target.version.tag == "v1.0.6"


def test_recover_existing_release_repairs_transient_python_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = stable_auto_train.StableVersion.parse("1.0.6")
    status_checks = iter(
        [
            stable_auto_train.PublicationStatus(
                python_visible=False,
                npm_visible=True,
                npm_latest=True,
                github_release=False,
            ),
            stable_auto_train.PublicationStatus(
                python_visible=True,
                npm_visible=True,
                npm_latest=True,
                github_release=True,
            ),
        ]
    )
    calls: list[str] = []
    monkeypatch.setattr(stable_auto_train, "publication_status", lambda target: next(status_checks))
    monkeypatch.setattr(stable_auto_train, "dispatch_publish_python", lambda target: calls.append("publish-python"))
    monkeypatch.setattr(stable_auto_train, "wait_for_pypi", lambda target: calls.append("wait-pypi"))
    monkeypatch.setattr(stable_auto_train, "ensure_github_release", lambda target: calls.append("github-release"))

    stable_auto_train.recover_existing_release(version)

    assert calls == ["publish-python", "wait-pypi", "github-release"]


def test_recover_existing_release_refuses_incomplete_npm_state() -> None:
    version = stable_auto_train.StableVersion.parse("1.0.6")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            stable_auto_train,
            "publication_status",
            lambda target: stable_auto_train.PublicationStatus(
                python_visible=True,
                npm_visible=False,
                npm_latest=False,
                github_release=False,
            ),
        )
        with pytest.raises(RuntimeError, match="npm state is incomplete"):
            stable_auto_train.recover_existing_release(version)


def test_recover_existing_release_retries_later_on_unknown_probe() -> None:
    version = stable_auto_train.StableVersion.parse("1.0.6")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            stable_auto_train,
            "publication_status",
            lambda target: stable_auto_train.PublicationStatus(
                python_visible=None,
                npm_visible=True,
                npm_latest=True,
                github_release=True,
            ),
        )
        with pytest.raises(RuntimeError, match="probe is incomplete"):
            stable_auto_train.recover_existing_release(version)


def test_run_once_resumes_locally_tagged_unpublished_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    queue = tmp_path / "queue.json"
    queue.write_text(
        json.dumps(
            {
                "schema": "attestplane_autodev_train_targets.v2",
                "targets": [
                    {"version": "1.0.9", "status": "queued", "channel": "latest", "min_soak_hours": 0},
                ],
            }
        ),
        encoding="utf-8",
    )
    version = stable_auto_train.StableVersion.parse("1.0.9")
    calls: list[str] = []

    monkeypatch.setattr(stable_auto_train, "assert_clean_tree", lambda: None)
    monkeypatch.setattr(stable_auto_train, "assert_on_main", lambda: None)
    monkeypatch.setattr(stable_auto_train, "best_effort_fetch_tags", lambda: None)
    monkeypatch.setattr(stable_auto_train, "latest_stable", lambda: version)
    monkeypatch.setattr(stable_auto_train, "latest_stable_before", lambda target: stable_auto_train.StableVersion.parse("1.0.8"))
    monkeypatch.setattr(stable_auto_train, "assert_release_gate_allows_target", lambda target: None)
    monkeypatch.setattr(stable_auto_train, "git_ref_exists", lambda ref: ref == "refs/tags/v1.0.9")
    monkeypatch.setattr(stable_auto_train, "remote_tag_exists", lambda tag: False)
    monkeypatch.setattr(stable_auto_train, "local_tag_points_to_head", lambda tag: True)
    monkeypatch.setattr(
        stable_auto_train,
        "publication_status",
        lambda target: stable_auto_train.PublicationStatus(
            python_visible=False,
            npm_visible=False,
            npm_latest=False,
            github_release=False,
        ),
    )
    monkeypatch.setattr(
        stable_auto_train,
        "resume_tagged_release_publish",
        lambda target, *, wait: calls.append(f"resume:{target.tag}:wait={wait}"),
    )
    monkeypatch.setattr(stable_auto_train, "recover_existing_release", lambda target: calls.append("recover"))

    result = stable_auto_train.run_once(publish=True, wait=True, target_queue=queue, dry_run=False)

    assert result == "v1.0.9"
    assert calls == ["resume:v1.0.9:wait=True"]


def test_run_once_refuses_unknown_status_for_existing_tag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    queue = tmp_path / "queue.json"
    queue.write_text(
        json.dumps(
            {
                "schema": "attestplane_autodev_train_targets.v2",
                "targets": [
                    {"version": "1.0.9", "status": "queued", "channel": "latest", "min_soak_hours": 0},
                ],
            }
        ),
        encoding="utf-8",
    )
    version = stable_auto_train.StableVersion.parse("1.0.9")

    monkeypatch.setattr(stable_auto_train, "assert_clean_tree", lambda: None)
    monkeypatch.setattr(stable_auto_train, "assert_on_main", lambda: None)
    monkeypatch.setattr(stable_auto_train, "best_effort_fetch_tags", lambda: None)
    monkeypatch.setattr(stable_auto_train, "latest_stable", lambda: version)
    monkeypatch.setattr(stable_auto_train, "latest_stable_before", lambda target: stable_auto_train.StableVersion.parse("1.0.8"))
    monkeypatch.setattr(stable_auto_train, "assert_release_gate_allows_target", lambda target: None)
    monkeypatch.setattr(stable_auto_train, "git_ref_exists", lambda ref: ref == "refs/tags/v1.0.9")
    monkeypatch.setattr(stable_auto_train, "remote_tag_exists", lambda tag: False)
    monkeypatch.setattr(stable_auto_train, "local_tag_points_to_head", lambda tag: True)
    monkeypatch.setattr(
        stable_auto_train,
        "publication_status",
        lambda target: stable_auto_train.PublicationStatus(
            python_visible=None,
            npm_visible=False,
            npm_latest=False,
            github_release=False,
        ),
    )

    with pytest.raises(RuntimeError, match="publication status probe is incomplete"):
        stable_auto_train.run_once(publish=True, wait=True, target_queue=queue, dry_run=False)


def test_stable_train_blocks_unverified_major_boundary() -> None:
    target = stable_auto_train.ReleaseTarget(
        version=stable_auto_train.StableVersion.parse("1.0.0"),
        channel="latest",
        min_soak_hours=0,
    )

    with pytest.raises(RuntimeError, match="audit_required_without_verified_plan"):
        stable_auto_train.assert_release_gate_allows_target(target)


def test_wait_for_push_ci_allows_successful_required_workflows(monkeypatch: pytest.MonkeyPatch) -> None:
    head_sha = "abc123"
    runs = [
        {
            "conclusion": "success",
            "databaseId": index,
            "headSha": head_sha,
            "name": name,
            "status": "completed",
            "url": f"https://example.test/{name}",
        }
        for index, name in enumerate(stable_auto_train.PUSH_CI_WORKFLOWS, start=1)
    ]

    monkeypatch.setattr(stable_auto_train, "capture", lambda argv: json.dumps(runs))

    stable_auto_train.wait_for_push_ci(head_sha)


def test_wait_for_push_ci_blocks_failed_required_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    head_sha = "abc123"
    runs = [
        {
            "conclusion": "success",
            "databaseId": index,
            "headSha": head_sha,
            "name": name,
            "status": "completed",
            "url": f"https://example.test/{name}",
        }
        for index, name in enumerate(stable_auto_train.PUSH_CI_WORKFLOWS, start=1)
    ]
    runs[0] = {**runs[0], "conclusion": "failure"}

    monkeypatch.setattr(stable_auto_train, "capture", lambda argv: json.dumps(runs))

    with pytest.raises(RuntimeError, match=r"push CI failed.*ci=failure"):
        stable_auto_train.wait_for_push_ci(head_sha)


def test_release_cd_dispatch_args_omits_audit_inputs_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATTESTPLANE_RELEASE_AUDIT_VERIFIED", raising=False)
    monkeypatch.delenv("ATTESTPLANE_RELEASE_AUDIT_PLAN_URL", raising=False)
    version = stable_auto_train.StableVersion.parse("0.9.10")

    argv = stable_auto_train.release_cd_dispatch_args(version)

    assert "audit_verified=true" not in argv
    assert all(not item.startswith("audit_plan_url=") for item in argv)
    assert argv[-2:] == ["--ref", "main"]


def test_release_cd_dispatch_args_forwards_verified_audit_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    audit_plan_url = (
        "https://github.com/attestplane/attestplane/blob/main/"
        "docs/validation/v1_0_0_release_audit_plan_20260520.md"
    )
    monkeypatch.setenv("ATTESTPLANE_RELEASE_AUDIT_VERIFIED", "1")
    monkeypatch.setenv("ATTESTPLANE_RELEASE_AUDIT_PLAN_URL", audit_plan_url)
    version = stable_auto_train.StableVersion.parse("1.0.0")

    argv = stable_auto_train.release_cd_dispatch_args(version)

    assert "audit_verified=true" in argv
    assert f"audit_plan_url={audit_plan_url}" in argv
    assert argv[-2:] == ["--ref", "main"]


def test_write_release_notes_uses_subjects_without_commit_hashes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "docs/release-notes").mkdir(parents=True)
    monkeypatch.setattr(stable_auto_train, "ROOT", tmp_path)
    monkeypatch.setattr(
        stable_auto_train,
        "capture",
        lambda argv: "fix(release): wait for push CI before publishing stable train\n"
        "docs(release): approve v1.0.0 audit gate",
    )

    stable_auto_train.write_release_notes(
        stable_auto_train.StableVersion.parse("0.9.10"),
        stable_auto_train.StableVersion.parse("1.0.0"),
    )

    notes = (tmp_path / "docs/release-notes/v1.0.0.draft.md").read_text(encoding="utf-8")
    assert "abc1234" not in notes
    assert "- fix(release): wait for push CI before publishing stable train" in notes
