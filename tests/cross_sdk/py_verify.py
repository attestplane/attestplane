# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Cross-SDK round-trip: Python final verifier (step 3 of 3).

Confirms ``py_emit.json`` and ``ts_reemit.json`` agree on every test case
(canonical bytes + SHA-256 hash). This is the closing edge of the Py → TS →
Py loop the architect required: any divergence between the two SDKs surfaces
here as a non-zero exit and a structured diff suitable for CI log triage.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def index_by_id(entries: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {e["id"]: e for e in entries}


def diff_section(
    name: str, py_entries: list[dict[str, str]], ts_entries: list[dict[str, str]]
) -> list[str]:
    py_idx = index_by_id(py_entries)
    ts_idx = index_by_id(ts_entries)
    failures: list[str] = []

    missing_in_ts = sorted(set(py_idx) - set(ts_idx))
    missing_in_py = sorted(set(ts_idx) - set(py_idx))
    for mid in missing_in_ts:
        failures.append(f"[{name}] case {mid!r} missing on TS side")
    for mid in missing_in_py:
        failures.append(f"[{name}] case {mid!r} missing on Py side")

    for cid in sorted(set(py_idx) & set(ts_idx)):
        py = py_idx[cid]
        ts = ts_idx[cid]
        if (
            py["canonical_b64"] != ts["canonical_b64"]
            or py["hash_hex"] != ts["hash_hex"]
        ):
            failures.append(
                f"[{name}] {cid}: py_hash={py['hash_hex']} ts_hash={ts['hash_hex']} "
                f"py_b64={py['canonical_b64']} ts_b64={ts['canonical_b64']}"
            )
    return failures


def main() -> int:
    here = Path(__file__).parent
    py_emit = json.loads((here / "py_emit.json").read_text(encoding="utf-8"))
    ts_reemit = json.loads((here / "ts_reemit.json").read_text(encoding="utf-8"))

    failures: list[str] = []
    failures += diff_section(
        "canonical_text", py_emit["canonical_text"], ts_reemit["canonical_text"]
    )
    failures += diff_section(
        "canonical_json", py_emit["canonical_json"], ts_reemit["canonical_json"]
    )

    if failures:
        print("::error::Cross-SDK round-trip mismatch:", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1

    total = len(py_emit["canonical_text"]) + len(py_emit["canonical_json"])
    print(f"Cross-SDK round-trip: {total} cases, Py↔TS byte-identical ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
