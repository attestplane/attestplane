#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Deterministic JSON state storage for the local Codex runner."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.local_codex_runner.models import State


def load_state(path: Path) -> State:
    if not path.exists():
        return State()
    return State.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_state(path: Path, state: State) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
