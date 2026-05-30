# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for T5 — ProofBundleBuilder additive signatures + JSON Schema.

Validates:

- ``signatures`` field absent when no records added (backward-compat
  for v0.0.2-alpha bundles).
- ``signatures`` present + JSON-Schema-valid when records added.
- Round-trip: serialise → JSON → ``deserialize_signature_record`` →
  identical :class:`SignatureRecord` instance.
- ``extend_signatures`` rejects malformed input (missing field).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from attestplane.hashchain import chain_extend, genesis_head
from attestplane.proof_bundle import (
    ProofBundleBuilder,
    deserialize_signature_record,
)
from attestplane.signing import InMemoryKeyProvider, Signer
from attestplane.types import ChainHead, EventDraft

pytest.importorskip("cryptography")
jsonschema = pytest.importorskip("jsonschema")

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_SCHEMAS_DIR = Path(__file__).resolve().parents[4] / "schemas" / "v1"


def _load_schema() -> dict:
    return json.loads((_SCHEMAS_DIR / "proof_bundle.schema.json").read_text("utf-8"))


def _build_chain(n: int) -> list:
    chain = []
    head = genesis_head()
    for i in range(n):
        ev = chain_extend(
            head,
            EventDraft(event_type="eval_event", actor=f"a{i}", payload={"i": i}),
            now=_NOW,
            event_id=f"00000000-0000-7000-8000-{i:012d}",
        )
        chain.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    return chain


def test_bundle_without_signatures_omits_field() -> None:
    """Backward compatibility: v0.0.2-alpha bundles don't have a `signatures` key."""
    builder = ProofBundleBuilder(chain_id="x", producer_runtime="test")
    builder.extend(_build_chain(2))
    bundle = builder.build()
    assert "signatures" not in bundle


def test_bundle_with_signatures_emits_field() -> None:
    chain = _build_chain(3)
    builder = ProofBundleBuilder(chain_id="x", producer_runtime="test")
    builder.extend(chain)

    signer = Signer(
        chain_id="x",
        key_provider=InMemoryKeyProvider(seed=b"\x00" * 32),
        now=lambda: _NOW,
    )
    records = signer.sign_segment_head(
        ChainHead(seq=2, event_hash=chain[2].event_hash),
    )
    builder.extend_signatures(records)

    bundle = builder.build()
    assert "signatures" in bundle
    assert len(bundle["signatures"]) == 1


def test_bundle_with_signatures_validates_against_schema() -> None:
    chain = _build_chain(2)
    builder = ProofBundleBuilder(chain_id="x", producer_runtime="test")
    builder.extend(chain)
    signer = Signer(
        chain_id="x",
        key_provider=InMemoryKeyProvider(seed=b"\x01" * 32),
        now=lambda: _NOW,
    )
    records = signer.sign_event(chain[1])
    builder.extend_signatures(records)

    bundle = builder.build()
    jsonschema.validate(bundle, _load_schema())


def test_signature_record_round_trips_through_json() -> None:
    chain = _build_chain(1)
    signer = Signer(
        chain_id="rt",
        key_provider=InMemoryKeyProvider(seed=b"\x02" * 32),
        now=lambda: _NOW,
    )
    records = signer.sign_event(chain[0])
    builder = ProofBundleBuilder(chain_id="rt", producer_runtime="test")
    builder.extend(chain)
    builder.extend_signatures(records)
    bundle = builder.build()

    # Serialise → JSON → reparse → deserialise → equality.
    json_text = json.dumps(bundle, sort_keys=True)
    reparsed = json.loads(json_text)

    sig_dicts = reparsed["signatures"]
    assert len(sig_dicts) == 1
    recovered = deserialize_signature_record(sig_dicts[0])

    original = records[0]
    assert recovered == original


def test_extend_signatures_rejects_malformed() -> None:
    builder = ProofBundleBuilder(chain_id="x", producer_runtime="test")
    with pytest.raises(ValueError, match="missing SignatureRecord"):
        builder.extend_signatures([{"not": "a-record"}])  # type: ignore[list-item]


def test_multi_signer_records_in_bundle_are_distinct() -> None:
    """Two seeds → two records, byte-different signatures, same payload."""
    from attestplane.signing import MultiSignerProvider

    chain = _build_chain(2)
    multi = MultiSignerProvider(
        [
            InMemoryKeyProvider(seed=b"\x00" * 32, provider_id="alpha"),
            InMemoryKeyProvider(seed=b"\x02" * 32, provider_id="beta"),
        ]
    )
    signer = Signer(chain_id="m", key_provider=multi, now=lambda: _NOW)
    records = signer.sign_segment_head(
        ChainHead(seq=1, event_hash=chain[1].event_hash),
    )

    builder = ProofBundleBuilder(chain_id="m", producer_runtime="test")
    builder.extend(chain)
    builder.extend_signatures(records)
    bundle = builder.build()

    assert len(bundle["signatures"]) == 2
    s0, s1 = bundle["signatures"][0], bundle["signatures"][1]
    assert s0["signed_payload_b64"] == s1["signed_payload_b64"]
    assert s0["signature_hex"] != s1["signature_hex"]
    assert s0["key_id"] != s1["key_id"]


def test_deserialize_signature_record_missing_field() -> None:
    with pytest.raises(ValueError, match="missing fields"):
        deserialize_signature_record({"signature_schema_version": 1})


def test_schema_locks_signature_mode_enum() -> None:
    """Schema-level lock: signature_mode is segment_head or per_event only."""
    schema = _load_schema()
    enum = schema["properties"]["signatures"]["items"]["properties"]["signature_mode"]["enum"]
    assert set(enum) == {"segment_head", "per_event"}


def test_schema_locks_key_id_format() -> None:
    """Schema-level lock: key_id MUST be 32 lowercase hex chars."""
    schema = _load_schema()
    pattern = schema["properties"]["signatures"]["items"]["properties"]["key_id"]["pattern"]
    assert pattern == "^[0-9a-f]{32}$"
