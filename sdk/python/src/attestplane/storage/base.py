# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Abstract storage-backend base.

The substrate's in-memory :class:`~attestplane.substrate.AttestSubstrate`
is the reference implementation. For deployments that need durability,
callers persist appended events through a
:class:`AbstractStorageBackend` implementation.

v1 ships one concrete backend: :class:`~attestplane.storage.jsonl.JsonlStorageBackend`.

The interface intentionally exposes only four verbs:

- :meth:`AbstractStorageBackend.append` — persist one chained event
- :meth:`AbstractStorageBackend.read_all` — return the persisted chain
- :meth:`AbstractStorageBackend.head` — return the current head (without
  reading the full chain)
- :meth:`AbstractStorageBackend.close` — release resources

There is no ``delete``, no ``update``, no ``rewrite``. The substrate is
append-only by design (ADR-0002 § immutability invariant), and a storage
backend that can delete events would defeat the chain's tamper-evidence.
This is a real boundary: any subclass that adds a public mutating verb
is a substrate-level boundary violation and the PR introducing it must
be rejected. The check mirrors :class:`~attestplane.adapters.GenericRuntimeAdapter`'s
forbidden-method gate (ADR-0004 § 1).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from attestplane.types import ChainedEvent, ChainHead


class StorageError(Exception):
    """Base class for storage-backend errors."""


class StorageReadError(StorageError):
    """Raised when reading from durable storage fails or yields a corrupt chain."""


class StorageWriteError(StorageError):
    """Raised when persisting an event fails (permissions, disk full, fsync, ...)."""


class StorageBoundaryError(TypeError):
    """Raised when a subclass defines a forbidden mutating verb at the public level."""


class AbstractStorageBackend(ABC):
    """Abstract base for any durable backend behind ``AttestSubstrate``.

    Concrete subclasses persist :class:`~attestplane.types.ChainedEvent`
    values produced by :func:`~attestplane.hashchain.chain_extend`. The
    substrate is responsible for hash-chain correctness; the backend is
    responsible only for durably persisting the bytes it is handed and
    returning them in seq order on read.

    Concurrency: implementations declare their concurrency contract in
    docstrings. The JSONL reference implementation is process-local and
    serializes appends through a lock; multi-writer backends (M6+) will
    document optimistic-concurrency semantics via the
    :class:`~attestplane.types.ChainHead` compare-and-swap contract.

    Forbidden subclass surface (rejected at class-creation time):

    - ``delete``, ``remove``, ``purge``, ``truncate``
    - ``update``, ``mutate``, ``rewrite``, ``overwrite``
    - ``compact`` (a compaction backend would re-order or re-hash; that
      belongs in a separate ADR, not at the storage abstraction layer)
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        forbidden = {
            "delete",
            "remove",
            "purge",
            "truncate",
            "update",
            "mutate",
            "rewrite",
            "overwrite",
            "compact",
        }
        offenders = sorted(name for name in vars(cls) if not name.startswith("_") and name in forbidden)
        if offenders:
            raise StorageBoundaryError(
                f"{cls.__name__} defines forbidden mutating method(s) {offenders}; "
                f"storage backends are append-only. See ADR-0002 § immutability."
            )

    @abstractmethod
    def append(self, event: ChainedEvent) -> None:
        """Durably persist one chained event.

        MUST be atomic: either the event is durable on return, or this
        method raises :class:`StorageWriteError` and the storage state is
        unchanged. Partial writes are not permitted.

        SHOULD fsync (or equivalent durability primitive) before
        returning, unless the implementation documents weaker semantics.
        """
        raise NotImplementedError

    @abstractmethod
    def read_all(self) -> list[ChainedEvent]:
        """Return the persisted chain in ``seq`` order.

        MAY raise :class:`StorageReadError` if the stored bytes are
        unreadable or fail integrity checks. MUST NOT silently truncate
        a corrupted chain to the last good event — the verifier sees the
        truncation and the chain integrity claim becomes ambiguous.
        """
        raise NotImplementedError

    @abstractmethod
    def head(self) -> ChainHead:
        """Return the current chain head.

        MAY be implemented as a tail read for backends that store a
        head pointer separately; otherwise it is equivalent to
        ``head_of(self.read_all())``.
        """
        raise NotImplementedError

    def close(self) -> None:
        """Release backend resources.

        Default is a no-op; backends with open file handles, network
        connections, or background workers MUST override.
        """
        return

    def __enter__(self) -> AbstractStorageBackend:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
