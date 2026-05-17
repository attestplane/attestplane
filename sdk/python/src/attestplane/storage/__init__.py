# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Durable storage backends for the substrate.

v1 ships :class:`JsonlStorageBackend` (file-backed JSON Lines). SQLite
and Postgres backends are M6+ deliverables governed by the
anticipated storage-backend ADR.

Public surface:

- :class:`AbstractStorageBackend` — the abstract base; subclass to add
  a backend. Forbidden mutating verbs (``delete``, ``update``,
  ``compact``, …) are rejected at class-creation time.
- :class:`JsonlStorageBackend` — file-backed reference implementation.
- :class:`StorageError` + concrete subclasses.
"""

from attestplane.storage.base import (
    AbstractStorageBackend,
    StorageBoundaryError,
    StorageError,
    StorageReadError,
    StorageWriteError,
)
from attestplane.storage.jsonl import JsonlStorageBackend

__all__ = [
    "AbstractStorageBackend",
    "JsonlStorageBackend",
    "StorageBoundaryError",
    "StorageError",
    "StorageReadError",
    "StorageWriteError",
]
