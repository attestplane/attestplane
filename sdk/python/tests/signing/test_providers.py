# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for :mod:`attestplane.signing.providers` (T2 ticket)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("cryptography")

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from attestplane.signing import (
    EnvKeyProvider,
    FileKeyProvider,
    InMemoryKeyProvider,
    KeyProviderError,
    MultiSignerProvider,
)

# --- InMemoryKeyProvider --------------------------------------------------


def test_in_memory_random_keys_differ() -> None:
    a = InMemoryKeyProvider().get_signing_material()
    b = InMemoryKeyProvider().get_signing_material()
    assert a.public_key_der != b.public_key_der


def test_in_memory_with_seed_is_deterministic() -> None:
    seed = bytes(range(32))
    a = InMemoryKeyProvider(seed=seed).get_signing_material()
    b = InMemoryKeyProvider(seed=seed).get_signing_material()
    assert a.public_key_der == b.public_key_der
    assert a.key_id == b.key_id


def test_in_memory_rejects_short_seed() -> None:
    with pytest.raises(KeyProviderError, match="32 bytes"):
        InMemoryKeyProvider(seed=b"\x00" * 16)


def test_in_memory_rejects_long_seed() -> None:
    with pytest.raises(KeyProviderError, match="32 bytes"):
        InMemoryKeyProvider(seed=b"\x00" * 64)


def test_in_memory_default_provider_id() -> None:
    p = InMemoryKeyProvider()
    assert p.provider_id == "in-memory"


def test_in_memory_custom_provider_id() -> None:
    p = InMemoryKeyProvider(provider_id="in-memory:test-key-A")
    assert p.provider_id == "in-memory:test-key-A"


def test_in_memory_rejects_empty_provider_id() -> None:
    with pytest.raises(ValueError, match="provider_id"):
        InMemoryKeyProvider(provider_id="")


def test_in_memory_repeated_calls_return_same_key() -> None:
    p = InMemoryKeyProvider()
    a = p.get_signing_material()
    b = p.get_signing_material()
    assert a.public_key_der == b.public_key_der


# --- FileKeyProvider ------------------------------------------------------


def _write_unencrypted_pem(key: Ed25519PrivateKey, path: Path) -> None:
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    path.write_bytes(pem)


def _write_encrypted_pem(key: Ed25519PrivateKey, path: Path, passphrase: bytes) -> None:
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(passphrase),
    )
    path.write_bytes(pem)


