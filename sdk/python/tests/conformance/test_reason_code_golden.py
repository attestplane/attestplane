# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Golden lock test preventing silent reason-code taxonomy drift.

Stability contract
------------------
Within a given ``reason_code_version`` / ``verify_reason_taxonomy_version``
the code set is **frozen**. Adding, removing, or renaming a code always
requires bumping the version — existing codes are append-only across
versions.

Drift detection
---------------
*test_reason_code_golden_lock* loads the golden snapshot from
:file:`reason_code_golden.json` and compares it against live module
state. Any add/remove/rename of a code **without** a corresponding
version bump fails the test.

Regeneration
------------
After a deliberate, version-bumped taxonomy change the snapshot must
be regenerated::

    REASON_CODE_GOLDEN_UPDATE=1 python3.11 -m pytest \\
        sdk/python/tests/conformance/test_reason_code_golden.py -x -q

The regenerated :file:`reason_code_golden.json` must be committed
alongside the version bump. An uncommitted golden snapshot = CI red.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from attestplane.reason_codes import ALL_REASON_CODES_V1, REASON_CODE_SCHEMA_VERSION
from attestplane.verify_reason_codes import (
    ALL_VERIFY_REASON_CODES_V1,
    VERIFY_REASON_TAXONOMY_VERSION,
)

_GOLDEN_PATH = Path(__file__).resolve().parent / "reason_code_golden.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _live_state() -> dict[str, Any]:
    """Return the current reason-code taxonomy derived from live modules."""
    return {
        "reason_codes_v1": {
            "version": REASON_CODE_SCHEMA_VERSION,
            "codes": sorted(ALL_REASON_CODES_V1),
            "count": len(ALL_REASON_CODES_V1),
        },
        "verify_reason_codes_v1": {
            "version": VERIFY_REASON_TAXONOMY_VERSION,
            "codes": sorted(ALL_VERIFY_REASON_CODES_V1),
            "count": len(ALL_VERIFY_REASON_CODES_V1),
        },
    }


def _golden_state() -> dict[str, Any]:
    """Load the frozen golden snapshot (metadata stripped)."""
    raw = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    return {
        "reason_codes_v1": raw["reason_codes_v1"],
        "verify_reason_codes_v1": raw["verify_reason_codes_v1"],
    }


def _rewrite_golden(payload: dict[str, Any]) -> None:
    """Overwrite the golden snapshot with live module state.

    Preserves ``$schema_version``, ``$comment``, and ``frozen_at`` fields
    from the current file; replaces taxonomy payloads.
    """
    current = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    current["reason_codes_v1"] = payload["reason_codes_v1"]
    current["verify_reason_codes_v1"] = payload["verify_reason_codes_v1"]
    current["frozen_at"] = "2026-05-30T00:00:00Z"  # keep stable for this session
    _GOLDEN_PATH.write_text(
        json.dumps(current, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _diff_section(label: str, golden: dict[str, Any], live: dict[str, Any]) -> str:
    """Return a human-readable diff block for one taxonomy section."""
    lines: list[str] = []
    g_ver = golden["version"]
    l_ver = live["version"]
    g_codes = set(golden["codes"])
    l_codes = set(live["codes"])

    if g_ver != l_ver:
        lines.append(f"  version: {g_ver} -> {l_ver}")

    added = sorted(l_codes - g_codes)
    removed = sorted(g_codes - l_codes)
    if added:
        lines.append(f"  codes added (+{len(added)}): {', '.join(added)}")
    if removed:
        lines.append(f"  codes removed (-{len(removed)}): {', '.join(removed)}")

    # Detect renames within the same version: same count, different names.
    if g_ver == l_ver and g_codes != l_codes and len(g_codes) == len(l_codes):
        lines.append("  ** rename detected (count unchanged) **")
        lines.append(f"    golden: {', '.join(sorted(g_codes))}")
        lines.append(f"    live:   {', '.join(sorted(l_codes))}")

    counts_match = golden["count"] == live["count"]
    if not counts_match:
        lines.append(f"  count: {golden['count']} -> {live['count']}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_reason_code_golden_lock() -> None:
    """Golden lock: reason-code taxonomy must match frozen snapshot.

    On failure, this test prints a detailed diff showing what changed,
    and instructs the developer on how to regenerate the snapshot after
    a deliberate, version-bumped taxonomy update.

    You can also run with ``REASON_CODE_GOLDEN_UPDATE=1`` to automatically
    regenerate the snapshot from live module state (use only when you
    have intentionally bumped the taxonomy version).
    """
    live = _live_state()
    golden = _golden_state()

    # --- Regeneration gate ---
    if os.environ.get("REASON_CODE_GOLDEN_UPDATE") == "1":
        _rewrite_golden(live)
        # Reload so the assertion below passes.
        golden = live

    # --- Compare ---
    errors: list[str] = []

    for section in ("reason_codes_v1", "verify_reason_codes_v1"):
        live_sec = live[section]
        golden_sec = golden[section]

        if live_sec["version"] != golden_sec["version"]:
            # Version changed => golden snapshot is stale (expected during
            # a deliberate taxonomy update). Still fail — the developer must
            # run with REASON_CODE_GOLDEN_UPDATE=1, which updates the snapshot
            # and then this assertion passes.
            errors.append(
                f"  [{section}] version drift: golden={golden_sec['version']} "
                f"live={live_sec['version']}. "
                f"Regenerate with REASON_CODE_GOLDEN_UPDATE=1 after bumping the version."
            )
        elif live_sec["codes"] != golden_sec["codes"]:
            # Same version but codes changed => silent taxonomy drift.
            diff = _diff_section(section, golden_sec, live_sec)
            errors.append(f"  [{section}] silent drift within version {live_sec['version']}:\n{diff}")
        elif live_sec["count"] != golden_sec["count"]:
            errors.append(f"  [{section}] count mismatch: golden={golden_sec['count']} live={live_sec['count']}")

    if errors:
        msg_parts = [
            "Reason-code taxonomy drift detected.",
            "",
            "Stability contract: within a given version the code set is frozen.",
            "Any add/remove/rename requires bumping the version.",
            "",
            "Details:",
        ]
        msg_parts.extend(errors)
        msg_parts.extend(
            [
                "",
                "To regenerate the golden snapshot after a deliberate version bump:",
                "  REASON_CODE_GOLDEN_UPDATE=1 python3.11 -m pytest \\",
                "      sdk/python/tests/conformance/test_reason_code_golden.py -x -q",
                "",
                "Then commit the updated reason_code_golden.json alongside the version bump.",
            ]
        )
        msg = "\n".join(msg_parts)
        raise AssertionError(msg)


def test_reason_code_golden_snapshot_exists() -> None:
    """The golden snapshot file must exist and be parseable."""
    assert _GOLDEN_PATH.is_file(), f"Golden snapshot not found: {_GOLDEN_PATH}"
    raw = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    assert raw.get("$schema_version") == 1
    assert "reason_codes_v1" in raw
    assert "verify_reason_codes_v1" in raw
    assert "frozen_at" in raw
    # Validate code patterns briefly
    for code in raw["reason_codes_v1"]["codes"]:
        assert isinstance(code, str) and len(code) >= 2
    for code in raw["verify_reason_codes_v1"]["codes"]:
        assert isinstance(code, str) and code.startswith("att.verify.")
