# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Adapter-conformance fixture replayer (ADR-0014 P2.2).

External runtime adapters (AIOS, LangGraph, custom runtimes) prove
they produce Attestplane-byte-identical `EventDraft`s by replaying a
fixture file against their `translate()` method. This module ships
the canonical replayer.

The fixture format is locked in
:doc:`/adr/0014-adapter-conformance-fixture-pinning`.

The replayer is **pure** — no I/O beyond reading the supplied fixture
path, no clock reads, no network. Calling twice with identical inputs
returns identical outputs.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from attestplane.canonical import canonicalize
from attestplane.types import EventDraft, SubjectRef


@dataclass(frozen=True, slots=True)
class AdapterCaseResult:
    """Outcome for one fixture case."""

    case_name: str
    ok: bool
    reason: str | None
    expected_canonical_hash: str | None
    """SHA-256 hex of the canonical bytes of expected_event_draft (for
    debugging when ok=False)."""
    actual_canonical_hash: str | None
    """SHA-256 hex of the canonical bytes of adapter.translate(...) output."""


@dataclass(frozen=True, slots=True)
class AdapterConformanceReport:
    """Aggregate report for one fixture replay."""

    fixture_path: str
    runtime_kind: str
    fixture_version: int
    cases_total: int
    cases_passed: int
    cases_failed: int
    results: tuple[AdapterCaseResult, ...]

    @property
    def ok(self) -> bool:
        return self.cases_failed == 0


def _eventdraft_to_dict(draft: EventDraft) -> dict[str, Any]:
    """Convert an EventDraft to a JSON-compatible dict matching the
    fixture's expected_event_draft shape."""

    def _subjectref_to_dict(ref: SubjectRef | None) -> dict[str, str] | None:
        if ref is None:
            return None
        return {"scheme": ref.scheme, "value": ref.value}

    return {
        "event_type": draft.event_type,
        "actor": draft.actor,
        "payload": draft.payload,
        "subject_ref": _subjectref_to_dict(draft.subject_ref),
        "session_id": draft.session_id,
        "reference_db_ref": draft.reference_db_ref,
        "matched_input_ref": draft.matched_input_ref,
        "human_verifier": _subjectref_to_dict(draft.human_verifier),
    }


def _canonical_bytes_hash(d: dict[str, Any]) -> str:
    import hashlib

    return hashlib.sha256(canonicalize(d)).hexdigest()


class AdapterConformanceError(Exception):
    """Raised when a fixture file is malformed (not when adapter output mismatches)."""


