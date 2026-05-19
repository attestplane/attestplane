import subprocess
from pathlib import Path

import pytest

from scripts.local_codex_runner.codex_driver import CodexDriver
from scripts.local_codex_runner.github_cli import RunnerCommandError


def test_codex_command_construction(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"

    command = CodexDriver(command="codex", sandbox="workspace-write").build_command(prompt, tmp_path)

    assert command == ["codex", "exec", "--cd", str(tmp_path), "--sandbox", "workspace-write", "--prompt-file", str(prompt)]


def test_codex_dry_run_does_not_execute(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(subprocess, "run", fake_run)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("x", encoding="utf-8")

    CodexDriver(dry_run=True).run_codex(prompt, tmp_path, tmp_path / "codex.log")

    assert called is False
    assert "dry-run" in (tmp_path / "codex.log").read_text(encoding="utf-8")


def test_codex_failure_redacts_stderr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, "", "GITHUB_TOKEN=github_pat_abc123")

    monkeypatch.setattr(subprocess, "run", fake_run)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("x", encoding="utf-8")

    with pytest.raises(RunnerCommandError) as excinfo:
        CodexDriver(dry_run=False).run_codex(prompt, tmp_path, tmp_path / "codex.log")

    assert "github_pat" not in str(excinfo.value)

