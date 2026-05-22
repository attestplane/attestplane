# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def test_v1_7_0_conformance_fixture_hash_lock_still_matches() -> None:
    result = subprocess.run(
        ["./scripts/check-fixture-hashes.sh"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_existing_verifier_conformance_vectors_still_pass() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "sdk/python/tests/conformance/test_verifier_conformance.py",
            "-q",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
