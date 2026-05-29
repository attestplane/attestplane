# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Public API manifest drift-gate tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKER = REPO_ROOT / "scripts/api/check_public_api_manifest.py"
PY_EXTRACTOR = REPO_ROOT / "scripts/api/extract_python_public_api.py"
TS_EXTRACTOR = REPO_ROOT / "scripts/api/extract_typescript_public_api.py"
PUBLIC_API_GATE = REPO_ROOT / "scripts/check-public-api.sh"
PY_BASELINE = REPO_ROOT / "api/public/python_v1.json"
TS_BASELINE = REPO_ROOT / "api/public/typescript_v1.json"
ALLOWLIST = REPO_ROOT / "api/public/py_ts_allowlist_v1.json"


def run_command(args: list[str], *, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def checker_args(tmp_path: Path) -> list[str]:
    return [
        sys.executable,
        str(CHECKER),
        "--python-current",
        str(tmp_path / "python_current.json"),
        "--typescript-current",
        str(tmp_path / "typescript_current.json"),
        "--python-baseline",
        str(tmp_path / "python_baseline.json"),
        "--typescript-baseline",
        str(tmp_path / "typescript_baseline.json"),
        "--allowlist",
        str(tmp_path / "allowlist.json"),
    ]


def copy_gate_inputs(tmp_path: Path) -> None:
    shutil.copyfile(PY_BASELINE, tmp_path / "python_current.json")
    shutil.copyfile(TS_BASELINE, tmp_path / "typescript_current.json")
    shutil.copyfile(PY_BASELINE, tmp_path / "python_baseline.json")
    shutil.copyfile(TS_BASELINE, tmp_path / "typescript_baseline.json")
    shutil.copyfile(ALLOWLIST, tmp_path / "allowlist.json")


def test_public_api_manifest_gate_passes() -> None:
    result = run_command([str(PUBLIC_API_GATE)])
    assert result.returncode == 0, result.stderr + result.stdout
    assert "Public API manifest check PASS" in result.stdout


def test_extractors_are_deterministic(tmp_path: Path) -> None:
    py_a = tmp_path / "py_a.json"
    py_b = tmp_path / "py_b.json"
    ts_a = tmp_path / "ts_a.json"
    ts_b = tmp_path / "ts_b.json"
    for args in [
        [sys.executable, str(PY_EXTRACTOR), "--out", str(py_a)],
        [sys.executable, str(PY_EXTRACTOR), "--out", str(py_b)],
        [sys.executable, str(TS_EXTRACTOR), "--out", str(ts_a)],
        [sys.executable, str(TS_EXTRACTOR), "--out", str(ts_b)],
    ]:
        result = run_command(args)
        assert result.returncode == 0, result.stderr + result.stdout
    assert py_a.read_bytes() == py_b.read_bytes()
    assert ts_a.read_bytes() == ts_b.read_bytes()


def test_checker_fails_unrecorded_python_symbol(tmp_path: Path) -> None:
    copy_gate_inputs(tmp_path)
    current = load_json(tmp_path / "python_current.json")
    current["symbols"].append(
        {  # type: ignore[index, union-attr]
            "documented": False,
            "kind": "function",
            "module": "attestplane",
            "name": "new_unrecorded_symbol",
            "notes": "",
            "stability": "alpha_public",
        }
    )
    write_json(tmp_path / "python_current.json", current)
    result = run_command(checker_args(tmp_path))
    assert result.returncode != 0
    assert "unrecorded symbols" in result.stderr


def test_checker_fails_documented_missing_symbol(tmp_path: Path) -> None:
    copy_gate_inputs(tmp_path)
    current = load_json(tmp_path / "python_current.json")
    current["symbols"] = [  # type: ignore[index]
        item
        for item in current["symbols"]  # type: ignore[index, union-attr]
        if item["name"] != "AttestSubstrate"
    ]
    write_json(tmp_path / "python_current.json", current)
    result = run_command(checker_args(tmp_path))
    assert result.returncode != 0
    assert "documented symbols missing" in result.stderr


def test_checker_fails_allowlist_without_reason_or_review_by(tmp_path: Path) -> None:
    copy_gate_inputs(tmp_path)
    allowlist = load_json(tmp_path / "allowlist.json")
    first = allowlist["allowed_asymmetries"][0]  # type: ignore[index]
    first["reason"] = ""  # type: ignore[index]
    first["review_by"] = ""  # type: ignore[index]
    write_json(tmp_path / "allowlist.json", allowlist)
    result = run_command(checker_args(tmp_path))
    assert result.returncode != 0
    assert "missing reason" in result.stderr
    assert "missing review_by" in result.stderr
