# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""TrustRoots YAML loader — T4 of the ADR-0005 plan per the
:doc:`T3+T4 architect review </architecture/adr_0005_t3_t4_review_20260517>` § 1 decision 9.

Strict YAML schema, ``yaml.safe_load`` only, 1 MB file size cap,
explicit-path-required (no environment-variable defaults per
:doc:`/architecture/adr_0005_signing_plan_20260517` § 5 R4).

Schema::

    version: 1
    keys:
      - key_id: "<32 lowercase hex chars>"
        public_key_der_b64: "<base64 SPKI>"
        valid_from: "2026-05-17T00:00:00Z"
        valid_until: "2027-05-17T00:00:00Z"
        provider_id: "<optional informational>"
        label: "<optional informational>"

Validation invariants:

- ``version`` MUST equal ``1`` (locked v1 schema).
- ``keys`` MUST be a non-empty list.
- Each entry's ``key_id`` MUST equal ``derive_key_id(b64decode(public_key_der_b64))``.
- ``valid_from`` < ``valid_until``.
- Both datetimes MUST be UTC-aware (Z suffix or explicit offset).
- ``additionalProperties`` strictly rejected: top-level and per-entry.
- File size > 1 MB rejected (DoS mitigation).
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

# PyYAML is imported lazily inside `load_trust_roots()` so that callers who only
# need the `TrustRoots` / `TrustRootEntry` dataclasses (e.g., constructed from an
# in-memory list) can import this module without the `[signing]` extras
# installed. The CI base environment does not install [signing]; previously the
# unconditional top-level `import yaml` caused
# `attestplane.signing.__init__` to crash on collection.
from attestplane.signing.base import (
    SigningError,
    derive_key_id,
)

_MAX_FILE_SIZE_BYTES: Final[int] = 1 * 1024 * 1024  # 1 MB
_REQUIRED_ENTRY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "key_id",
        "public_key_der_b64",
        "valid_from",
        "valid_until",
    }
)
_OPTIONAL_ENTRY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "provider_id",
        "label",
    }
)
_REQUIRED_TOP_KEYS: Final[frozenset[str]] = frozenset({"version", "keys"})


class TrustRootsError(SigningError):
    """A TrustRoots YAML file failed validation."""


@dataclass(frozen=True, slots=True)
class TrustRootEntry:
    """One trusted signing key with validity window."""

    key_id: str
    public_key_der: bytes
    valid_from: datetime
    valid_until: datetime
    provider_id: str | None
    label: str | None


@dataclass(frozen=True, slots=True)
class TrustRoots:
    """The full set of trusted keys + their validity windows."""

    version: int
    entries: tuple[TrustRootEntry, ...]

    def lookup(self, key_id: str) -> TrustRootEntry | None:
        """Return the entry matching ``key_id`` or ``None``."""
        for e in self.entries:
            if e.key_id == key_id:
                return e
        return None


def _parse_datetime(raw: object, field_name: str) -> datetime:
    """Parse an ISO 8601 UTC datetime; reject naive or non-UTC."""
    if isinstance(raw, datetime):
        dt = raw
    elif isinstance(raw, str):
        # Normalise trailing Z to +00:00 for fromisoformat.
        normalized = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
        try:
            dt = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise TrustRootsError(f"{field_name}: not valid ISO 8601: {raw!r} ({exc})") from exc
    else:
        raise TrustRootsError(f"{field_name}: must be string or datetime, got {type(raw).__name__}")
    if dt.tzinfo is None:
        raise TrustRootsError(f"{field_name}: must be UTC-aware (use 'Z' or '+00:00' suffix)")
    if dt.utcoffset() != UTC.utcoffset(None):
        raise TrustRootsError(f"{field_name}: must be UTC (got offset {dt.utcoffset()})")
    return dt


