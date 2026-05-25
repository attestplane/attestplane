#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Configuration loading for the local Codex runner."""

from __future__ import annotations

import argparse
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RunnerConfig:
    repo: str | None = None
    workdir: str | None = None
    base_branch: str = "main"
    base_checkout_ref: str | None = None
    approved_label: str = "auto-codex-approved"
    candidate_label: str = "auto-codex-candidate"
    in_progress_label: str = "codex-in-progress"
    pr_opened_label: str = "codex-pr-opened"
    ci_green_label: str = "codex-ci-green"
    needs_human_label: str = "codex-needs-human"
    max_issues_per_run: int = 3
    max_local_fix_rounds: int = 3
    max_ci_fix_rounds: int = 2
    dry_run: bool = True
    watch_ci: bool = True
    create_pr: bool = True
    codex_command: str = "codex"
    codex_command_template: str | None = None
    codex_model: str | None = None
    codex_sandbox: str = "workspace-write"
    codex_timeout_seconds: int = 1800
    allow_danger_full_access: bool = False
    allow_dirty: bool = False
    allow_push_on_local_failure: bool = False
    allow_rerun: bool = False
    state_path: str = ".local_codex_runner/state.json"
    evidence_dir: str = "docs/validation/local_codex_runner"
    gate_matrix_path: str = ".local-codex-gates.yml"
    gate_timeout_seconds: int = 900
    ci_timeout_seconds: int = 1800
    ci_poll_seconds: int = 30
    auto_advance_before_consume: bool = False
    allow_auto_merge: bool = False
    allow_dependency_unlock: bool = False
    auto_merge_ready_label: str = "auto-merge-ready"
    planned_task_label: str = "planned-task"
    waiting_deps_label: str = "status:waiting-deps"
    blocking_pr_labels: list[str] = field(default_factory=lambda: ["do-not-merge", "hold", "wip"])
    allowed_pr_authors: list[str] = field(default_factory=list)
    max_pr_merges_per_run: int = 1
    max_dependency_unlocks_per_run: int = 5
    cleanup_stale_state: bool = True
    auto_recover_needs_human: bool = False
    needs_human_scan_limit: int = 100
    max_needs_human_recoveries_per_run: int = 2
    max_needs_human_attempts: int = 2
    needs_human_recovered_label: str = "codex-recovered"
    needs_human_policy_block_labels: list[str] = field(
        default_factory=lambda: ["codex-policy-blocked", "codex-external-blocked", "do-not-merge", "hold"]
    )
    needs_human_recoverable_reasons: list[str] = field(
        default_factory=lambda: ["rate_limit", "network_timeout", "ci_failed"]
    )
    lane_name: str | None = None
    lane_slot: int | None = None
    lane_include_labels: list[str] = field(default_factory=list)
    lane_exclude_labels: list[str] = field(default_factory=list)
    product_delta_idle_dispatch: bool = False
    product_delta_idle_log_glob: str | None = None
    product_delta_idle_threshold: int = 2
    product_delta_idle_tail_lines: int = 200
    product_delta_idle_create_task: bool = False
    product_delta_idle_task_title: str = "[P1][sdk][verifier] Add product implementation delta for stalled stable train"
    product_delta_idle_task_labels: list[str] = field(default_factory=list)

    def validate(self) -> None:
        missing = [name for name in ("repo", "workdir") if not getattr(self, name)]
        if missing:
            raise ConfigError(f"Missing required local Codex runner config field(s): {', '.join(missing)}")
        if self.codex_sandbox == "danger-full-access" and not self.allow_danger_full_access:
            raise ConfigError("danger-full-access requires allow_danger_full_access=true")
        if self.codex_timeout_seconds < 1:
            raise ConfigError("codex_timeout_seconds must be a positive integer")
        if self.needs_human_scan_limit < 1:
            raise ConfigError("needs_human_scan_limit must be a positive integer")
        if self.allow_auto_merge and not self.allowed_pr_authors:
            raise ConfigError("allow_auto_merge requires at least one allowed_pr_authors entry")
        if self.lane_slot is not None and self.lane_slot < 1:
            raise ConfigError("lane_slot must be a positive integer")
        if self.product_delta_idle_threshold < 1:
            raise ConfigError("product_delta_idle_threshold must be a positive integer")
        if self.product_delta_idle_tail_lines < 1:
            raise ConfigError("product_delta_idle_tail_lines must be a positive integer")

    def workdir_path(self) -> Path:
        if self.workdir is None:
            raise ConfigError("workdir is required")
        return Path(self.workdir).expanduser().resolve()

    def state_file(self) -> Path:
        return self.workdir_path() / self.state_path

    def evidence_root(self) -> Path:
        return self.workdir_path() / self.evidence_dir

    def gate_matrix_file(self) -> Path:
        return self.workdir_path() / self.gate_matrix_path

    def checkout_ref(self) -> str:
        return self.base_checkout_ref or self.base_branch


