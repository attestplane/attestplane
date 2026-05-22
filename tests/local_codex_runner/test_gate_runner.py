import subprocess
from pathlib import Path

from scripts.local_codex_runner.gate_runner import GateRunner


def test_label_to_gate_mapping(tmp_path: Path) -> None:
    matrix = tmp_path / "gates.yml"
    matrix.write_text('default:\n  - "pytest -q"\nclaim-safety:\n  - "pytest tests/sentinel -q"\n', encoding="utf-8")

    gate, commands = GateRunner(tmp_path, matrix).select_gate(["claim-safety"])

    assert gate == "claim-safety"
    assert commands == ["pytest tests/sentinel -q"]


def test_label_mapping_allows_colon_in_key(tmp_path: Path) -> None:
    matrix = tmp_path / "gates.yml"
    matrix.write_text(
        'default:\n  - "pytest -q"\narea:verifier:\n  - "pytest tests/verifier -q"\n',
        encoding="utf-8",
    )

    gate, commands = GateRunner(tmp_path, matrix).select_gate(["area:verifier"])

    assert gate == "area:verifier"
    assert commands == ["pytest tests/verifier -q"]


def test_command_failure_is_captured(monkeypatch, tmp_path: Path) -> None:
    def fake_run(*args, **kwargs):
        assert args[0] == ["pytest", "-q"]
        assert "shell" not in kwargs
        return subprocess.CompletedProcess(args[0], 2, "out", "err token=abc")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = GateRunner(tmp_path, tmp_path / "missing.yml").run_command("pytest -q", live_allowed=False)

    assert result.exit_code == 2
    assert "[REDACTED]" in result.stderr


def test_gate_command_uses_argv_list(monkeypatch, tmp_path: Path) -> None:
    observed = {}

    def fake_run(*args, **kwargs):
        observed["argv"] = args[0]
        observed["shell"] = kwargs.get("shell")
        return subprocess.CompletedProcess(args[0], 0, "ok", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = GateRunner(tmp_path, tmp_path / "missing.yml").run_command("python -m compileall scripts", live_allowed=False)

    assert result.exit_code == 0
    assert observed["argv"] == ["python", "-m", "compileall", "scripts"]
    assert observed["shell"] is None


def test_no_live_tests_by_default(tmp_path: Path) -> None:
    result = GateRunner(tmp_path, tmp_path / "missing.yml").run_command("pytest --live", live_allowed=False)

    assert result.exit_code == 2
    assert "blocked" in result.stderr
