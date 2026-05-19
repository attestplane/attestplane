from pathlib import Path

import pytest

from scripts.local_codex_runner.config import ConfigError, load_config


def test_config_defaults_to_dry_run(tmp_path: Path) -> None:
    config_path = tmp_path / "runner.yml"
    config_path.write_text('repo: "attestplane/attestplane"\nworkdir: "/tmp/attestplane"\n', encoding="utf-8")

    config = load_config(config_path)

    assert config.dry_run is True
    assert config.approved_label == "auto-codex-approved"


def test_config_requires_repo_and_workdir(tmp_path: Path) -> None:
    config_path = tmp_path / "runner.yml"
    config_path.write_text("dry_run: true\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="repo, workdir"):
        load_config(config_path)


def test_cli_overrides_config(tmp_path: Path) -> None:
    config_path = tmp_path / "runner.yml"
    config_path.write_text('repo: "old/repo"\nworkdir: "/tmp/old"\ndry_run: true\n', encoding="utf-8")

    config = load_config(config_path, {"repo": "new/repo", "dry_run": False})

    assert config.repo == "new/repo"
    assert config.dry_run is False

