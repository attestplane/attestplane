#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Local gate execution for issue-driven repairs."""

from __future__ import annotations

import json
import os
import resource
import shlex
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from scripts.local_codex_runner.config import load_yaml_mapping
from scripts.local_codex_runner.github_cli import redact, truncate

FORBIDDEN_COMMAND_WORDS = (
    "publish",
    "twine upload",
    "npm publish",
    "git tag",
    "gh release upload",
)
LIVE_COMMAND_WORDS = ("--live", "live-test", "external-live")
DOCS_ONLY_GATE = "type:docs"
CI_FAILED_GATE = "ci:failed"
MIN_GATE_OPEN_FILES = 4096


@dataclass(frozen=True)
class GateCommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class GateReport:
    status: str
    selected_gate: str
    commands: list[GateCommandResult]

    def summary(self) -> str:
        lines = [
            f"# Gate Report: {self.status}",
            "",
            f"Gate: `{self.selected_gate}`",
            "",
            "## Commands",
            "",
        ]
        for result in self.commands:
            lines.append(f"- `{result.command}`: exit={result.exit_code}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, object]:
        return {
            "commands": [asdict(command) for command in self.commands],
            "selected_gate": self.selected_gate,
            "status": self.status,
        }


class GateRunner:
    def __init__(
        self, workdir: Path, matrix_path: Path, *, timeout_seconds: int = 900
    ) -> None:
        self.workdir = workdir
        self.matrix_path = matrix_path
        self.timeout_seconds = timeout_seconds

    def load_matrix(self) -> dict[str, list[str]]:
        if not self.matrix_path.exists():
            return {"default": ["python -m compileall scripts", "pytest -q"]}
        loaded = load_yaml_mapping(self.matrix_path)
        return {
            str(key): [str(item) for item in value]
            for key, value in loaded.items()
            if isinstance(value, list)
        }

    def select_gate(
        self,
        labels: list[str],
        *,
        changed_files: list[str] | None = None,
        preferred_gate: str | None = None,
    ) -> tuple[str, list[str]]:
        matrix = self.load_matrix()
        if preferred_gate and preferred_gate in matrix:
            return preferred_gate, matrix[preferred_gate]
        for label in labels:
            if label in matrix:
                if (
                    label == DOCS_ONLY_GATE
                    and changed_files
                    and not all(is_docs_only_path(path) for path in changed_files)
                ):
                    break
                return label, matrix[label]
        return "default", matrix.get(
            "default", ["python -m compileall scripts", "pytest -q"]
        )

    def run(
        self,
        labels: list[str],
        evidence_dir: Path,
        *,
        preferred_gate: str | None = None,
    ) -> GateReport:
        gate_name, commands = self.select_gate(
            labels,
            changed_files=self.changed_files(),
            preferred_gate=preferred_gate,
        )
        live_allowed = "live-test-approved" in labels
        results = [
            self.run_command(
                self.rewrite_for_project_python(command), live_allowed=live_allowed
            )
            for command in commands
        ]
        status = "PASS" if all(result.exit_code == 0 for result in results) else "FAIL"
        report = GateReport(status=status, selected_gate=gate_name, commands=results)
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "gate_report.json").write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (evidence_dir / "gate_report.md").write_text(
            report.summary() + "\n", encoding="utf-8"
        )
        return report

    def run_command(self, command: str, *, live_allowed: bool) -> GateCommandResult:
        lowered = command.lower()
        if any(word in lowered for word in FORBIDDEN_COMMAND_WORDS):
            return GateCommandResult(
                command,
                2,
                "",
                "Forbidden publish/tag/release command blocked by gate runner",
            )
        if not live_allowed and any(word in lowered for word in LIVE_COMMAND_WORDS):
            return GateCommandResult(
                command,
                2,
                "",
                "Live external test command blocked without live-test-approved label",
            )
        argv = shlex.split(command)
        if not argv:
            return GateCommandResult(command, 2, "", "Empty gate command blocked")
        completed = subprocess.run(  # noqa: S603 - configured gate commands are executed as argv, never shell.
            argv,
            cwd=self.workdir,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
            preexec_fn=raise_open_file_limit if os.name == "posix" else None,
        )
        return GateCommandResult(
            command=command,
            exit_code=completed.returncode,
            stdout=truncate(redact(completed.stdout)),
            stderr=truncate(redact(completed.stderr)),
        )

    def rewrite_for_project_python(self, command: str) -> str:
        python = self.workdir / "sdk/python/.venv/bin/python"
        pytest = self.workdir / "sdk/python/.venv/bin/pytest"
        if not python.exists() or not pytest.exists():
            return command

        argv = shlex.split(command)
        if not argv:
            return command
        if argv[0] == "python":
            argv[0] = str(python)
        elif argv[0] == "pytest":
            argv[0] = str(pytest)
        elif argv[0] == "env":
            for index, token in enumerate(argv[1:], start=1):
                if "=" in token:
                    continue
                if token == "python":
                    argv[index] = str(python)
                elif token == "pytest":
                    argv[index] = str(pytest)
                break
        return shlex.join(argv)

    def changed_files(self) -> list[str]:
        completed = subprocess.run(  # noqa: S603 - Git status argv is fixed by the runner.
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=self.workdir,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return []
        files: list[str] = []
        for line in completed.stdout.splitlines():
            if not line:
                continue
            path = line[3:].strip()
            if " -> " in path:
                path = path.rsplit(" -> ", 1)[1]
            files.append(path)
        return files


def is_docs_only_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return (
        normalized.startswith("docs/")
        or normalized.endswith(".md")
        or normalized in {"README.md", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE"}
    )


def raise_open_file_limit() -> None:
    """Raise the gate subprocess fd soft limit when launchd/tmux starts low."""
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    except (OSError, ValueError):
        return
    if soft >= MIN_GATE_OPEN_FILES:
        return
    target = min(max(MIN_GATE_OPEN_FILES, soft), hard)
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))
    except (OSError, ValueError):
        return
