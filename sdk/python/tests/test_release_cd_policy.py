from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts/release/validate_release_cd.py"

spec = importlib.util.spec_from_file_location("validate_release_cd", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
validate_release_cd = importlib.util.module_from_spec(spec)
sys.modules["validate_release_cd"] = validate_release_cd
spec.loader.exec_module(validate_release_cd)


def _write_package_versions(root: Path, *, python_version: str, npm_version: str) -> None:
    pyproject = root / "sdk/python/pyproject.toml"
    package_json = root / "sdk/typescript/package.json"
    pyproject.parent.mkdir(parents=True)
    package_json.parent.mkdir(parents=True)
    pyproject.write_text(f"[project]\nversion = \"{python_version}\"\n", encoding="utf-8")
    package_json.write_text(json.dumps({"version": npm_version}), encoding="utf-8")


@pytest.mark.parametrize(
    ("tag", "expected_python", "expected_npm", "expected_channel", "is_prerelease"),
    [
        ("v0.8.0-alpha.0", "0.8.0a0", "0.8.0-alpha.0", "alpha", True),
        ("v0.8.0-beta.0", "0.8.0b0", "0.8.0-beta.0", "beta", True),
        ("v0.8.0-rc.1", "0.8.0rc1", "0.8.0-rc.1", "rc", True),
        ("v0.8.0", "0.8.0", "0.8.0", "latest", False),
    ],
)
def test_expected_versions(
    tag: str,
    expected_python: str,
    expected_npm: str,
    expected_channel: str,
    is_prerelease: bool,
) -> None:
    python_version, npm_version, channel, prerelease = validate_release_cd.expected_versions(tag)
    assert python_version == expected_python
    assert npm_version == expected_npm
    assert channel == expected_channel
    assert prerelease is is_prerelease


def test_release_cd_policy_accepts_matching_rc_versions(tmp_path: Path) -> None:
    _write_package_versions(tmp_path, python_version="0.8.0rc1", npm_version="0.8.0-rc.1")

    decision = validate_release_cd.decide_release(
        release_tag="v0.8.0-rc.1",
        requested_channel="rc",
        repo_root=tmp_path,
    )

    assert decision.python_version == "0.8.0rc1"
    assert decision.npm_version == "0.8.0-rc.1"
    assert decision.npm_dist_tag == "rc"
    assert decision.is_prerelease is True


def test_release_cd_policy_rejects_prerelease_latest(tmp_path: Path) -> None:
    _write_package_versions(tmp_path, python_version="0.8.0rc1", npm_version="0.8.0-rc.1")

    with pytest.raises(validate_release_cd.ReleaseCdPolicyError, match="does not match"):
        validate_release_cd.decide_release(
            release_tag="v0.8.0-rc.1",
            requested_channel="latest",
            repo_root=tmp_path,
        )


def test_release_cd_policy_allows_prerelease_latest_only_with_explicit_override(
    tmp_path: Path,
) -> None:
    _write_package_versions(tmp_path, python_version="0.8.0b0", npm_version="0.8.0-beta.0")

    decision = validate_release_cd.decide_release(
        release_tag="v0.8.0-beta.0",
        requested_channel="latest",
        repo_root=tmp_path,
        allow_prerelease_latest=True,
    )

    assert decision.npm_dist_tag == "latest"
    assert decision.is_prerelease is True


@pytest.mark.parametrize(
    ("tag", "python_version", "npm_version", "requested_channel"),
    [
        ("v0.8.0-alpha.0", "0.8.0a0", "0.8.0-alpha.0", "beta"),
        ("v0.8.0-beta.0", "0.8.0b0", "0.8.0-beta.0", "rc"),
        ("v0.8.0-rc.1", "0.8.0rc1", "0.8.0-rc.1", "beta"),
        ("v0.8.0", "0.8.0", "0.8.0", "rc"),
    ],
)
def test_release_cd_policy_rejects_channel_drift(
    tmp_path: Path,
    tag: str,
    python_version: str,
    npm_version: str,
    requested_channel: str,
) -> None:
    _write_package_versions(tmp_path, python_version=python_version, npm_version=npm_version)

    with pytest.raises(validate_release_cd.ReleaseCdPolicyError, match="does not match"):
        validate_release_cd.decide_release(
            release_tag=tag,
            requested_channel=requested_channel,
            repo_root=tmp_path,
        )


def test_release_cd_policy_rejects_package_version_drift(tmp_path: Path) -> None:
    _write_package_versions(tmp_path, python_version="0.8.0b0", npm_version="0.8.0-rc.1")

    with pytest.raises(validate_release_cd.ReleaseCdPolicyError, match="Python package version"):
        validate_release_cd.decide_release(
            release_tag="v0.8.0-rc.1",
            requested_channel="rc",
            repo_root=tmp_path,
        )


def test_release_cd_policy_can_read_metadata_from_git_ref(tmp_path: Path) -> None:
    _write_package_versions(tmp_path, python_version="0.8.0rc1", npm_version="0.8.0-rc.1")
    git = shutil.which("git")
    assert git is not None

    subprocess.run([git, "init"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)  # noqa: S603
    subprocess.run([git, "add", "."], cwd=tmp_path, check=True)  # noqa: S603
    subprocess.run(  # noqa: S603
        [git, "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-m", "snapshot"],
        cwd=tmp_path,
        check=True,
        stdout=subprocess.PIPE,
    )

    decision = validate_release_cd.decide_release(
        release_tag="v0.8.0-rc.1",
        requested_channel="rc",
        repo_root=tmp_path,
        metadata_ref="HEAD",
    )

    assert decision.npm_dist_tag == "rc"
