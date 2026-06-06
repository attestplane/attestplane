# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coverage-gap tests for attestplane.signing.trust_roots, providers, and base.

trust_roots.py missing:  104, 110-113, 123, 127, 139, 146, 152, 170, 173,
                         201-202, 208-209
providers.py missing:    121-122, 175-176, 178
base.py missing:         296
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("cryptography")
pytest.importorskip("yaml")

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from attestplane.signing import (
    InMemoryKeyProvider,
    derive_key_id,
)
from attestplane.signing.base import (
    SIGNATURE_SCHEMA_VERSION,
    KeyProvider,
    KeyProviderError,
    SigningMaterial,
)
from attestplane.signing.providers import EnvKeyProvider, FileKeyProvider
from attestplane.signing.trust_roots import (
    TrustRootsError,
    _parse_datetime,
    _validate_entry,
    load_trust_roots,
)


def _make_valid_der() -> bytes:
    """Return a fresh Ed25519 SPKI DER."""
    return InMemoryKeyProvider().get_signing_material().public_key_der


def _make_entry_yaml(
    seed: bytes,
    *,
    key_id: str | None = None,
    vf: str = "2026-05-17T00:00:00Z",
    vu: str = "2027-05-17T00:00:00Z",
) -> tuple[str, str]:
    p = InMemoryKeyProvider(seed=seed)
    der = p.get_signing_material().public_key_der
    derived = derive_key_id(der)
    b64 = base64.standard_b64encode(der).decode("ascii")
    actual_kid = key_id if key_id is not None else derived
    text = f"""version: 1
keys:
  - key_id: "{actual_kid}"
    public_key_der_b64: "{b64}"
    valid_from: "{vf}"
    valid_until: "{vu}"
"""
    return derived, text


# =============================================================================
# trust_roots.py: _parse_datetime
# =============================================================================


# Line 104: raw is already a datetime object (not string)
def test_parse_datetime_accepts_datetime_object() -> None:
    """Line 104: if isinstance(raw, datetime) branch → returns dt directly."""
    dt_in = datetime(2026, 5, 17, tzinfo=UTC)
    result = _parse_datetime(dt_in, "test_field")
    assert result == dt_in


# Line 104: datetime object but naive → raises
def test_parse_datetime_naive_datetime_object_raises() -> None:
    """Line 104 then 114: datetime object but no tzinfo → TrustRootsError."""
    naive = datetime(2026, 5, 17)
    with pytest.raises(TrustRootsError, match="UTC-aware"):
        _parse_datetime(naive, "test_field")


# Line 104: datetime object but non-UTC offset → raises
def test_parse_datetime_non_utc_datetime_object_raises() -> None:
    """Line 104 then 116-117: datetime with +05:00 offset → TrustRootsError."""
    from datetime import timedelta
    tz_pos5 = timezone(timedelta(hours=5))
    dt = datetime(2026, 5, 17, tzinfo=tz_pos5)
    with pytest.raises(TrustRootsError, match="must be UTC"):
        _parse_datetime(dt, "test_field")


# Lines 110-113: invalid ISO 8601 string
def test_parse_datetime_invalid_iso8601_string_raises() -> None:
    """Lines 110-113: fromisoformat fails → TrustRootsError with 'not valid ISO 8601'."""
    with pytest.raises(TrustRootsError, match="not valid ISO 8601"):
        _parse_datetime("not-a-date", "test_field")


# Lines 112-113: another invalid ISO string
def test_parse_datetime_partial_date_raises() -> None:
    """Lines 110-113: partial date like '2026-13-99' → TrustRootsError."""
    with pytest.raises(TrustRootsError, match="not valid ISO 8601"):
        _parse_datetime("2026-13-99T00:00:00+00:00", "test_field")


# Line 113 (else branch): raw is neither datetime nor string
def test_parse_datetime_non_string_non_datetime_raises() -> None:
    """Line 113: raw is int → TrustRootsError 'must be string or datetime'."""
    with pytest.raises(TrustRootsError, match="must be string or datetime"):
        _parse_datetime(12345, "test_field")


# Line 113: raw is a list
def test_parse_datetime_list_raises() -> None:
    """Line 113: raw is list → TrustRootsError."""
    with pytest.raises(TrustRootsError, match="must be string or datetime"):
        _parse_datetime([], "test_field")


# =============================================================================
# trust_roots.py: _validate_entry
# =============================================================================


