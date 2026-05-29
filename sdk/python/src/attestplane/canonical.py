# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Restricted-JCS canonicalization for audit-event hashing.

This module implements the restricted JSON profile defined in ADR-0002. The
profile extends RFC 8785 (JCS) with the following constraints, which are
necessary to make Python, TypeScript, and Rust SDKs produce byte-identical
hashes:

- Strings must be UTF-8 NFC normalized.
- Integers are limited to the signed 64-bit range.
- Floats, NaN, and infinities are forbidden.
- Datetimes are serialized as RFC 3339 strings in UTC with microsecond
  precision and a literal ``"Z"`` suffix.
- Bytes are serialized as base64url without padding.
- Object keys must be strings and are emitted in code-point order.

Inputs that violate the profile are rejected with ``CanonicalizationError``
rather than coerced.
"""

from __future__ import annotations

import base64
import unicodedata
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from typing import Any, Final

INT64_MIN: Final[int] = -(2**63)
INT64_MAX: Final[int] = 2**63 - 1
_ASCII_CONTROL_LIMIT: Final[int] = 0x20
_SURROGATE_MIN: Final[int] = 0xD800
_SURROGATE_MAX: Final[int] = 0xDFFF

_ESCAPES: Final[dict[int, str]] = {
    0x08: "\\b",
    0x09: "\\t",
    0x0A: "\\n",
    0x0C: "\\f",
    0x0D: "\\r",
    0x22: '\\"',
    0x5C: "\\\\",
}


class CanonicalizationError(ValueError):
    """Raised when an input violates the restricted JSON profile."""


def canonicalize(value: object) -> bytes:
    """Serialize ``value`` to canonical UTF-8 bytes per the restricted profile.

    Pure function with no side effects. Identical inputs in any SDK
    implementation must produce identical output bytes.
    """

    out: list[str] = []
    _emit(value, out, path="$")
    return "".join(out).encode("utf-8")


def _emit(value: object, out: list[str], *, path: str) -> None:  # noqa: PLR0911
    # Type-dispatch fan-out: each branch terminates with `return` to keep the
    # control flow flat; consolidating into a table would obscure the
    # restricted-profile contract that this dispatch enforces.
    if value is None:
        out.append("null")
        return
    if isinstance(value, bool):
        out.append("true" if value else "false")
        return
    if isinstance(value, int):
        if not (INT64_MIN <= value <= INT64_MAX):
            raise CanonicalizationError(f"{path}: integer {value} outside signed 64-bit range")
        out.append(str(value))
        return
    if isinstance(value, float):
        raise CanonicalizationError(
            f"{path}: float values are forbidden in canonical payloads "
            f"(use integers, base64-encoded bytes, or string representations)"
        )
    if isinstance(value, str):
        _emit_string(value, out, path=path)
        return
    if isinstance(value, bytes):
        encoded = base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
        _emit_string(encoded, out, path=path)
        return
    if isinstance(value, datetime):
        _emit_datetime(value, out, path=path)
        return
    if isinstance(value, dict):
        _emit_object(value, out, path=path)
        return
    if isinstance(value, (list, tuple)):
        _emit_array(value, out, path=path)
        return
    if is_dataclass(value) and not isinstance(value, type):
        _emit_object(_dataclass_to_dict(value), out, path=path)
        return
    raise CanonicalizationError(f"{path}: unsupported type {type(value).__name__!r} in canonical payload")


def _emit_string(value: str, out: list[str], *, path: str) -> None:
    if unicodedata.normalize("NFC", value) != value:
        raise CanonicalizationError(
            f"{path}: string is not Unicode-NFC normalized; normalize before passing to the substrate"
        )
    out.append('"')
    for ch in value:
        code = ord(ch)
        if _SURROGATE_MIN <= code <= _SURROGATE_MAX:
            raise CanonicalizationError(f"{path}: string contains lone surrogate code point")
        escape = _ESCAPES.get(code)
        if escape is not None:
            out.append(escape)
        elif code < _ASCII_CONTROL_LIMIT:
            out.append(f"\\u{code:04x}")
        else:
            out.append(ch)
    out.append('"')


def _emit_datetime(value: datetime, out: list[str], *, path: str) -> None:
    if value.tzinfo is None:
        raise CanonicalizationError(f"{path}: datetime must be timezone-aware")
    if value.utcoffset() != UTC.utcoffset(None):
        raise CanonicalizationError(f"{path}: datetime must be in UTC (got offset {value.utcoffset()})")
    formatted = value.strftime("%Y-%m-%dT%H:%M:%S")
    micro = f".{value.microsecond:06d}"
    _emit_string(formatted + micro + "Z", out, path=path)


def _emit_object(value: dict[Any, Any], out: list[str], *, path: str) -> None:
    out.append("{")
    keys: list[str] = []
    for key in value:
        if not isinstance(key, str):
            raise CanonicalizationError(f"{path}: object keys must be strings (got {type(key).__name__!r})")
        keys.append(key)
    keys.sort()
    seen: set[str] = set()
    for index, key in enumerate(keys):
        if key in seen:
            raise CanonicalizationError(f"{path}: duplicate object key {key!r}")
        seen.add(key)
        if index > 0:
            out.append(",")
        _emit_string(key, out, path=f"{path}.{key}")
        out.append(":")
        _emit(value[key], out, path=f"{path}.{key}")
    out.append("}")


def _emit_array(value: list[Any] | tuple[Any, ...], out: list[str], *, path: str) -> None:
    out.append("[")
    for index, item in enumerate(value):
        if index > 0:
            out.append(",")
        _emit(item, out, path=f"{path}[{index}]")
    out.append("]")


def _dataclass_to_dict(value: Any) -> dict[str, Any]:
    return {f.name: getattr(value, f.name) for f in fields(value)}