def _load_and_validate_fixture(fixture_path: str | Path) -> dict[str, Any]:
    """Load + structurally validate a fixture per ADR-0014 § 1.

    Raises :class:`AdapterConformanceError` on bad shape; downstream
    case-by-case mismatches are reported via the result, not raised.
    """
    path = Path(fixture_path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AdapterConformanceError(f"cannot load fixture {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise AdapterConformanceError(f"fixture {path}: top level must be object, got {type(raw).__name__}")
    if raw.get("$schema_version") != 1:
        raise AdapterConformanceError(f"fixture {path}: $schema_version must be 1, got {raw.get('$schema_version')!r}")
    if raw.get("fixture_kind") != "adapter_conformance":
        raise AdapterConformanceError(
            f"fixture {path}: fixture_kind must be 'adapter_conformance', got {raw.get('fixture_kind')!r}"
        )
    if not isinstance(raw.get("runtime_kind"), str) or not raw["runtime_kind"]:
        raise AdapterConformanceError(f"fixture {path}: runtime_kind must be non-empty string")
    if not isinstance(raw.get("fixture_version"), int) or raw["fixture_version"] < 1:
        raise AdapterConformanceError(f"fixture {path}: fixture_version must be integer >= 1")
    cases = raw.get("cases")
    if not isinstance(cases, list) or not cases:
        raise AdapterConformanceError(f"fixture {path}: cases must be non-empty list")
    seen_names: set[str] = set()
    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            raise AdapterConformanceError(f"fixture {path}: cases[{i}] must be object")
        name = case.get("name")
        if not isinstance(name, str) or not name:
            raise AdapterConformanceError(f"fixture {path}: cases[{i}].name must be non-empty string")
        if name in seen_names:
            raise AdapterConformanceError(f"fixture {path}: duplicate case name {name!r}")
        seen_names.add(name)
        if "runtime_event_input" not in case:
            raise AdapterConformanceError(f"fixture {path}: cases[{i}] missing runtime_event_input")
        if "expected_event_draft" not in case:
            raise AdapterConformanceError(f"fixture {path}: cases[{i}] missing expected_event_draft")
        if not isinstance(case["expected_event_draft"], dict):
            raise AdapterConformanceError(f"fixture {path}: cases[{i}].expected_event_draft must be object")
    return raw


def replay_fixture(
    fixture_path: str | Path,
    adapter: Any,
    *,
    pre_translate: Callable[[dict[str, Any]], Any] | None = None,
) -> AdapterConformanceReport:
    """Replay every case in ``fixture_path`` against ``adapter.translate()``.

    :param fixture_path: filesystem path to a JSON fixture matching
        the locked shape (ADR-0014 § 1).
    :param adapter: any object with a ``.translate(runtime_event)`` method
        that returns an :class:`~attestplane.types.EventDraft`.
        Typically a subclass of
        :class:`~attestplane.adapters.GenericRuntimeAdapter`.
    :param pre_translate: optional callable that converts the fixture's
        raw ``runtime_event_input`` dict into the runtime-event type
        the adapter expects (e.g., ``LangSmithAdapter.from_dict``).
        If ``None``, the raw dict is passed directly to ``translate()``.
    :returns: :class:`AdapterConformanceReport`. ``report.ok`` is True
        iff every case's adapter output matches its expected_event_draft
        byte-equal under canonical-JSON.
    """
    fixture = _load_and_validate_fixture(fixture_path)
    results: list[AdapterCaseResult] = []
    passed = 0
    failed = 0
    for case in fixture["cases"]:
        case_name = case["name"]
        runtime_input = case["runtime_event_input"]
        expected = case["expected_event_draft"]
        expected_hash = _canonical_bytes_hash(expected)

        try:
            if pre_translate is not None:
                runtime_event = pre_translate(runtime_input)
            else:
                runtime_event = runtime_input
            actual_draft = adapter.translate(runtime_event)
        except Exception as exc:
            results.append(
                AdapterCaseResult(
                    case_name=case_name,
                    ok=False,
                    reason=f"adapter raised: {type(exc).__name__}: {exc}",
                    expected_canonical_hash=expected_hash,
                    actual_canonical_hash=None,
                )
            )
            failed += 1
            continue

        actual = _eventdraft_to_dict(actual_draft)
        actual_hash = _canonical_bytes_hash(actual)
        if actual_hash == expected_hash:
            results.append(
                AdapterCaseResult(
                    case_name=case_name,
                    ok=True,
                    reason=None,
                    expected_canonical_hash=expected_hash,
                    actual_canonical_hash=actual_hash,
                )
            )
            passed += 1
        else:
            results.append(
                AdapterCaseResult(
                    case_name=case_name,
                    ok=False,
                    reason=(f"canonical-bytes mismatch (expected hash {expected_hash}, got {actual_hash})"),
                    expected_canonical_hash=expected_hash,
                    actual_canonical_hash=actual_hash,
                )
            )
            failed += 1

    return AdapterConformanceReport(
        fixture_path=str(fixture_path),
        runtime_kind=fixture["runtime_kind"],
        fixture_version=fixture["fixture_version"],
        cases_total=len(fixture["cases"]),
        cases_passed=passed,
        cases_failed=failed,
        results=tuple(results),
    )


__all__ = [
    "AdapterCaseResult",
    "AdapterConformanceError",
    "AdapterConformanceReport",
    "replay_fixture",
]
