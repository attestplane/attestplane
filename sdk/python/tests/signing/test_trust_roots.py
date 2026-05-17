# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for :mod:`attestplane.signing.trust_roots` (T4 loader)."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from pathlib import Path

import pytest

pytest.importorskip("cryptography")
pytest.importorskip("yaml")

from attestplane.signing import (
    InMemoryKeyProvider,
    TrustRootsError,
    derive_key_id,
    load_trust_roots,
)


def _make_entry_yaml(seed: bytes, *, key_id: str | None = None,
                     vf: str = "2026-05-17T00:00:00Z",
                     vu: str = "2027-05-17T00:00:00Z") -> tuple[str, str]:
    """Return (key_id, single-entry YAML string)."""
    p = InMemoryKeyProvider(seed=seed)
    der = p.get_signing_material().public_key_der
    derived = derive_key_id(der)
    b64 = base64.standard_b64encode(der).decode("ascii")
    actual_kid = key_id if key_id is not None else derived
    yaml_text = f"""version: 1
keys:
  - key_id: "{actual_kid}"
    public_key_der_b64: "{b64}"
    valid_from: "{vf}"
    valid_until: "{vu}"
    provider_id: "test-{derived[:8]}"
    label: "Test Key"
"""
    return derived, yaml_text


def test_load_minimal_valid_yaml(tmp_path: Path) -> None:
    derived, text = _make_entry_yaml(b"\x00" * 32)
    p = tmp_path / "tr.yaml"
    p.write_text(text)
    tr = load_trust_roots(p)
    assert tr.version == 1
    assert len(tr.entries) == 1
    assert tr.entries[0].key_id == derived


def test_lookup_returns_entry() -> None:
    """Direct test of TrustRoots.lookup()."""
    from attestplane.signing.trust_roots import TrustRootEntry, TrustRoots
    entry = TrustRootEntry(
        key_id="ab" * 16,
        public_key_der=b"\x00" * 44,
        valid_from=datetime(2026, 5, 17, tzinfo=UTC),
        valid_until=datetime(2027, 5, 17, tzinfo=UTC),
        provider_id=None,
        label=None,
    )
    tr = TrustRoots(version=1, entries=(entry,))
    assert tr.lookup("ab" * 16) is entry
    assert tr.lookup("cd" * 16) is None


# --- File-level rejections -------------------------------------------------


def test_load_missing_file(tmp_path: Path) -> None:
    with pytest.raises(TrustRootsError, match="not found"):
        load_trust_roots(tmp_path / "missing.yaml")


def test_load_exceeds_size_cap(tmp_path: Path) -> None:
    p = tmp_path / "big.yaml"
    # 1 MB + 1 byte = should be rejected.
    p.write_bytes(b"a" * (1024 * 1024 + 1))
    with pytest.raises(TrustRootsError, match="1 MB"):
        load_trust_roots(p)