# Line 123: entry is not a dict
def test_validate_entry_not_a_dict_raises() -> None:
    """Line 123: entry is a list, not a dict → TrustRootsError."""
    with pytest.raises(TrustRootsError, match="entry must be a mapping"):
        _validate_entry(0, ["not", "a", "dict"])


# Line 123: entry is a string
def test_validate_entry_string_raises() -> None:
    """Line 123: entry is a string → TrustRootsError."""
    with pytest.raises(TrustRootsError, match="entry must be a mapping"):
        _validate_entry(0, "just a string")


# Line 127: defensive idx not int (unreachable in normal flow, triggered by calling directly)
def test_validate_entry_non_int_idx_raises() -> None:
    """Line 127: idx is not int → defensive TrustRootsError (unreachable in production)."""
    # We bypass enumerate() and call directly with a non-int idx
    # First provide a valid-looking dict so we reach line 125
    der = _make_valid_der()
    b64 = base64.standard_b64encode(der).decode("ascii")
    kid = derive_key_id(der)
    raw_entry = {
        "key_id": kid,
        "public_key_der_b64": b64,
        "valid_from": "2026-01-01T00:00:00Z",
        "valid_until": "2027-01-01T00:00:00Z",
    }
    # idx must be non-int to trigger line 125
    with pytest.raises(TrustRootsError, match="entry index is not int"):
        _validate_entry("not-an-int", raw_entry)  # type: ignore[arg-type]


# Line 139: key_id is not a string
def test_validate_entry_key_id_not_string_raises(tmp_path: Path) -> None:
    """Line 139: key_id is an int, not string → TrustRootsError."""
    der = _make_valid_der()
    b64 = base64.standard_b64encode(der).decode("ascii")
    p = tmp_path / "x.yaml"
    p.write_text(f"""version: 1
keys:
  - key_id: 12345
    public_key_der_b64: "{b64}"
    valid_from: "2026-01-01T00:00:00Z"
    valid_until: "2027-01-01T00:00:00Z"
""")
    with pytest.raises(TrustRootsError, match="must be string"):
        load_trust_roots(p)


# Line 146: public_key_der_b64 not a string
def test_validate_entry_der_b64_not_string_raises(tmp_path: Path) -> None:
    """Line 146: public_key_der_b64 is an int → TrustRootsError 'must be string'."""
    p = tmp_path / "x.yaml"
    p.write_text(f"""version: 1
keys:
  - key_id: "{'0' * 32}"
    public_key_der_b64: 12345
    valid_from: "2026-01-01T00:00:00Z"
    valid_until: "2027-01-01T00:00:00Z"
""")
    with pytest.raises(TrustRootsError, match="must be string"):
        load_trust_roots(p)


# Line 152: base64 decodes to empty bytes
def test_validate_entry_empty_der_after_decode_raises(tmp_path: Path) -> None:
    """Line 152: public_key_der_b64 decodes to empty → TrustRootsError 'empty bytes'."""
    p = tmp_path / "x.yaml"
    # base64("") == ""
    empty_b64 = base64.standard_b64encode(b"").decode("ascii")
    p.write_text(f"""version: 1
keys:
  - key_id: "{'0' * 32}"
    public_key_der_b64: "{empty_b64}"
    valid_from: "2026-01-01T00:00:00Z"
    valid_until: "2027-01-01T00:00:00Z"
""")
    with pytest.raises(TrustRootsError, match="empty bytes"):
        load_trust_roots(p)


# Line 170: provider_id is not a string
def test_validate_entry_provider_id_not_string_raises(tmp_path: Path) -> None:
    """Line 170: provider_id is an int → TrustRootsError 'must be string or absent'."""
    der = _make_valid_der()
    b64 = base64.standard_b64encode(der).decode("ascii")
    kid = derive_key_id(der)
    p = tmp_path / "x.yaml"
    p.write_text(f"""version: 1
keys:
  - key_id: "{kid}"
    public_key_der_b64: "{b64}"
    valid_from: "2026-01-01T00:00:00Z"
    valid_until: "2027-01-01T00:00:00Z"
    provider_id: 999
""")
    with pytest.raises(TrustRootsError, match="must be string or absent"):
        load_trust_roots(p)


