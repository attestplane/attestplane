# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Conformance tests for ProofBundle.policy_trace_refs (ADR-0012 / P1.2)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from attestplane.event_types import POLICY_CHECK_EVENT, TOOL_CALL_EVENT
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.proof_bundle import ProofBundleBuilder
from attestplane.types import ChainHead, EventDraft

_VECTORS_PATH = (
    Path(__file__).resolve().parent
    / "conformance"
    / "proof_bundle_policy_trace_vectors.json"
)

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _load_vectors() -> dict:
    return json.loads(_VECTORS_PATH.read_text(encoding="utf-8"))


def _build_chain_from_event_types(event_types: list[str]) -> list:
    """Construct a deterministic chain with one event per supplied type."""
    chain = []
    head: ChainHead = genesis_head()
    for i, etype in enumerate(event_types):
        ev = chain_extend(
            head,
            EventDraft(event_type=etype, actor=f"a{i}", payload={"i": i}),
            now=_NOW,
            event_id=f"00000000-0000-7000-8000-{i:012d}",
        )
        chain.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    return chain


def test_vectors_file_loads() -> None:
    v = _load_vectors()
    assert v["$schema_version"] == 1
    assert len(v["builder_vectors"]) == 4


@pytest.mark.parametrize(
    "vec",
    _load_vectors()["builder_vectors"],
    ids=lambda v: v["name"],
)
def test_builder_vector(vec: dict) -> None:
    chain = _build_chain_from_event_types(vec["input"]["chain_event_types"])
    builder = ProofBundleBuilder(
        chain_id="vec-policy-trace",
        producer_runtime="conformance-test",
    )
    builder.extend(chain)
    bundle = builder.build(now=_NOW)

    if vec["expected_field_absent"]:
        assert "policy_trace_refs" not in bundle
        return

    assert "policy_trace_refs" in bundle
    refs = bundle["policy_trace_refs"]
    assert isinstance(refs, list)
    assert len(refs) == vec["expected_policy_trace_refs_count"]

    # Verify each ref is a valid event_hash_hex.
    for r in refs:
        assert isinstance(r, str)
        assert len(r) == 64
        assert all(c in "0123456789abcdef" for c in r)

    # Verify ordering matches the expected chain seqs (per ADR-0012 § 1
    # "chain seq ascending").
    if "expected_seqs" in vec:
        expected_hashes = [
            chain[seq].event_hash.hex() for seq in vec["expected_seqs"]
        ]
        assert refs == expected_hashes


def test_backward_compat_v0_0_1_alpha_bundle_unchanged() -> None:
    """A bundle with no policy_check_event must not contain policy_trace_refs."""
    chain = _build_chain_from_event_types([TOOL_CALL_EVENT] * 3)
    builder = ProofBundleBuilder(
        chain_id="vec-bc",
        producer_runtime="bc-test",
    )
    builder.extend(chain)
    bundle = builder.build(now=_NOW)
    assert "policy_trace_refs" not in bundle, (
        "v0.0.1-alpha-shaped bundles MUST NOT contain policy_trace_refs key"
    )


def test_refs_are_chain_seq_ordered() -> None:
    """Multiple policy events: refs MUST equal chain order, not insertion."""
    types = [TOOL_CALL_EVENT, POLICY_CHECK_EVENT, TOOL_CALL_EVENT, POLICY_CHECK_EVENT]
    chain = _build_chain_from_event_types(types)
    builder = ProofBundleBuilder(chain_id="ord", producer_runtime="ord")
    builder.extend(chain)
    bundle = builder.build(now=_NOW)
    refs = bundle["policy_trace_refs"]
    # Expected order = seqs 1 then 3
    assert refs == [chain[1].event_hash.hex(), chain[3].event_hash.hex()]


def test_refs_have_no_duplicates() -> None:
    """An event_hash uniquely identifies its event; refs MUST NOT duplicate."""
    chain = _build_chain_from_event_types([POLICY_CHECK_EVENT] * 4)
    builder = ProofBundleBuilder(chain_id="dup", producer_runtime="dup")
    builder.extend(chain)
    bundle = builder.build(now=_NOW)
    refs = bundle["policy_trace_refs"]
    assert len(refs) == len(set(refs))
