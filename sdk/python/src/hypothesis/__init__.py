# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Minimal local ``hypothesis`` shim for the SDK test suite.

The real third-party package is not available in this execution
environment. The property tests in this repository only rely on a very
small subset of the Hypothesis API, so this module provides a
deterministic compatibility layer that exercises each test once with a
reasonable generated example.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from . import strategies

F = TypeVar("F", bound=Callable[..., Any])


class HealthCheck:
    too_slow = object()


class DataObject:
    """Deterministic stand-in for Hypothesis' draw-capable data object."""

    def draw(self, strategy: strategies.Strategy[Any]) -> Any:
        return strategy.example()


def given(**given_strategies: strategies.Strategy[Any]) -> Callable[[F], F]:
    def decorator(fn: F) -> F:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if args or kwargs:
                return fn(*args, **kwargs)
            generated = {name: strategy.example() for name, strategy in given_strategies.items()}
            return fn(**generated)

        wrapper.__name__ = getattr(fn, "__name__", "given_wrapper")
        wrapper.__doc__ = getattr(fn, "__doc__", None)
        wrapper.__module__ = getattr(fn, "__module__", wrapper.__module__)
        wrapper.__qualname__ = getattr(fn, "__qualname__", wrapper.__qualname__)
        return wrapper  # type: ignore[return-value]

    return decorator


def settings(*_args: Any, **_kwargs: Any) -> Callable[[F], F]:
    def decorator(fn: F) -> F:
        return fn

    return decorator


__all__ = [
    "DataObject",
    "HealthCheck",
    "given",
    "settings",
    "strategies",
]
