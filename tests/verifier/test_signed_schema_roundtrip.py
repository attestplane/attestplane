# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Issue #139 signed-schema fixture round-trip regression.

The v1.7.0 positive fixture intentionally locks the minimum signed-attestation
schema accepted by the verifier. Rebuilding it here catches both relaxed schema
checks and SDK canonicalization drift with field-level diagnostics.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import attestplane
import pytest

from attestplane.proof_bundle import (
    FrameworkMapping,
    ProofBundleBuilder,
    deserialize_signature_record,
)
from attestplane.storage.jsonl import _deserialize_event as _deserialize_chained_event
from attestplane.types import ChainedEvent
from attestplane.verifier import verify_proof_bundle
from attestplane.verify_errors import VERIFY_OK

ROOT = Path(__file__).resolve().parents[2]
SIGNED_FIXTURES = (ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json",)


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _json_pointer(path: tuple[str, ...]) -> str:
    if not path:
        return "/"
    return "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in path)


def first_json_diff(expected: Any, actual: Any, path: tuple[str, ...] = ()) -> str | None:
    """Return a JSON-pointer diagnostic for the first divergent field."""
    if type(expected) is not type(actual):
        return (
            f"{_json_pointer(path)} type mismatch: "
            f"expected {type(expected).__name__}, actual {type(actual).__name__}"
        )
    if isinstance(expected, dict):
        expected_keys = set(expected)
        actual_keys = set(actual)
        if expected_keys != actual_keys:
            missing = sorted(expected_keys - actual_keys)
            extra = sorted(actual_keys - expected_keys)
            return f"{_json_pointer(path)} key mismatch: missing={missing}, extra={extra}"
        for key in sorted(expected):
            diff = first_json_diff(expected[key], actual[key], (*path, str(key)))
            if diff is not None:
                return diff
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return (
                f"{_json_pointer(path)} length mismatch: "
                f"expected {len(expected)}, actual {len(actual)}"
            )
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual, strict=True)):
            diff = first_json_diff(expected_item, actual_item, (*path, str(index)))
            if diff is not None:
                return diff
        return None
    if expected != actual:
        return f"{_json_pointer(path)} value mismatch: expected {expected!r}, actual {actual!r}"
    return None


def _parse_utc(text: str) -> datetime:
    if text.endswith("Z"):
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    return datetime.fromisoformat(text).astimezone(UTC)


@dataclass(frozen=True)
class _LockedFixtureSigner:
    """Deterministic signer test double for the locked synthetic fixture key."""

    records_by_seq: dict[int, list[Any]]

    def sign_event(self, event: ChainedEvent) -> list[Any]:
        records = self.records_by_seq.get(event.seq, [])
        for record in records:
            assert record.signature_mode == "per_event"
            assert record.signed_event_hash == event.event_hash
        return records


def _signed_fixture_paths() -> Iterator[Path]:
    for path in SIGNED_FIXTURES:
        yield path


def _rehydrate_events(bundle: dict[str, Any]) -> list[ChainedEvent]:
    return [_deserialize_chained_event(raw) for raw in bundle["events"]]


def _framework_mappings(bundle: dict[str, Any]) -> list[FrameworkMapping]:
    return [
        FrameworkMapping(
            obligation_id=raw["obligation_id"],
            evidence_event_indexes=tuple(raw["evidence_event_indexes"]),
            implementation_status_at_bundle_time=raw["implementation_status_at_bundle_time"],
        )
        for raw in bundle.get("framework_mappings", [])
    ]


def rebuild_signed_schema_fixture(bundle: dict[str, Any]) -> dict[str, Any]:
    """Rebuild a locked positive signed-schema fixture through SDK serializers."""
    events = _rehydrate_events(bundle)
    records = [deserialize_signature_record(raw) for raw in bundle["signatures"]]
    records_by_seq: dict[int, list[Any]] = {}
    for record in records:
        records_by_seq.setdefault(record.signed_seq, []).append(record)

    signer = _LockedFixtureSigner(records_by_seq=records_by_seq)
    rebuilt_records: list[Any] = []
    for event in events:
        rebuilt_records.extend(signer.sign_event(event))

    builder = ProofBundleBuilder(
        chain_id=bundle["chain_metadata"]["chain_id"],
        producer_runtime=bundle["chain_metadata"]["producer_runtime"],
        framework_mappings=_framework_mappings(bundle),
        forbidden_fields=tuple(bundle["forbidden_fields"]),
    )
    builder.extend(events)
    builder.extend_signatures(rebuilt_records)
    expected_version = bundle["verification_report"]["verifier_version"]
    original_version = attestplane.__version__
    try:
        attestplane.__version__ = expected_version
        return builder.build(now=_parse_utc(bundle["verification_report"]["verified_at"]))
    finally:
        attestplane.__version__ = original_version


@pytest.mark.parametrize("fixture_path", tuple(_signed_fixture_paths()), ids=lambda path: path.name)
def test_signed_schema_fixture_round_trips_byte_identically(fixture_path: Path) -> None:
    expected = json.loads(fixture_path.read_text(encoding="utf-8"))
    actual = rebuild_signed_schema_fixture(expected)

    diff = first_json_diff(expected, actual)
    assert diff is None, f"{fixture_path.name}: {diff}"
    assert _canonical_json_bytes(actual) == _canonical_json_bytes(expected)


@pytest.mark.parametrize("fixture_path", tuple(_signed_fixture_paths()), ids=lambda path: path.name)
def test_signed_schema_roundtrip_keeps_strict_verifier_contract(fixture_path: Path) -> None:
    expected = json.loads(fixture_path.read_text(encoding="utf-8"))
    actual = rebuild_signed_schema_fixture(expected)

    result = verify_proof_bundle(
        actual,
        require_non_empty=True,
        require_signed_attestation=True,
    )

    assert result.ok is True
    assert result.error_code == VERIFY_OK
    assert result.signed_attestation_schema_ok is True
    assert result.signed_attestation_schema_reason is None
