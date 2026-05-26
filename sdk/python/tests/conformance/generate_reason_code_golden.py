#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Explicit regeneration helper for the frozen reason-code golden snapshot.

The snapshot is intentionally checked in and only changes when this helper is
run with ``--update``. Normal runs compare the generated payload to the file
and fail if the taxonomy drifted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from attestplane.reason_codes import ALL_REASON_CODES_V1, REASON_CODE_SCHEMA_VERSION

SNAPSHOT_PATH = Path(__file__).with_name("reason_code_golden.json")


def build_snapshot() -> dict[str, object]:
    """Return the canonical golden payload for the reason-code taxonomy."""
    return {
        "$schema_version": 1,
        "reason_code_version": REASON_CODE_SCHEMA_VERSION,
        "reason_codes": sorted(ALL_REASON_CODES_V1),
    }


def render_snapshot() -> str:
    return json.dumps(build_snapshot(), indent=2, sort_keys=True) + "\n"


def verify_snapshot() -> int:
    expected = render_snapshot()
    actual = SNAPSHOT_PATH.read_text(encoding="utf-8")
    if actual == expected:
        print(
            "reason_code_golden.json is current: "
            f"{len(ALL_REASON_CODES_V1)} codes at version "
            f"{REASON_CODE_SCHEMA_VERSION}"
        )
        return 0

    print("::error::reason_code_golden.json drift detected.", flush=True)
    print("Expected canonical payload:", flush=True)
    print(expected, end="" if expected.endswith("\n") else "\n")
    print("Actual file contents:", flush=True)
    print(actual, end="" if actual.endswith("\n") else "\n")
    print(
        "If this change is intentional, run this helper with --update and "
        "commit the regenerated snapshot together with the version bump.",
        flush=True,
    )
    return 1


def update_snapshot() -> int:
    SNAPSHOT_PATH.write_text(render_snapshot(), encoding="utf-8")
    print(
        "Updated reason_code_golden.json: "
        f"{len(ALL_REASON_CODES_V1)} codes at version "
        f"{REASON_CODE_SCHEMA_VERSION}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check or regenerate the frozen reason-code golden snapshot."
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="rewrite reason_code_golden.json from the current source-of-truth values",
    )
    args = parser.parse_args()
    return update_snapshot() if args.update else verify_snapshot()


if __name__ == "__main__":
    raise SystemExit(main())
