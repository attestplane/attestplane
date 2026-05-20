# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Package import-surface smoke tests for alpha release hardening."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import attestplane

REPO_ROOT = Path(__file__).resolve().parents[3]
PY_SRC = REPO_ROOT / "sdk" / "python" / "src"


def test_import_attestplane_smoke() -> None:
    assert attestplane.__version__ == "0.6.3a0"
    assert attestplane.canonicalize({"a": 1}) == b'{"a":1}'


def test_public_all_symbols_are_defined() -> None:
    missing = [name for name in attestplane.__all__ if not hasattr(attestplane, name)]
    assert not missing


def test_core_readme_import_symbols_smoke() -> None:
    from attestplane import AttestSubstrate, EventDraft, SubjectRef

    sub = AttestSubstrate()
    sub.append(
        EventDraft(
            event_type="ai_decision",
            actor="agent://smoke/v1",
            payload={"outcome": "approved", "confidence_bp": 9120},
            subject_ref=SubjectRef(scheme="sha256_salted", value="2c1b"),
        )
    )
    assert sub.verify().ok is True


def test_adapter_public_symbols_exported_from_root() -> None:
    from attestplane import LangFuseAdapter, LangSmithAdapter, RuntimeEvent

    assert LangFuseAdapter.__name__ == "LangFuseAdapter"
    assert LangSmithAdapter.__name__ == "LangSmithAdapter"
    assert RuntimeEvent.__name__ == "RuntimeEvent"


def test_optional_dependency_absence_keeps_core_import_surface_defined() -> None:
    script = """
import builtins

orig_import = builtins.__import__
blocked = ("cryptography", "asn1crypto", "yaml")

def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == blocked or name.startswith(blocked):
        raise ImportError(f"blocked optional dependency: {name}")
    return orig_import(name, globals, locals, fromlist, level)

builtins.__import__ = guarded_import

import attestplane
import attestplane.anchoring as anchoring

missing_root = [name for name in attestplane.__all__ if not hasattr(attestplane, name)]
missing_anchor = [name for name in anchoring.__all__ if not hasattr(anchoring, name)]
assert not missing_root, missing_root
assert not missing_anchor, missing_anchor
assert hasattr(attestplane, "AttestSubstrate")
assert not hasattr(attestplane, "InMemoryKeyProvider")
assert not hasattr(anchoring, "FreeTSAProvider")
"""
    env = {
        **os.environ,
        "PYTHONPATH": str(PY_SRC),
    }
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