def _validate_entry(idx: int, raw: object) -> TrustRootEntry:
    if not isinstance(raw, dict):
        raise TrustRootsError(f"keys[{idx}]: entry must be a mapping, got {type(raw).__name__}")
    keys_present = set(raw.keys())
    if not isinstance(idx, int):
        # Defensive — should never happen
        raise TrustRootsError(f"internal: entry index is not int: {idx!r}")

    missing = _REQUIRED_ENTRY_KEYS - keys_present
    if missing:
        raise TrustRootsError(f"keys[{idx}]: missing required fields {sorted(missing)}")
    allowed = _REQUIRED_ENTRY_KEYS | _OPTIONAL_ENTRY_KEYS
    unexpected = keys_present - allowed
    if unexpected:
        raise TrustRootsError(f"keys[{idx}]: unexpected fields {sorted(unexpected)} (allowed: {sorted(allowed)})")

    key_id_raw = raw["key_id"]
    if not isinstance(key_id_raw, str):
        raise TrustRootsError(f"keys[{idx}].key_id: must be string, got {type(key_id_raw).__name__}")
    key_id = key_id_raw.lower()
    if len(key_id) != 32 or any(c not in "0123456789abcdef" for c in key_id):
        raise TrustRootsError(f"keys[{idx}].key_id: must be 32 lowercase hex chars, got {key_id_raw!r}")

    der_b64_raw = raw["public_key_der_b64"]
    if not isinstance(der_b64_raw, str):
        raise TrustRootsError(f"keys[{idx}].public_key_der_b64: must be string")
    try:
        public_key_der = base64.b64decode(der_b64_raw, validate=True)
    except Exception as exc:
        raise TrustRootsError(f"keys[{idx}].public_key_der_b64: invalid base64: {exc}") from exc
    if not public_key_der:
        raise TrustRootsError(f"keys[{idx}].public_key_der_b64: decoded to empty bytes")

    derived = derive_key_id(public_key_der)
    if derived != key_id:
        raise TrustRootsError(
            f"keys[{idx}].key_id ({key_id}) does not match derive_key_id() of public_key_der_b64 ({derived})"
        )

    valid_from = _parse_datetime(raw["valid_from"], f"keys[{idx}].valid_from")
    valid_until = _parse_datetime(raw["valid_until"], f"keys[{idx}].valid_until")
    if not valid_from < valid_until:
        raise TrustRootsError(
            f"keys[{idx}]: valid_from ({valid_from.isoformat()}) must be "
            f"strictly before valid_until ({valid_until.isoformat()})"
        )

    provider_id = raw.get("provider_id")
    if provider_id is not None and not isinstance(provider_id, str):
        raise TrustRootsError(f"keys[{idx}].provider_id: must be string or absent")
    label = raw.get("label")
    if label is not None and not isinstance(label, str):
        raise TrustRootsError(f"keys[{idx}].label: must be string or absent")

    return TrustRootEntry(
        key_id=key_id,
        public_key_der=public_key_der,
        valid_from=valid_from,
        valid_until=valid_until,
        provider_id=provider_id,
        label=label,
    )


def load_trust_roots(path: str | os.PathLike[str]) -> TrustRoots:
    """Load + validate a TrustRoots YAML file.

    Locked behaviour per architect review § 1 decision 9:

    - ``yaml.safe_load`` only (never ``yaml.load`` / ``yaml.unsafe_load``).
    - Path must be explicit; no environment-variable default.
    - File size cap 1 MB.
    - Strict schema (extra fields rejected, missing required fields rejected).
    - Every entry's ``key_id`` cross-checked against derived hash.
    """
    p = Path(path)
    try:
        size = p.stat().st_size
    except FileNotFoundError as exc:
        raise TrustRootsError(f"TrustRoots file not found: {p}") from exc
    except OSError as exc:
        raise TrustRootsError(f"cannot stat TrustRoots file {p}: {exc}") from exc
    if size > _MAX_FILE_SIZE_BYTES:
        raise TrustRootsError(f"TrustRoots file {p} exceeds 1 MB cap (got {size} bytes)")

    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise TrustRootsError(f"cannot read TrustRoots file {p}: {exc}") from exc

    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "attestplane.signing.trust_roots.load_trust_roots() requires the "
            "'signing' extras with PyYAML. Install with: pip install "
            "attestplane[signing]"
        ) from exc

    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise TrustRootsError(f"TrustRoots {p}: YAML parse failed: {exc}") from exc

    if not isinstance(raw, dict):
        raise TrustRootsError(f"TrustRoots {p}: top-level must be a mapping, got {type(raw).__name__}")

    keys_present = set(raw.keys())
    missing = _REQUIRED_TOP_KEYS - keys_present
    if missing:
        raise TrustRootsError(f"TrustRoots {p}: missing required top-level fields {sorted(missing)}")
    unexpected = keys_present - _REQUIRED_TOP_KEYS
    if unexpected:
        raise TrustRootsError(f"TrustRoots {p}: unexpected top-level fields {sorted(unexpected)}")

    version = raw["version"]
    if version != 1:
        raise TrustRootsError(f"TrustRoots {p}: version must be 1 (v1 schema), got {version!r}")

    keys_raw = raw["keys"]
    if not isinstance(keys_raw, list):
        raise TrustRootsError(f"TrustRoots {p}: 'keys' must be a list, got {type(keys_raw).__name__}")
    if not keys_raw:
        raise TrustRootsError(f"TrustRoots {p}: 'keys' must contain at least one entry")

    entries = tuple(_validate_entry(i, e) for i, e in enumerate(keys_raw))
    seen_ids: set[str] = set()
    for entry in entries:
        if entry.key_id in seen_ids:
            raise TrustRootsError(f"TrustRoots {p}: duplicate key_id {entry.key_id!r}")
        seen_ids.add(entry.key_id)

    return TrustRoots(version=version, entries=entries)


__all__ = [
    "TrustRootEntry",
    "TrustRoots",
    "TrustRootsError",
    "load_trust_roots",
]
