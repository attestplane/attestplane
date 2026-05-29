# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Frozen proof-bundle anchor-state fixtures.

The fixtures in this module are deterministic, offline, and byte-stable
under canonical JSON serialization. They exercise the additive
``anchor_status`` bundle field in both the successful anchored state and
the claim-safe quarantined state that follows a simulated TSA failure.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Literal

from attestplane.hashchain import chain_extend, genesis_head
from attestplane.proof_bundle import ProofBundleBuilder
from attestplane.types import EventDraft

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _build_chain() -> list[Any]:
    head = genesis_head()
    draft = EventDraft(
        event_type="eval_event",
        actor="agent://test/anchor",
        payload={"state": "anchored"},
    )
    event = chain_extend(
        head,
        draft,
        now=_NOW,
        event_id="00000000-0000-7000-8000-00000000a448",
    )
    return [event]


def _build_bundle(
    *,
    chain_id: str,
    anchor_status: Literal["unanchored", "pending", "anchored", "quarantined"],
    anchor_ref: str | None = None,
) -> dict[str, Any]:
    builder = ProofBundleBuilder(chain_id=chain_id, producer_runtime="test")
    builder.extend(_build_chain())
    builder.anchor_status = anchor_status
    if anchor_ref is not None:
        builder.anchor_ref = anchor_ref
    return builder.build(now=_NOW)


ANCHOR_BUNDLE_FIXTURES: dict[str, Any] = {
    "$schema_version": 1,
    "description": (
        "Frozen proof-bundle anchor-state fixtures. The anchored entry "
        "records a successful anchored claim path; the quarantined entry "
        "records the same chain with anchor_status=quarantined after a "
        "simulated TSA failure. Both are byte-stable under canonical JSON "
        "serialization."
    ),
    "entries": [
        {
            "name": "anchored_bundle",
            "bundle": _build_bundle(
                chain_id="anchor-anchored",
                anchor_status="anchored",
                anchor_ref="freetsa.org:0",
            ),
        },
        {
            "name": "quarantined_bundle",
            "bundle": _build_bundle(
                chain_id="anchor-quarantined",
                anchor_status="quarantined",
            ),
        },
    ],
}

ANCHOR_BUNDLE_FIXTURES_JSON = json.dumps(
    ANCHOR_BUNDLE_FIXTURES,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
)
ANCHOR_BUNDLE_FIXTURES_SHA256 = sha256(ANCHOR_BUNDLE_FIXTURES_JSON.encode("utf-8")).hexdigest()
