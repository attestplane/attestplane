# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for :mod:`attestplane.canonical_text`.

Pins behavior against the frozen vector set at
``tests/conformance/text_vectors.json`` and exercises the rejection
rules. Cross-language byte stability is enforced by an identical
vector replay in ``sdk/typescript/test/canonical_text.test.ts``.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any

import pytest

from attestplane.canonical_text import (
    CanonicalTextError,
    canonicalize_text,
    text_hash,
    text_hash_hex,
)

_VECTORS_PATH = Path(__file__).parent / "conformance" / "text_vectors.json"


def _load_vectors() -> dict[str, Any]:
    return json.loads(_VECTORS_PATH.read_text(encoding="utf-8"))


def test_vectors_file_exists_and_has_entries() -> None:
    vectors = _load_vectors()
    assert vectors["$schema_version"] == 1
    assert len(vectors["entries"]) >= 12


@pytest.mark.parametrize("vector_index", range(12))
def test_vector_canonical_bytes_match(vector_index: int) -> None:
    vectors = _load_vectors()
    entry = vectors["entries"][vector_index]
    # NFD inputs are stored as already-decomposed in the JSON; reconstruct
    # the decomposed form via unicodedata.normalize NFD on the composed
    # version to ensure the test exercises the NFC stage rather than
    # accepting whatever form JSON loaded.
    raw_input = entry["input"]
    if entry["name"] == "nfc_decomposed_input":
        raw_input = unicodedata.normalize("NFD", raw_input)
    canonical = canonicalize_text(raw_input)
    assert canonical.hex() == entry["canonical_utf8_hex"], entry["name"]


@pytest.mark.parametrize("vector_index", range(12))
def test_vector_hash_matches(vector_index: int) -> None:
    vectors = _load_vectors()
    entry = vectors["entries"][vector_index]
    raw_input = entry["input"]
    if entry["name"] == "nfc_decomposed_input":
        raw_input = unicodedata.normalize("NFD", raw_input)
    assert text_hash_hex(raw_input) == entry["text_hash_hex"], entry["name"]


def test_nfc_composed_equals_decomposed_hash() -> None:
    """The same logical text in composed and decomposed form MUST hash equal."""
    composed = "café"  # NFC
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed  # paranoia: forms genuinely differ
    assert text_hash(composed) == text_hash(decomposed)


def test_case_insensitive() -> None:
    assert text_hash("AGENT_ALPHA") == text_hash("agent_alpha")
    assert text_hash("Agent_Alpha") == text_hash("agent_alpha")


def test_whitespace_fold_collapses_runs() -> None:
    assert text_hash("agent  alpha") == text_hash("agent alpha")
    assert text_hash("agent\talpha") == text_hash("agent alpha")
    assert text_hash("agent\nalpha") == text_hash("agent alpha")
    assert text_hash("  agent alpha  ") == text_hash("agent alpha")


def test_whitespace_fold_collapses_ideographic_space() -> None:
    # U+3000 IDEOGRAPHIC SPACE is Unicode whitespace.
    assert text_hash("agent　alpha") == text_hash("agent alpha")


def test_zero_width_chars_stripped() -> None:
    for zw in ["​", "‌", "‍", "﻿"]:
        assert text_hash(f"agent{zw}alpha") == text_hash("agentalpha"), (
            f"zero-width {hex(ord(zw))} not stripped"
        )


def test_empty_input_produces_empty_canonical() -> None:
    assert canonicalize_text("") == b""
    assert text_hash_hex("") == hashlib.sha256(b"").hexdigest()


def test_pure_whitespace_input_folds_to_empty() -> None:
    assert canonicalize_text("   \t  \n  ") == b""


def test_canonicalize_text_rejects_non_string() -> None:
    with pytest.raises(CanonicalTextError, match="expects str"):
        canonicalize_text(42)  # type: ignore[arg-type]
    with pytest.raises(CanonicalTextError, match="expects str"):
        canonicalize_text(None)  # type: ignore[arg-type]
    with pytest.raises(CanonicalTextError, match="expects str"):
        canonicalize_text(b"bytes input")  # type: ignore[arg-type]


def test_canonicalize_text_rejects_null_byte() -> None:
    with pytest.raises(CanonicalTextError, match="U\\+0000"):
        canonicalize_text("agent\x00alpha")


def test_canonicalize_text_rejects_unpaired_surrogate() -> None:
    # An unpaired high surrogate is not representable in valid UTF-8.
    bad = "agent\ud800alpha"
    with pytest.raises(CanonicalTextError, match="surrogate"):
        canonicalize_text(bad)


def test_text_hash_returns_32_bytes() -> None:
    h = text_hash("agent")
    assert isinstance(h, bytes)
    assert len(h) == 32


def test_text_hash_hex_is_lowercase_hex() -> None:
    h = text_hash_hex("agent")
    assert len(h) == 64
    assert h == h.lower()
    assert all(c in "0123456789abcdef" for c in h)


def test_pure_function_idempotent() -> None:
    """Same input -> same output across repeated calls."""
    for _ in range(5):
        assert text_hash_hex("Agent Alpha") == text_hash_hex("Agent Alpha")


def test_distinct_inputs_distinct_hashes() -> None:
    a = text_hash_hex("agent_alpha")
    b = text_hash_hex("agent_beta")
    assert a != b


def test_cjk_passthrough() -> None:
    """CJK characters survive NFC + lowercase + whitespace fold."""
    assert text_hash_hex("代理") == text_hash_hex("代理")
    assert text_hash_hex("代理　人") == text_hash_hex("代理 人")
