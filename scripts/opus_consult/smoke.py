# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Dry-run smoke test for the Opus planning hotline telemetry.

Usage::

    python -m scripts.opus_consult.smoke --milestone v1.6.0 --dry-run

The script runs a synthetic consultation for the given milestone and prints
the emitted ``autodev.plan.consult`` event to stdout so operators can verify
the telemetry pipeline end-to-end without contacting a real Opus backend.

Safety
------
- ``--dry-run`` is required.  The script never calls an external Opus command,
  never creates issues, never moves tags, and never publishes packages.
- Prompt bodies are never logged — only a redacted hash is emitted.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

if str(Path(__file__).resolve().parents[2]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.opus_consult.telemetry import compute_prompt_hash, emit_plan_consult_event


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--milestone", required=True, help="Milestone tag to test, e.g. v1.6.0"
    )
    parser.add_argument(
        "--dry-run", action="store_true", required=True, help="Required safety flag"
    )
    parser.add_argument(
        "--plan-level", default="daily", choices=("daily", "medium", "architecture")
    )
    parser.add_argument("--anchor", default="v1.5.9")
    parser.add_argument("--head-sha", default="0" * 40)
    args = parser.parse_args(argv)

    if not args.dry_run:
        print("--dry-run is required for safety. Aborting.", file=sys.stderr)
        return 1

    # Simulate a consultation: build a synthetic prompt, hash it, emit event.
    synthetic_prompt = (
        f"Attestplane stable autodev {args.plan_level} development planning "
        f"for {args.milestone}."
    )
    prompt_hash = compute_prompt_hash(synthetic_prompt)

    # Simulate wall-clock duration.
    start = time.monotonic()
    time.sleep(0.05)  # 50 ms synthetic consultation
    duration_ms = int((time.monotonic() - start) * 1000)

    emit_plan_consult_event(
        milestone=args.milestone,
        plan_level=args.plan_level,
        anchor=args.anchor,
        head_sha=args.head_sha,
        duration_ms=duration_ms,
        exit_code=0,
        fallback_used=False,
        prompt_hash=prompt_hash,
        plan_source="opus-live",
    )

    print(
        f"smoke OK — emitted autodev.plan.consult for {args.milestone} "
        f"({args.plan_level})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