# Line 173: label is not a string
def test_validate_entry_label_not_string_raises(tmp_path: Path) -> None:
    """Line 173: label is a list → TrustRootsError 'must be string or absent'."""
    der = _make_valid_der()
    b64 = base64.standard_b64encode(der).decode("ascii")
    kid = derive_key_id(der)
    p = tmp_path / "x.yaml"
    p.write_text(f"""version: 1
keys:
  - key_id: "{kid}"
    public_key_der_b64: "{b64}"
    valid_from: "2026-01-01T00:00:00Z"
    valid_until: "2027-01-01T00:00:00Z"
    label: [not, a, string]
""")
    with pytest.raises(TrustRootsError, match="must be string or absent"):
        load_trust_roots(p)


# =============================================================================
# trust_roots.py: load_trust_roots OSError paths
# =============================================================================


# Lines 201-202: OSError on stat (not FileNotFoundError)
def test_load_trust_roots_stat_oserror(tmp_path: Path) -> None:
    """Lines 201-202: stat() raises generic OSError → TrustRootsError 'cannot stat'."""
    p = tmp_path / "x.yaml"
    p.write_text("version: 1\nkeys: []\n")

    with (
        patch("attestplane.signing.trust_roots.Path.stat", side_effect=OSError("permission denied")),
        pytest.raises(TrustRootsError, match="cannot stat"),
    ):
        load_trust_roots(p)


# Lines 208-209: OSError on read_text
def test_load_trust_roots_read_oserror(tmp_path: Path) -> None:
    """Lines 208-209: read_text() raises OSError → TrustRootsError 'cannot read'."""
    p = tmp_path / "x.yaml"
    p.write_text("version: 1\nkeys: []\n")

    # stat must succeed, but read_text fails
    real_stat = p.stat()
    with (
        patch("attestplane.signing.trust_roots.Path.stat", return_value=real_stat),
        patch("attestplane.signing.trust_roots.Path.read_text", side_effect=OSError("read error")),
        pytest.raises(TrustRootsError, match="cannot read"),
    ):
        load_trust_roots(p)


# =============================================================================
# providers.py: FileKeyProvider OSError on read
# =============================================================================


# Lines 121-122: OSError (not FileNotFoundError) on read_bytes
def test_file_key_provider_read_oserror(tmp_path: Path) -> None:
    """Lines 121-122: read_bytes raises generic OSError → KeyProviderError 'cannot read'."""
    key = Ed25519PrivateKey.generate()
    pem_path = tmp_path / "k.pem"
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pem_path.write_bytes(pem)

    p = FileKeyProvider(pem_path)
    with (
        patch.object(type(pem_path), "read_bytes", side_effect=OSError("read error")),
        pytest.raises(KeyProviderError, match="cannot read"),
    ):
        p.get_signing_material()


# =============================================================================
# providers.py: EnvKeyProvider bad PEM and non-Ed25519
# =============================================================================


# Lines 175-176: EnvKeyProvider invalid PEM → KeyProviderError
def test_env_key_provider_invalid_pem_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lines 175-176: env var set but PEM is invalid → KeyProviderError 'failed to load'."""
    bad_pem = "-----BEGIN PRIVATE KEY-----\nnot real pem\n-----END PRIVATE KEY-----\n"
    monkeypatch.setenv("ATTESTPLANE_TEST_BAD_PEM", bad_pem)
    p = EnvKeyProvider("ATTESTPLANE_TEST_BAD_PEM")
    with pytest.raises(KeyProviderError, match="failed to load"):
        p.get_signing_material()


# Line 178: EnvKeyProvider key is not Ed25519
def test_env_key_provider_rsa_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Line 178: env var contains RSA key → KeyProviderError 'not Ed25519'."""
    from cryptography.hazmat.primitives.asymmetric import rsa

    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_text = rsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    monkeypatch.setenv("ATTESTPLANE_TEST_RSA_KEY", pem_text)

    p = EnvKeyProvider("ATTESTPLANE_TEST_RSA_KEY")
    with pytest.raises(KeyProviderError, match="not Ed25519"):
        p.get_signing_material()


# =============================================================================
# base.py line 296: abstract get_signing_material raises NotImplementedError
# =============================================================================


def test_key_provider_get_signing_material_not_implemented() -> None:
    """Line 296: abstract base get_signing_material raises NotImplementedError."""

    class ConcreteProvider(KeyProvider):
        provider_id = "concrete"
        schema_version = SIGNATURE_SCHEMA_VERSION

        def get_signing_material(self) -> SigningMaterial:
            return super().get_signing_material()  # type: ignore[misc]

    p = ConcreteProvider()
    with pytest.raises(NotImplementedError):
        p.get_signing_material()
