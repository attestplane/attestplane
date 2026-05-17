# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Replay-manifest verifier — read-only walker, NEVER re-executes.

ADR-0009 A.9 + ADR-0011 P1.1. Given a `ReplayManifest` describing
which original chain segment was replayed and what observed booleans
the external replay runner reported, this module's `verify_replay_manifest`
function checks that the manifest is internally consistent against
the chain provided by the caller.

**Hard constraint** (per ADR-0009 § B.6 + invariant 7): this module
NEVER re-executes the workload. It does not call any external system.
It only walks the provided chain looking for ``replay_event`` payloads
that match the manifest's claims and confirms their internal
consistency. Replay execution lives in REDLINE C.13
(``aios-replay-runner``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from attestplane.event_payloads import validate_replay_event_payload

# We intentionally avoid importing ChainedEvent / verify_chain types here to
# keep this module independent of hashchain implementation details. The
# verifier accepts a list of dicts (ordered by seq) containing at minimum
# {"seq": int, "event_type": str, "payload": dict}. This matches the
# JSONL storage backend's serialised form and the proof_bundle wire format.


ReplayCoverage = Literal["deterministic", "non_deterministic", "no_replay_event"]
"""Outcomes of `verify_replay_manifest`.

- ``deterministic``: manifest's ``deterministic_result=true`` matched at
  least one ``replay_event`` payload in the chain with the same
  ``replay_run_id``.
- ``non_deterministic``: matching event found but its ``deterministic_result``
  was ``false`` (some divergence reported by the external runner).
- ``no_replay_event``: no ``replay_event`` payload in the chain has
  the manifest's ``replay_run_id``.
"""


@dataclass(frozen=True, slots=True)
class ReplayManifest:
    """Manifest describing a replay claim made by an external runner.

    The verifier does NOT execute the replay itself. The manifest tells
    the verifier what to look for in the chain.
    """

    replay_run_id: str
    original_run_id: str
    expected_deterministic: bool
    """The runner's claimed outcome. The verifier checks the chain agrees."""

    snapshot_id_ref: str | None = None


@dataclass(frozen=True, slots=True)
class ReplayVerificationResult:
    """Outcome of :func:`verify_replay_manifest`.

    The ``ok`` field is true iff:

    - At least one ``replay_event`` payload in the chain matches the
      manifest's ``replay_run_id`` and ``original_run_id``.
    - That payload's ``deterministic_result`` matches the manifest's
      ``expected_deterministic``.
    - The payload's internal AND cross-check (validated by
      ``validate_replay_event_payload``) is satisfied.
    """

    ok: bool
    coverage: ReplayCoverage
    matching_seq: int | None
    """The chain seq of the matching ``replay_event``, or None."""
    reason: str | None


def verify_replay_manifest(
    chain_events: list[dict[str, Any]],
    manifest: ReplayManifest,
    *,
    verification_time: datetime | None = None,
) -> ReplayVerificationResult:
    """Check that ``chain_events`` contains a ``replay_event`` matching ``manifest``.

    Read-only. Pure function. Never re-executes. Never modifies anything.

    :param chain_events: list of event dicts (typically
        ``ProofBundle["events"][i]`` rows, or the JSONL store's
        ``_serialize_event`` output). Each dict MUST contain
        ``seq``, ``event_type``, ``payload``.
    :param manifest: the :class:`ReplayManifest` describing the
        external runner's claim.
    :param verification_time: optional UTC datetime; reserved for
        future window-validity checks. Currently unused.
    """
    if not isinstance(chain_events, list):
        return ReplayVerificationResult(
            ok=False,
            coverage="no_replay_event",
            matching_seq=None,
            reason=f"chain_events must be list, got {type(chain_events).__name__}",
        )
    if verification_time is not None and verification_time.tzinfo is None:
        return ReplayVerificationResult(
            ok=False,
            coverage="no_replay_event",
            matching_seq=None,
            reason="verification_time must be UTC-aware",
        )

    candidates: list[tuple[int, dict[str, Any]]] = []
    for ev in chain_events:
        if not isinstance(ev, dict):
            continue
        if ev.get("event_type") != "replay_event":
            continue
        payload = ev.get("payload")
        if not isinstance(payload, dict):
            continue
        if payload.get("replay_run_id") != manifest.replay_run_id:
            continue
        if payload.get("original_run_id") != manifest.original_run_id:
            continue
        if (
            manifest.snapshot_id_ref is not None
            and payload.get("snapshot_id_ref") != manifest.snapshot_id_ref
        ):
            continue
        seq = ev.get("seq")
        if not isinstance(seq, int):
            continue
        candidates.append((seq, payload))

    if not candidates:
        return ReplayVerificationResult(
            ok=False,
            coverage="no_replay_event",
            matching_seq=None,
            reason=(
                f"no replay_event payload found with "
                f"replay_run_id={manifest.replay_run_id!r}"
            ),
        )

    # Use the latest matching candidate (largest seq) — convention: the
    # most recent observation of the replay outcome is authoritative.
    candidates.sort(key=lambda item: item[0])
    seq, payload = candidates[-1]

    # Defensive: validate the payload's internal consistency. If the
    # producer wrote a bad replay_event payload (mismatched AND), the
    # verifier surfaces that as the failure reason. validate_*() raises
    # ValueError; we capture and convert to a soft result.
    try:
        validate_replay_event_payload(payload)
    except ValueError as exc:
        return ReplayVerificationResult(
            ok=False,
            coverage="no_replay_event",
            matching_seq=seq,
            reason=f"matching replay_event payload failed validation: {exc}",
        )

    actual_det = bool(payload["deterministic_result"])
    if manifest.expected_deterministic != actual_det:
        return ReplayVerificationResult(
            ok=False,
            coverage="non_deterministic" if not actual_det else "deterministic",
            matching_seq=seq,
            reason=(
                f"manifest expected deterministic_result={manifest.expected_deterministic}, "
                f"chain payload reports {actual_det}"
            ),
        )

    return ReplayVerificationResult(
        ok=True,
        coverage="deterministic" if actual_det else "non_deterministic",
        matching_seq=seq,
        reason=None,
    )


__all__ = [
    "ReplayCoverage",
    "ReplayManifest",
    "ReplayVerificationResult",
    "verify_replay_manifest",
]
