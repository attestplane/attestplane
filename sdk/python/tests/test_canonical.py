# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the restricted-JCS canonicalization layer."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta, timezone

import pytest

from attestplane.canonical import CanonicalizationError, canonicalize
from attestplane.types import SubjectRef


def test_primitives() -> None:
    assert canonicalize(None) == b"null"
    assert canonicalize(True) == b"true"
    assert canonicalize(False) == b"false"
    assert canonicalize(0) == b"0"
    assert canonicalize(42) == b"42"
    assert canonicalize(-1) == b"-1"


def test_string_basic() -> None:
    assert canonicalize("hello") == b'"hello"'


def test_string_escapes() -> None:
    assert canonicalize('quote: "') == b'"quote: \\""'
    assert canonicalize("back\\slash") == b'"back\\\\slash"'
    assert canonicalize("tab\tin") == b'"tab\\tin"'
    assert canonicalize("line\nbreak") == b'"line\\nbreak"'
    assert canonicalize("\x01") == b'"\\u0001"'


def test_string_unicode_nfc_required() -> None:
    nfc = "é"
    nfd = "é"
    assert canonicalize(nfc) == b'"\xc3\xa9"'
    with pytest.raises(CanonicalizationError, match="NFC"):
        canonicalize(nfd)


def test_string_rejects_lone_surrogate() -> None:
    with pytest.raises(CanonicalizationError, match="surrogate"):
        canonicalize("\ud800")
    with pytest.raises(CanonicalizationError, match="surrogate"):
        canonicalize("\udc00")


def test_canonical_json_does_not_normalize_strings_implicitly() -> None:
    assert canonicalize("①") == '"①"'.encode()
    with pytest.raises(CanonicalizationError, match="NFC"):
        canonicalize("A\u030a")


def test_int64_bounds() -> None:
    assert canonicalize(2**63 - 1) == str(2**63 - 1).encode()
    assert canonicalize(-(2**63)) == str(-(2**63)).encode()
    with pytest.raises(CanonicalizationError, match="64-bit"):
        canonicalize(2**63)
    with pytest.raises(CanonicalizationError, match="64-bit"):
        canonicalize(-(2**63) - 1)


def test_float_rejected() -> None:
    with pytest.raises(CanonicalizationError, match="float"):
        canonicalize(1.5)
    with pytest.raises(CanonicalizationError, match="float"):
        canonicalize(math.nan)
    with pytest.raises(CanonicalizationError, match="float"):
        canonicalize(math.inf)


def test_bytes_base64url_no_padding() -> None:
    assert canonicalize(b"\x00\x01\x02") == b'"AAEC"'
    assert canonicalize(b"abc") == b'"YWJj"'
    assert canonicalize(b"") == b'""'


def test_datetime_required_utc() -> None:
    naive = datetime(2026, 5, 17, 12, 0, 0, 123456)
    with pytest.raises(CanonicalizationError, match="timezone-aware"):
        canonicalize(naive)


def test_datetime_must_be_utc_offset() -> None:
    plus_one = datetime(2026, 5, 17, 12, 0, 0, 0, tzinfo=timezone(timedelta(hours=1)))
    with pytest.raises(CanonicalizationError, match="UTC"):
        canonicalize(plus_one)


def test_datetime_rfc3339_microsecond_z() -> None:
    value = datetime(2026, 5, 17, 12, 0, 0, 123456, tzinfo=UTC)
    assert canonicalize(value) == b'"2026-05-17T12:00:00.123456Z"'


def test_object_sorted_keys() -> None:
    assert canonicalize({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
    assert canonicalize({"z": True, "a": None, "m": "x"}) == b'{"a":null,"m":"x","z":true}'


def test_object_rejects_non_string_keys() -> None:
    with pytest.raises(CanonicalizationError, match="strings"):
        canonicalize({1: "one"})


def test_nested() -> None:
    obj = {"outer": {"b": [1, 2, 3], "a": "x"}}
    assert canonicalize(obj) == b'{"outer":{"a":"x","b":[1,2,3]}}'


def test_array_preserves_order() -> None:
    assert canonicalize([3, 1, 2]) == b"[3,1,2]"
    assert canonicalize([]) == b"[]"
    assert canonicalize((1, 2)) == b"[1,2]"


def test_unsupported_type_rejected() -> None:
    class Custom:
        pass

    with pytest.raises(CanonicalizationError, match="unsupported"):
        canonicalize(Custom())


def test_subject_ref_dataclass_serializes() -> None:
    ref = SubjectRef(scheme="opaque", value="abc")
    assert canonicalize(ref) == b'{"scheme":"opaque","value":"abc"}'


def test_deterministic_across_dict_insertion_order() -> None:
    a = canonicalize({"x": 1, "y": 2, "z": 3})
    b = canonicalize({"z": 3, "y": 2, "x": 1})
    assert a == b
