# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Runtime adapters — the only adapter surface that ships in the substrate.

Per ADR-0004 § 4, the Attestplane OSS tree contains exactly one adapter
surface: the abstract :class:`GenericRuntimeAdapter` base class. Concrete
adapters (AIOS, LangGraph, Claude Code SDK, CrewAI, etc.) live outside this
tree — in the respective execution-plane repository or in
``attestplane-contrib``.

The lone exception is :mod:`attestplane.adapters.aios_spec`, which is a
docstring-only stub that documents the contract an AIOS adapter must satisfy.
It contains no executable code.
"""

from attestplane.adapters.base import (
    AdapterError,
    AdapterTranslationError,
    GenericRuntimeAdapter,
    RuntimeEvent,
)

__all__ = [
    "AdapterError",
    "AdapterTranslationError",
    "GenericRuntimeAdapter",
    "RuntimeEvent",
]