def test_file_loads_unencrypted_key(tmp_path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    pem_path = tmp_path / "k.pem"
    _write_unencrypted_pem(key, pem_path)

    p = FileKeyProvider(pem_path)
    mat = p.get_signing_material()
    assert mat.public_key_der == key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def test_file_loads_encrypted_key(tmp_path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    pem_path = tmp_path / "k.pem"
    _write_encrypted_pem(key, pem_path, b"secret-pass")

    p = FileKeyProvider(pem_path, passphrase=b"secret-pass")
    mat = p.get_signing_material()
    assert mat is not None


def test_file_wrong_passphrase_raises(tmp_path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    pem_path = tmp_path / "k.pem"
    _write_encrypted_pem(key, pem_path, b"real")

    p = FileKeyProvider(pem_path, passphrase=b"wrong")
    with pytest.raises(KeyProviderError, match="failed to load"):
        p.get_signing_material()


def test_file_missing_path_raises(tmp_path: Path) -> None:
    p = FileKeyProvider(tmp_path / "does-not-exist.pem")
    with pytest.raises(KeyProviderError, match="not found"):
        p.get_signing_material()


def test_file_rejects_non_ed25519(tmp_path: Path) -> None:
    """An RSA key in the file should be rejected (v1 supports Ed25519 only)."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = rsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pem_path = tmp_path / "rsa.pem"
    pem_path.write_bytes(pem)

    p = FileKeyProvider(pem_path)
    with pytest.raises(KeyProviderError, match="not Ed25519"):
        p.get_signing_material()


def test_file_provider_id_defaults_to_path(tmp_path: Path) -> None:
    pem_path = tmp_path / "k.pem"
    _write_unencrypted_pem(Ed25519PrivateKey.generate(), pem_path)
    p = FileKeyProvider(pem_path)
    assert p.provider_id == f"file:{pem_path}"


# --- EnvKeyProvider -------------------------------------------------------


def _pem_text(key: Ed25519PrivateKey) -> str:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")


def test_env_loads_key(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ATTESTPLANE_TEST_KEY", _pem_text(key))
    p = EnvKeyProvider("ATTESTPLANE_TEST_KEY")
    mat = p.get_signing_material()
    assert mat is not None


def test_env_unset_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATTESTPLANE_TEST_KEY_UNSET", raising=False)
    p = EnvKeyProvider("ATTESTPLANE_TEST_KEY_UNSET")
    with pytest.raises(KeyProviderError, match="not set"):
        p.get_signing_material()


def test_env_empty_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATTESTPLANE_TEST_KEY", "   ")
    p = EnvKeyProvider("ATTESTPLANE_TEST_KEY")
    with pytest.raises(KeyProviderError, match="empty"):
        p.get_signing_material()


def test_env_rejects_empty_env_var_name() -> None:
    with pytest.raises(ValueError, match="env_var"):
        EnvKeyProvider("")


def test_env_provider_id_default() -> None:
    p = EnvKeyProvider("ATTESTPLANE_KEY")
    assert p.provider_id == "env:ATTESTPLANE_KEY"


# --- MultiSignerProvider --------------------------------------------------


def test_multi_signer_gathers_all_materials() -> None:
    p1 = InMemoryKeyProvider(provider_id="alpha")
    p2 = InMemoryKeyProvider(provider_id="beta")
    multi = MultiSignerProvider([p1, p2])

    mats = multi.get_signing_materials()
    assert len(mats) == 2
    assert mats[0].key_id != mats[1].key_id


def test_multi_signer_requires_at_least_one() -> None:
    with pytest.raises(ValueError, match="at least one"):
        MultiSignerProvider([])


def test_multi_signer_rejects_duplicate_ids() -> None:
    p1 = InMemoryKeyProvider(provider_id="same")
    p2 = InMemoryKeyProvider(provider_id="same")
    with pytest.raises(ValueError, match="distinct provider_id"):
        MultiSignerProvider([p1, p2])


def test_multi_signer_provider_ids_property() -> None:
    p1 = InMemoryKeyProvider(provider_id="alpha")
    p2 = InMemoryKeyProvider(provider_id="beta")
    multi = MultiSignerProvider([p1, p2])
    assert multi.provider_ids == ("alpha", "beta")


def test_multi_signer_not_a_key_provider() -> None:
    """Type-level distinction: MultiSignerProvider returns N materials, not 1.
    It deliberately does NOT subclass KeyProvider (architect plan § 1 H)."""
    from attestplane.signing import KeyProvider
    assert not issubclass(MultiSignerProvider, KeyProvider)


def test_multi_signer_schema_version_check() -> None:
    """If a future v2 provider is mixed with v1, the composite refuses."""
    class V2Provider(InMemoryKeyProvider):
        schema_version = 2

    p1 = InMemoryKeyProvider(provider_id="ok")
    p2 = V2Provider(provider_id="v2")
    with pytest.raises(ValueError, match="schema_version"):
        MultiSignerProvider([p1, p2])


# --- Concurrency safety ---------------------------------------------------


def test_in_memory_safe_for_concurrent_calls() -> None:
    """KeyProvider implementations MUST be safe for concurrent
    get_signing_material() calls per the architect plan § 1 D
    contract. Smoke test from multiple threads."""
    import threading

    seed = bytes(range(32))
    p = InMemoryKeyProvider(seed=seed)
    results: list[bytes] = []
    lock = threading.Lock()

    def worker() -> None:
        for _ in range(50):
            der = p.get_signing_material().public_key_der
            with lock:
                results.append(der)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All 200 calls return the same key.
    assert len(results) == 200
    assert len(set(results)) == 1
