# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""CI smoke test: exercise the 5-minute quickstart (docs/quickstart.md).

Ensures packaging/dependency changes cannot silently break first-run usage.
Non-destructive: writes the chain to a pytest-managed tmpdir, never to the
repo or cwd. Deterministic, no network, no external services.
"""

from __future__ import annotations

from pathlib import Path

from attestplane import (
    LEASE_LIFECYCLE_EVENT,
    POLICY_CHECK_EVENT,
    STATE_TRANSITION_EVENT,
    AttestSubstrate,
    EventDraft,
    JsonlStorageBackend,
)


def test_quickstart_smoke(tmp_path: Path) -> None:
    """Replicate the 5-minute quickstart snippet and verify the chain."""
    jsonl_path = tmp_path / "chain.jsonl"

    sub = AttestSubstrate()
    storage = JsonlStorageBackend(jsonl_path)

    drafts = [
        EventDraft(
            event_type=LEASE_LIFECYCLE_EVENT,
            actor="agent://demo/v1",
            payload={"lease_id": "lease-demo-0001", "phase": "acquired"},
        ),
        EventDraft(
            event_type=POLICY_CHECK_EVENT,
            actor="agent://demo/v1",
            payload={"policy_id": "demo.allow_read", "decision": "allow"},
        ),
        EventDraft(
            event_type=STATE_TRANSITION_EVENT,
            actor="agent://demo/v1",
            payload={"from": "idle", "to": "working"},
        ),
    ]

    for draft in drafts:
        chained = sub.append(draft)
        storage.append(chained)

    # Verify the chain is consistent.
    result = sub.verify()
    assert result.ok is True, f"chain verification failed: {result.reason}"
    assert result.first_bad_index is None

    # Verify the JSONL file was written with exactly 3 lines.
    lines = jsonl_path.read_text().splitlines()
    assert len(lines) == 3, f"expected 3 JSONL lines, got {len(lines)}"
