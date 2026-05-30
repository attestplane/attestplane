# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Structured telemetry for the Opus planning hotline.

Every Opus consultation emits a single ``autodev.plan.consult`` event
via the shared observability stream.  Consumers can pipe that stream
into log aggregators, dashboards, or the autodev train log file.

Typical usage::

    from scripts.opus_consult.telemetry import emit_plan_consult_event

    emit_plan_consult_event(
        milestone="v1.6.0",
        plan_level="daily",
        anchor="v1.5.9",
        head_sha="abc123...",
        duration_ms=1234,
        exit_code=0,
        fallback_used=False,
        prompt_hash="a1b2c3d4e5f6a7b8",
        plan_source="opus-live",
    )
"""

from __future__ import annotations

import hashlib
from typing import Any

from scripts.observability.events import AUTODEV_PLAN_CONSULT, emit_event


def compute_prompt_hash(prompt_text: str) -> str:
    """Return the first 16 hex characters of SHA-256(prompt_text).

    This is intentionally lossy — the full hash is never stored, only the
    redacted prefix, so prompt bodies cannot be reconstructed from telemetry.

    Returns ``"0" * 16`` when *prompt_text* is empty.
    """
    if not prompt_text:
        return "0" * 16
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:16]


def emit_plan_consult_event(
    *,
    milestone: str,
    plan_level: str,
    anchor: str,
    head_sha: str,
    duration_ms: int,
    exit_code: int,
    fallback_used: bool,
    prompt_hash: str,
    plan_source: str,
) -> None:
    """Validate and emit one ``autodev.plan.consult`` event to stdout.

    Args:
        milestone: Milestone tag being planned (e.g. ``"v1.6.0"``).
        plan_level: One of ``"daily"``, ``"medium"``, ``"architecture"``.
        anchor: Anchor tag or ``"repository start"``.
        head_sha: Full SHA of the milestone commit.
        duration_ms: Wall-clock duration of the consultation in milliseconds.
        exit_code: ``0`` on success (Opus returned a valid plan), ``1`` on fallback.
        fallback_used: ``True`` when a deterministic-template fallback was used.
        prompt_hash: First 16 hex chars of SHA-256(consultation prompt).
        plan_source: ``"opus-live"``, ``"opus-fake-response"``, or
            ``"deterministic-template"``.
    """
    payload: dict[str, Any] = {
        "event": AUTODEV_PLAN_CONSULT,
        "milestone": milestone,
        "plan_level": plan_level,
        "anchor": anchor,
        "head_sha": head_sha,
        "duration_ms": duration_ms,
        "exit_code": exit_code,
        "fallback_used": fallback_used,
        "prompt_hash": prompt_hash,
        "plan_source": plan_source,
    }
    emit_event(payload)
