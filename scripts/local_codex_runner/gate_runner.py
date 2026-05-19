#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Local gate execution for issue-driven repairs."""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from scripts.local_codex_runner.config import load_yaml_mapping
from scripts.local_codex_runner.github_cli import redact, truncate


FORBIDDEN_COMMAND_WORDS = ("publish", "twine upload", "npm publish", "git tag", "gh release upload")
LIVE_COMMAND_WORDS = ("--live", "live-test", "external-live")


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
        lines = [f"{self.status}: gate={self.selected_gate}"]
        for result in self.commands:
            lines.append(f"- {result.command}: exit={result.exit_code}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, object]:
        return {
            "commands": [asdict(command) for command in self.commands],
            "selected_gate": self.selected_gate,
            "status": self.status,
        }


class GateRunner:
    def __init__(self, workdir: Path, matrix_path: Path, *, timeout_seconds: int = 900) -> None:
        self.workdir = workdir
        self.matrix_path = matrix_path
        self.timeout_seconds = timeout_seconds

    def load_matrix(self) -> dict[str, list[str]]:
        if not self.matrix_path.exists():
            return {"default": ["python -m compileall scripts", "pytest -q"]}
        loaded = load_yaml_mapping(self.matrix_path)
        return {str(key): [str(item) for item in value] for key, value in loaded.items() if isinstance(value, list)}

    def select_gate(self, labels: list[str]) -> tuple[str, list[str]]:
        matrix = self.load_matrix()
        for label in labels:
            if label in matrix:
                return label, matrix[label]
        return "default", matrix.get("default", ["python -m compileall scripts", "pytest -q"])

    def run(self, labels: list[str], evidence_dir: Path) -> GateReport:
        gate_name, commands = self.select_gate(labels)
        live_allowed = "live-test-approved" in labels
        results = [self.run_command(self.rewrite_for_uv(command), live_allowed=live_allowed) for command in commands]
        status = "PASS" if all(result.exit_code == 0 for result in results) else "FAIL"
        report = GateReport(status=status, selected_gate=gate_name, commands=results)
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "gate_report.json").write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (evidence_dir / "gate_report.md").write_text(report.summary() + "\n", encoding="utf-8")
        return report

    def run_command(self, command: str, *, live_allowed: bool) -> GateCommandResult:
        lowered = command.lower()
        if any(word in lowered for word in FORBIDDEN_COMMAND_WORDS):
            return GateCommandResult(command, 2, "", "Forbidden publish/tag/release command blocked by gate runner")
        if not live_allowed and any(word in lowered for word in LIVE_COMMAND_WORDS):
            return GateCommandResult(command, 2, "", "Live external test command blocked without live-test-approved label")
        argv = shlex.split(command)
        if not argv:
            return GateCommandResult(command, 2, "", "Empty gate command blocked")
        completed = subprocess.run(
            argv,
            cwd=self.workdir,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        return GateCommandResult(
            command=command,
            exit_code=completed.returncode,
            stdout=truncate(redact(completed.stdout)),
            stderr=truncate(redact(completed.stderr)),
        )

    def rewrite_for_uv(self, command: str) -> str:
        has_uv_project = (self.workdir / "pyproject.toml").exists() or (self.workdir / "uv.lock").exists()
        if has_uv_project and shutil.which("uv") and command.startswith("pytest "):
            return "uv run " + command
        return command
