#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Codex CLI execution wrapper."""

from __future__ import annotations

import shlex
import os
import signal
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
        try:
            completed = run_with_process_group_timeout(command, workdir, prompt_stdin, timeout)
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            output = redact(
                "\n".join(
                    part
                    for part in (
                        f"Codex command timed out after {timeout} seconds.",
                        stdout,
                        f"STDERR:\n{stderr}" if stderr else "",
                    )
                    if part
                )
            )
            log_path.write_text(truncate(output), encoding="utf-8")
            raise RunnerCommandError(command, 124, output) from exc
        output = redact((completed.stdout or "") + ("\nSTDERR:\n" + completed.stderr if completed.stderr else ""))
        log_path.write_text(truncate(output), encoding="utf-8")
        if completed.returncode != 0:
            raise RunnerCommandError(command, completed.returncode, output)
        return output


def run_with_process_group_timeout(
    command: list[str],
    workdir: Path,
    prompt_stdin: str | None,
    timeout: int | None,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(  # noqa: S603 - command argv is assembled by CodexDriver.
        command,
        cwd=workdir,
        stdin=subprocess.PIPE if prompt_stdin is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(input=prompt_stdin, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        terminate_process_group(process)
        try:
            stdout, stderr = process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            kill_process_group(process)
            stdout, stderr = process.communicate()
        exc.stdout = stdout
        exc.stderr = stderr
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def terminate_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return


def kill_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
