#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Codex CLI execution wrapper."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from scripts.local_codex_runner.github_cli import RunnerCommandError, redact, truncate


class CodexDriver:
    def __init__(
        self,
        *,
        command: str = "codex",
        command_template: str | None = None,
        model: str | None = None,
        sandbox: str = "workspace-write",
        dry_run: bool = True,
    ) -> None:
        self.command = command
        self.command_template = command_template
        self.model = model
        self.sandbox = sandbox
        self.dry_run = dry_run
        self.commands_run: list[str] = []

    def build_command(self, prompt_file: Path, workdir: Path) -> tuple[list[str], str | None]:
        if self.command_template:
            command = shlex.split(
                self.command_template.format(
                    command=self.command,
                    model=self.model or "",
                    workdir=str(workdir),
                    sandbox=self.sandbox,
                    prompt_file=str(prompt_file),
                )
            )
            return command, None
        command = [
            self.command,
            "exec",
            "--ignore-user-config",
            "--ephemeral",
            "--cd",
            str(workdir),
            "--sandbox",
            self.sandbox,
            "-",
        ]
        if self.model:
            command[2:2] = ["--model", self.model]
        return command, prompt_file.read_text(encoding="utf-8")

    def run_codex(self, prompt_file: Path, workdir: Path, log_path: Path, timeout: int | None = None) -> str:
        command, prompt_stdin = self.build_command(prompt_file, workdir)
        command_log = " ".join(command)
        if prompt_stdin is not None:
            command_log = f"{command_log} < {prompt_file}"
        self.commands_run.append(command_log)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if self.dry_run:
            text = f"[dry-run] would run: {command_log}\n"
            log_path.write_text(text, encoding="utf-8")
            return text
        completed = subprocess.run(
            command,
            cwd=workdir,
            capture_output=True,
            text=True,
            input=prompt_stdin,
            timeout=timeout,
            check=False,
        )
        output = redact((completed.stdout or "") + ("\nSTDERR:\n" + completed.stderr if completed.stderr else ""))
        log_path.write_text(truncate(output), encoding="utf-8")
        if completed.returncode != 0:
            raise RunnerCommandError(command, completed.returncode, output)
        return output
