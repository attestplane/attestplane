#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Replay the marked quickstart blocks in docs/quickstart.md.

The runner executes only command blocks that are explicitly marked in the
markdown with ``<!-- quickstart-smoke:... -->`` comments. It uses local-only
fixtures:

- a temporary shim for ``uuid_utils.uuid7()``
- a temporary ``pip`` shim that accepts the documented install step without
  network access
- a temporary ``attestplane`` shim that dispatches to the in-repo CLI source

That keeps the smoke non-destructive and deterministic while still exercising
the quickstart flow end-to-end in a clean working directory.
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SDK_PYTHON_SRC = REPO_ROOT / "sdk" / "python" / "src"
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "quickstart.md"
MARKER_PREFIX = "quickstart-smoke:"


@dataclasses.dataclass(frozen=True, slots=True)
class QuickstartBlock:
    """A fenced executable markdown block."""

    label: str
    language: str
    code: str
    start_line: int
    end_line: int


class QuickstartFailure(Exception):
    """Raised when a quickstart block exits non-zero."""

    __slots__ = ("doc_path", "block", "command", "returncode", "stdout", "stderr")

    def __init__(
        self,
        *,
        doc_path: Path,
        block: QuickstartBlock,
        command: str,
        returncode: int,
        stdout: str,
        stderr: str,
    ) -> None:
        super().__init__()
        self.doc_path = doc_path
        self.block = block
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def __str__(self) -> str:
        location = f"{self.doc_path}:{self.block.start_line}"
        lines = [
            f"{location} quickstart block {self.block.label!r} failed with exit code {self.returncode}",
            f"command: {self.command}",
        ]
        if self.stdout.strip():
            lines.append("stdout:")
            lines.append(self.stdout.rstrip())
        if self.stderr.strip():
            lines.append("stderr:")
            lines.append(self.stderr.rstrip())
        return "\n".join(lines)


def parse_quickstart_blocks(doc_path: Path) -> list[QuickstartBlock]:
    """Extract marked fenced blocks from ``doc_path`` in source order."""
    text = doc_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    blocks: list[QuickstartBlock] = []
    pending_marker: tuple[str, int] | None = None
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("<!--") and stripped.endswith("-->"):
            marker = stripped[4:-3].strip()
            if marker.startswith(MARKER_PREFIX):
                pending_marker = (marker.removeprefix(MARKER_PREFIX).strip(), index + 1)
            index += 1
            continue

        if pending_marker is not None and stripped.startswith("```"):
            label, _marker_line = pending_marker
            language = stripped[3:].strip()
            if not language:
                raise ValueError(f"{doc_path}:{index + 1} executable block is missing a language tag")
            start_line = index + 1
            code_lines: list[str] = []
            end_index = index + 1
            while end_index < len(lines):
                candidate = lines[end_index]
                if candidate.strip() == "```":
                    blocks.append(
                        QuickstartBlock(
                            label=label,
                            language=language,
                            code="\n".join(code_lines),
                            start_line=start_line,
                            end_line=end_index + 1,
                        ),
                    )
                    pending_marker = None
                    break
                code_lines.append(candidate)
                end_index += 1
            else:
                raise ValueError(f"{doc_path}:{start_line} unterminated quickstart block")
            index = end_index + 1
            continue

        if pending_marker is not None and stripped:
            marker_label, marker_line = pending_marker
            raise ValueError(
                f"{doc_path}:{marker_line} marker {marker_label!r} must be followed by a fenced code block",
            )
        index += 1

    if pending_marker is not None:
        marker_label, marker_line = pending_marker
        raise ValueError(f"{doc_path}:{marker_line} marker {marker_label!r} was not followed by a code fence")

    return blocks


def _strip_shell_prompt(code: str) -> str:
    normalized: list[str] = []
    for line in code.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("$ "):
            normalized.append(stripped[2:])
        elif stripped.startswith("> "):
            normalized.append(stripped[2:])
        else:
            normalized.append(line)
    return "\n".join(normalized)


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _make_fixture_environment(workdir: Path) -> dict[str, str]:
    fixture_bin = workdir / "bin"
    fixture_bin.mkdir(parents=True, exist_ok=True)

    (workdir / "uuid_utils.py").write_text(
        """from __future__ import annotations\n\nfrom uuid import uuid4\n\n\ndef uuid7() -> object:\n    return uuid4()\n""",
        encoding="utf-8",
    )

    attestplane_script = fixture_bin / "attestplane"
    _write_executable(
        attestplane_script,
        f"""#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

os.execv(
    {sys.executable!r},
    [{sys.executable!r}, "-m", "attestplane.cli.main", *sys.argv[1:]],
)
""",
    )

    pip_script = fixture_bin / "pip"
    _write_executable(
        pip_script,
        f"""#!/usr/bin/env python3
from __future__ import annotations

import sys

def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] != "install":
        print("fixture pip only supports the documented quickstart install step", file=sys.stderr)
        return 2
    if not any(arg.startswith("attestplane") for arg in args[1:]):
        print("fixture pip expected an attestplane install target", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
""",
    )

    path_value = os.pathsep.join((str(fixture_bin), os.environ.get("PATH", "")))
    pythonpath_value = os.pathsep.join((str(workdir), str(SDK_PYTHON_SRC)))
    env = dict(os.environ)
    env.update(
        {
            "PATH": path_value,
            "PYTHONPATH": pythonpath_value,
            "PYTHON": sys.executable,
            "PYTHONNOUSERSITE": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        },
    )
    return env


def _run_command(
    command: str,
    *,
    workdir: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-euo", "pipefail", "-c", command],
        cwd=workdir,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _execute_block(
    block: QuickstartBlock,
    *,
    doc_path: Path,
    workdir: Path,
    env: dict[str, str],
) -> None:
    if block.language.lower() == "python":
        script_path = workdir / f"{block.label or 'quickstart'}.py"
        script_path.write_text(block.code + "\n", encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=workdir,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        command = f"{sys.executable} {script_path.name}"
    else:
        command = _strip_shell_prompt(block.code)
        completed = _run_command(command, workdir=workdir, env=env)

    if completed.returncode != 0:
        raise QuickstartFailure(
            doc_path=doc_path,
            block=block,
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


def run_quickstart(doc_path: Path) -> list[QuickstartBlock]:
    """Run the executable quickstart blocks in order and return them."""
    blocks = parse_quickstart_blocks(doc_path)
    if not blocks:
        raise ValueError(f"{doc_path} did not contain any marked quickstart smoke blocks")

    with tempfile.TemporaryDirectory(prefix="attestplane-quickstart-smoke-") as tmp:
        workdir = Path(tmp)
        env = _make_fixture_environment(workdir)
        for block in blocks:
            _execute_block(block, doc_path=doc_path, workdir=workdir, env=env)
    return blocks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the marked quickstart smoke blocks from docs/quickstart.md")
    parser.add_argument(
        "doc_path",
        nargs="?",
        type=Path,
        default=DEFAULT_DOC_PATH,
        help="markdown file containing the marked quickstart blocks",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        blocks = run_quickstart(args.doc_path)
    except QuickstartFailure as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - fail closed for malformed docs or runner setup errors
        print(f"{args.doc_path}: quickstart smoke runner failed: {exc}", file=sys.stderr)
        return 1

    line_summary = ", ".join(f"{block.start_line}-{block.end_line}" for block in blocks)
    print(f"PASS {args.doc_path} [{line_summary}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
