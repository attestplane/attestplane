# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Restricted text canonicalizer for cross-language hash stability.

A second, independent canonicalization primitive alongside the JSON
canonicalizer in :mod:`attestplane.canonical`. The text canonicalizer is
intended for cases where the substrate (or a verifier) needs to compare
free-form strings — actor identifiers, free-text reasons hashed for
proof, framework citations, etc. — without sensitivity to typographic
differences that are semantically irrelevant.

The four-stage algorithm is locked by ``docs/spec/canonical-text-v1.md``:

1. **NFC normalize** — Unicode Canonical Decomposition followed by
   Canonical Composition. Removes representational ambiguity for
   accented characters and pre-composed vs. decomposed forms.
2. **Unicode default lowercase** — :py:meth:`str.lower` is Unicode-aware
   and uses the Default Case Conversion algorithm. Cross-language byte
   stable for ASCII letters and most common European characters; see
   ``canonical-text-v1.md § Cross-language stability`` for the edge-case
   list (Turkish dotted i, German sharp s, certain Greek mappings).
3. **Zero-width strip** — remove U+200B (ZERO WIDTH SPACE), U+200C
   (ZERO WIDTH NON-JOINER), U+200D (ZERO WIDTH JOINER), U+FEFF
   (ZERO WIDTH NO-BREAK SPACE / BOM). These are invisible characters
   commonly used to defeat string comparison.
4. **Whitespace fold** — collapse any run of Unicode whitespace into a
   single ASCII space (U+0020); trim leading and trailing whitespace.

The output of :func:`canonicalize_text` is the UTF-8 encoding of the
normalized string. :func:`text_hash` is the SHA-256 of those bytes.

The primitive is intentionally narrow: it does not strip punctuation,
does not transliterate, does not remove diacritics. Those operations
are lossy in ways that obscure compliance evidence (e.g., the
difference between "García" and "Garcia" can be load-bearing for
identity disambiguation). NFC normalization is the only diacritic-level
operation, and it preserves all visual information.
"""

from __future__ import annotations

import hashlib
import unicodedata
from typing import Final

_ZERO_WIDTH_CHARS: Final[frozenset[str]] = frozenset(
    {
        "\u200b",  # ZERO WIDTH SPACE
        "‌",  # ZERO WIDTH NON-JOINER
        "‍",  # ZERO WIDTH JOINER
        "﻿",  # ZERO WIDTH NO-BREAK SPACE (BOM)
    }
)


class CanonicalTextError(ValueError):
    """Raised when an input cannot be canonicalized.

    v1 raises on these inputs:

    - Non-string types
    - Strings containing unpaired surrogates (U+D800–U+DFFF)
    - Strings containing the null character (U+0000)
    """


def canonicalize_text(text: str) -> bytes:
    """Return the canonical UTF-8 bytes of ``text``.

    Pure, deterministic, cross-language byte stable for the input set
    described in :mod:`canonical_text` and the spec document. Identical
    inputs in any conforming SDK implementation MUST produce identical
    output bytes.
    """
    if not isinstance(text, str):
        raise CanonicalTextError(f"canonicalize_text expects str, got {type(text).__name__}")

    # Reject inputs that contain code points that have no defensible
    # canonical form. Null bytes terminate strings in many languages and
    # are a common smuggling vector; unpaired surrogates are not valid
    # UTF-8 and would cause encode-time failures downstream anyway.
    for ch in text:
        code = ord(ch)
        if code == 0:
            raise CanonicalTextError("input contains U+0000 (null) — forbidden")
        if 0xD800 <= code <= 0xDFFF:
            raise CanonicalTextError(f"input contains unpaired surrogate U+{code:04X} — forbidden")

    # Stage 1: NFC.
    nfc = unicodedata.normalize("NFC", text)

    # Stage 2: Unicode default lowercase.
    lowered = nfc.lower()

    # Stage 3: zero-width strip.
    stripped_chars = [ch for ch in lowered if ch not in _ZERO_WIDTH_CHARS]

    # Stage 4: whitespace fold.
    # ``"".join`` then ``str.split()`` is the simplest cross-language
    # equivalent operation: split on any run of Unicode whitespace, then
    # rejoin with a single ASCII space. Trims edges as a side effect.
    folded = " ".join("".join(stripped_chars).split())

    return folded.encode("utf-8")


def text_hash(text: str) -> bytes:
    """SHA-256 of ``canonicalize_text(text)``. Returns 32 raw bytes."""
    return hashlib.sha256(canonicalize_text(text)).digest()


def text_hash_hex(text: str) -> str:
    """Lowercase hex form of :func:`text_hash`."""
    return text_hash(text).hex()


__all__ = [
    "CanonicalTextError",
    "canonicalize_text",
    "text_hash",
    "text_hash_hex",
]