def test_load_bad_yaml(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("not: a: valid: yaml: :")
    with pytest.raises(TrustRootsError, match="YAML parse"):
        load_trust_roots(p)


def test_load_rejects_non_mapping(tmp_path: Path) -> None:
    p = tmp_path / "list.yaml"
    p.write_text("- one\n- two\n")
    with pytest.raises(TrustRootsError, match="top-level must be a mapping"):
        load_trust_roots(p)


# --- Top-level schema rejections -------------------------------------------


def test_load_rejects_missing_version(tmp_path: Path) -> None:
    p = tmp_path / "x.yaml"
    p.write_text("keys: []\n")
    with pytest.raises(TrustRootsError, match="missing required top-level"):
        load_trust_roots(p)


def test_load_rejects_wrong_version(tmp_path: Path) -> None:
    _, text = _make_entry_yaml(b"\x00" * 32)
    p = tmp_path / "x.yaml"
    p.write_text(text.replace("version: 1", "version: 99"))
    with pytest.raises(TrustRootsError, match="version must be 1"):
        load_trust_roots(p)


def test_load_rejects_unexpected_top_level(tmp_path: Path) -> None:
    _, text = _make_entry_yaml(b"\x00" * 32)
    p = tmp_path / "x.yaml"
    p.write_text(text + "extra_field: oops\n")
    with pytest.raises(TrustRootsError, match="unexpected top-level"):
        load_trust_roots(p)


def test_load_rejects_empty_keys_list(tmp_path: Path) -> None:
    p = tmp_path / "x.yaml"
    p.write_text("version: 1\nkeys: []\n")
    with pytest.raises(TrustRootsError, match="at least one"):
        load_trust_roots(p)


def test_load_rejects_keys_not_list(tmp_path: Path) -> None:
    p = tmp_path / "x.yaml"
    p.write_text("version: 1\nkeys: not-a-list\n")
    with pytest.raises(TrustRootsError, match="must be a list"):
        load_trust_roots(p)


# --- Per-entry schema rejections -------------------------------------------


def test_load_rejects_entry_missing_field(tmp_path: Path) -> None:
    p = tmp_path / "x.yaml"
    p.write_text(
        "version: 1\n"
        "keys:\n"
        '  - key_id: "00112233445566778899aabbccddeeff"\n'
    )
    with pytest.raises(TrustRootsError, match="missing required fields"):
        load_trust_roots(p)


def test_load_rejects_entry_unexpected_field(tmp_path: Path) -> None:
    _, text = _make_entry_yaml(b"\x00" * 32)
    p = tmp_path / "x.yaml"
    # Inject an unexpected per-entry key.
    text = text.rstrip() + '\n    unexpected_field: "oops"\n'
    p.write_text(text)
    with pytest.raises(TrustRootsError, match="unexpected fields"):
        load_trust_roots(p)


def test_load_rejects_bad_key_id_format(tmp_path: Path) -> None:
    _, text = _make_entry_yaml(b"\x00" * 32, key_id="not-hex-and-wrong-length")
    p = tmp_path / "x.yaml"
    p.write_text(text)
    with pytest.raises(TrustRootsError, match="32 lowercase hex"):
        load_trust_roots(p)


def test_load_rejects_key_id_mismatch(tmp_path: Path) -> None:
    """key_id MUST equal derive_key_id(public_key_der_b64)."""
    _, text = _make_entry_yaml(b"\x00" * 32, key_id="ff" * 16)
    p = tmp_path / "x.yaml"
    p.write_text(text)
    with pytest.raises(TrustRootsError, match="does not match derive_key_id"):
        load_trust_roots(p)


def test_load_rejects_naive_datetime(tmp_path: Path) -> None:
    _, text = _make_entry_yaml(b"\x00" * 32, vf="2026-05-17T00:00:00")
    p = tmp_path / "x.yaml"
    p.write_text(text)
    with pytest.raises(TrustRootsError, match="UTC-aware"):
        load_trust_roots(p)


def test_load_rejects_non_utc_datetime(tmp_path: Path) -> None:
    _, text = _make_entry_yaml(b"\x00" * 32, vf="2026-05-17T00:00:00+05:00")
    p = tmp_path / "x.yaml"
    p.write_text(text)
    with pytest.raises(TrustRootsError, match="must be UTC"):
        load_trust_roots(p)


def test_load_rejects_inverted_validity_window(tmp_path: Path) -> None:
    _, text = _make_entry_yaml(
        b"\x00" * 32,
        vf="2027-05-17T00:00:00Z",
        vu="2026-05-17T00:00:00Z",
    )
    p = tmp_path / "x.yaml"
    p.write_text(text)
    with pytest.raises(TrustRootsError, match="strictly before"):
        load_trust_roots(p)


def test_load_rejects_duplicate_key_id(tmp_path: Path) -> None:
    derived, text_one = _make_entry_yaml(b"\x00" * 32)
    # Build a YAML with TWO entries having the same key_id.
    import base64
    der = InMemoryKeyProvider(seed=b"\x00" * 32).get_signing_material().public_key_der
    b64 = base64.standard_b64encode(der).decode("ascii")
    yaml_text = f"""version: 1
keys:
  - key_id: "{derived}"
    public_key_der_b64: "{b64}"
    valid_from: "2026-05-17T00:00:00Z"
    valid_until: "2027-05-17T00:00:00Z"
  - key_id: "{derived}"
    public_key_der_b64: "{b64}"
    valid_from: "2026-05-17T00:00:00Z"
    valid_until: "2027-05-17T00:00:00Z"
"""
    p = tmp_path / "dup.yaml"
    p.write_text(yaml_text)
    with pytest.raises(TrustRootsError, match="duplicate key_id"):
        load_trust_roots(p)


def test_load_rejects_invalid_base64(tmp_path: Path) -> None:
    derived = "0" * 32
    p = tmp_path / "x.yaml"
    p.write_text(f"""version: 1
keys:
  - key_id: "{derived}"
    public_key_der_b64: "***not base64***"
    valid_from: "2026-05-17T00:00:00Z"
    valid_until: "2027-05-17T00:00:00Z"
""")
    with pytest.raises(TrustRootsError, match="invalid base64"):
        load_trust_roots(p)
