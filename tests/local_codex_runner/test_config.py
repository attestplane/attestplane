from pathlib import Path

import pytest
from scripts.local_codex_runner.config import ConfigError, load_config, parse_simple_yaml


def test_config_defaults_to_dry_run(tmp_path: Path) -> None:
    config_path = tmp_path / "runner.yml"
    config_path.write_text('repo: "attestplane/attestplane"\nworkdir: "/tmp/attestplane"\n', encoding="utf-8")

    config = load_config(config_path)

    assert config.dry_run is True
    assert config.approved_label == "auto-codex-approved"
    assert config.codex_timeout_seconds == 1800


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


def test_checkout_ref_defaults_to_pr_base(tmp_path: Path) -> None:
    config_path = tmp_path / "runner.yml"
    config_path.write_text('repo: "attestplane/attestplane"\nworkdir: "/tmp/attestplane"\n', encoding="utf-8")

    config = load_config(config_path)

    assert config.checkout_ref() == "main"


def test_checkout_ref_can_use_remote_tracking_ref(tmp_path: Path) -> None:
    config_path = tmp_path / "runner.yml"
    config_path.write_text(
        'repo: "attestplane/attestplane"\n'
        'workdir: "/tmp/attestplane"\n'
        'base_branch: "main"\n'
        'base_checkout_ref: "origin/main"\n',
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.base_branch == "main"
    assert config.checkout_ref() == "origin/main"


def test_auto_merge_requires_author_whitelist(tmp_path: Path) -> None:
    config_path = tmp_path / "runner.yml"
    config_path.write_text(
        'repo: "attestplane/attestplane"\n'
        'workdir: "/tmp/attestplane"\n'
        "allow_auto_merge: true\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="allowed_pr_authors"):
        load_config(config_path)


def test_lane_config_accepts_label_filters(tmp_path: Path) -> None:
    config_path = tmp_path / "runner.yml"
    config_path.write_text(
        'repo: "attestplane/attestplane"\n'
        'workdir: "/tmp/attestplane-p0"\n'
        'lane_name: "p0"\n'
        "lane_slot: 1\n"
        "lane_include_labels:\n"
        '  - "priority-P0"\n'
        "lane_exclude_labels:\n"
        '  - "codex-needs-human"\n',
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.lane_name == "p0"
    assert config.lane_slot == 1
    assert config.lane_include_labels == ["priority-P0"]
    assert config.lane_exclude_labels == ["codex-needs-human"]


def test_config_accepts_needs_human_recovery_controls(tmp_path: Path) -> None:
    config_path = tmp_path / "runner.yml"
    config_path.write_text(
        'repo: "attestplane/attestplane"\n'
        'workdir: "/tmp/attestplane-p0"\n'
        'codex_model: "gpt-5.4-mini"\n'
        "auto_recover_needs_human: true\n"
        "max_needs_human_recoveries_per_run: 1\n"
        "max_needs_human_attempts: 1\n"
        "needs_human_policy_block_labels: []\n"
        "needs_human_recoverable_reasons:\n"
        '  - "rate_limit"\n',
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.codex_model == "gpt-5.4-mini"
    assert config.auto_recover_needs_human is True
    assert config.max_needs_human_recoveries_per_run == 1
    assert config.max_needs_human_attempts == 1
    assert config.needs_human_policy_block_labels == []
    assert config.needs_human_recoverable_reasons == ["rate_limit"]


def test_lane_slot_must_be_positive(tmp_path: Path) -> None:
    config_path = tmp_path / "runner.yml"
    config_path.write_text(
        'repo: "attestplane/attestplane"\n'
        'workdir: "/tmp/attestplane-p0"\n'
        "lane_slot: 0\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="lane_slot"):
        load_config(config_path)


def test_codex_timeout_must_be_positive(tmp_path: Path) -> None:
    config_path = tmp_path / "runner.yml"
    config_path.write_text(
        'repo: "attestplane/attestplane"\n'
        'workdir: "/tmp/attestplane"\n'
        "codex_timeout_seconds: 0\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="codex_timeout_seconds"):
        load_config(config_path)


def test_simple_yaml_parser_allows_colon_in_mapping_key(tmp_path: Path) -> None:
    config_path = tmp_path / "gates.yml"
    parsed = parse_simple_yaml(
        'default:\n  - "pytest -q"\narea:verifier:\n  - "pytest tests/verifier -q"\n',
        config_path,
    )

    assert parsed["area:verifier"] == ["pytest tests/verifier -q"]
