#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Check that SECURITY.md and SECURITY_zh.md keep the same section shape.

The Chinese mirror is a translation, not a separate policy. The heading
structure therefore needs to stay aligned even though the prose differs.

Run locally with:

    python scripts/docs/security_parity.py SECURITY.md SECURITY_zh.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FILES = (REPO_ROOT / "SECURITY.md", REPO_ROOT / "SECURITY_zh.md")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
FENCE_RE = re.compile(r"^(```|~~~)")


def _extract_heading_levels(path: Path) -> list[int]:
    if not path.is_file():
        raise FileNotFoundError(f"missing security policy: {path}")
    levels: list[int] = []
    in_fence = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if match:
            levels.append(len(match.group(1)))
    return levels


def main(argv: list[str]) -> int:
    paths = [Path(arg) for arg in argv[1:]] or list(DEFAULT_FILES)
    if len(paths) != 2:
        print("usage: python scripts/docs/security_parity.py SECURITY.md SECURITY_zh.md")
        return 2

    resolved = []
    for path in paths:
        resolved.append(path if path.is_absolute() else REPO_ROOT / path)

    left_levels = _extract_heading_levels(resolved[0])
    right_levels = _extract_heading_levels(resolved[1])

    if left_levels != right_levels:
        print("security parity failed: heading structures differ")
        print(f"  {resolved[0].relative_to(REPO_ROOT)}: {left_levels}")
        print(f"  {resolved[1].relative_to(REPO_ROOT)}: {right_levels}")
        return 1

    print(
        "security parity OK: "
        f"{resolved[0].relative_to(REPO_ROOT)} and {resolved[1].relative_to(REPO_ROOT)} share the same heading structure"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