class ConfigError(ValueError):
    """Raised when runner configuration is invalid."""


def load_config(path: Path | None, overrides: dict[str, Any] | None = None) -> RunnerConfig:
    data: dict[str, Any] = {}
    if path is not None and path.exists():
        data.update(load_yaml_mapping(path))
    if overrides:
        data.update({key: value for key, value in overrides.items() if value is not None})
    config = RunnerConfig(**{key: value for key, value in data.items() if key in RunnerConfig.__dataclass_fields__})
    config.validate()
    return config


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-not-found]

        loaded = yaml.safe_load(text) or {}
        if not isinstance(loaded, dict):
            raise ConfigError(f"{path}: expected a YAML mapping")
        return dict(loaded)
    except ModuleNotFoundError:
        return parse_simple_yaml(text, path)


def parse_simple_yaml(text: str, path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key:
            values = data.setdefault(current_key, [])
            if not isinstance(values, list):
                raise ConfigError(f"{path}: YAML list item follows scalar key: {current_key}")
            values.append(parse_scalar(line[4:].strip()))
            continue
        split = split_simple_yaml_mapping(line)
        if split is None:
            raise ConfigError(f"{path}: unsupported YAML line: {raw_line}")
        key, value = split
        current_key = key.strip()
        data[current_key] = [] if not value.strip() else parse_scalar(value.strip())
    return data


def split_simple_yaml_mapping(line: str) -> tuple[str, str] | None:
    """Split a simple YAML mapping line, allowing ':' inside label-like keys."""
    for index, char in enumerate(line):
        if char != ":":
            continue
        next_char = line[index + 1] if index + 1 < len(line) else ""
        if not next_char or next_char.isspace():
            return line[:index], line[index + 1 :]
    return None


def parse_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "None", "~"}:
        return None
    if value == "[]":
        return []
    try:
        return int(value)
    except ValueError:
        return shlex.split(value)[0] if value.startswith(('"', "'")) else value


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, default=Path(".local-codex-runner.yml"))
    parser.add_argument("--repo")
    parser.add_argument("--workdir")
    parser.add_argument("--issue-number", type=int)
    parser.add_argument("--dry-run", action="store_true", default=None)
    parser.add_argument("--no-dry-run", action="store_false", dest="dry_run")
    parser.add_argument("--max-local-fix-rounds", type=int)
    parser.add_argument("--max-ci-fix-rounds", type=int)
    parser.add_argument("--create-pr", action="store_true", default=None)
    parser.add_argument("--no-create-pr", action="store_false", dest="create_pr")
    parser.add_argument("--watch-ci", action="store_true", default=None)
    parser.add_argument("--no-watch-ci", action="store_false", dest="watch_ci")
    parser.add_argument("--allow-dirty", action="store_true", default=None)
    parser.add_argument("--include-label", action="append", default=[])
    parser.add_argument("--exclude-label", action="append", default=[])


def overrides_from_args(args: argparse.Namespace) -> dict[str, Any]:
    keys = (
        "repo",
        "workdir",
        "dry_run",
        "max_local_fix_rounds",
        "max_ci_fix_rounds",
        "create_pr",
        "watch_ci",
        "allow_dirty",
    )
    return {key: getattr(args, key) for key in keys if hasattr(args, key)}
