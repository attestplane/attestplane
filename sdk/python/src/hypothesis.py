# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Minimal offline Hypothesis-compatible shim for the sdk/python tests.

The real Hypothesis package is unavailable in this sandbox, so the property
tests use this deterministic subset instead. It executes each decorated test
once with a valid example derived from the requested strategy tree.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class SearchStrategy(Generic[T]):
    """Deterministic strategy wrapper."""

    def __init__(self, factory: Callable[[], T]) -> None:
        self._factory = factory

    def example(self) -> T:
        return self._factory()

    def filter(self, predicate: Callable[[T], bool]) -> SearchStrategy[T]:
        def _factory() -> T:
            value = self.example()
            if predicate(value):
                return value
            if isinstance(value, str):
                candidate: T = value + "x"  # type: ignore[assignment]
                if predicate(candidate):
                    return candidate
            raise ValueError("hypothesis shim could not satisfy filter predicate")

        return SearchStrategy(_factory)

    def __or__(self, other: SearchStrategy[T]) -> SearchStrategy[T]:
        def _factory() -> T:
            return self.example()

        return SearchStrategy(_factory)


class DataObject:
    """Very small stand-in for ``hypothesis.strategies.data()``."""

    def draw(self, strategy: SearchStrategy[T]) -> T:
        return strategy.example()


class _Strategies:
    @staticmethod
    def none() -> SearchStrategy[Any]:
        return SearchStrategy(lambda: None)

    @staticmethod
    def booleans() -> SearchStrategy[bool]:
        return SearchStrategy(lambda: False)

    @staticmethod
    def integers(*, min_value: int | None = None, max_value: int | None = None) -> SearchStrategy[int]:
        def _factory() -> int:
            if min_value is not None:
                return min_value
            if max_value is not None and max_value < 0:
                return max_value
            return 0

        return SearchStrategy(_factory)

    @staticmethod
    def text(*, alphabet: str = "abc", min_size: int = 0, max_size: int = 10) -> SearchStrategy[str]:
        def _factory() -> str:
            ch = alphabet[0] if alphabet else "a"
            size = max(min_size, 1)
            size = min(size, max_size) if max_size >= 0 else size
            return ch * size

        return SearchStrategy(_factory)

    @staticmethod
    def sampled_from(values: list[Any] | tuple[Any, ...]) -> SearchStrategy[Any]:
        return SearchStrategy(lambda: values[0])

    @staticmethod
    def one_of(*strategies: SearchStrategy[Any]) -> SearchStrategy[Any]:
        def _factory() -> Any:
            return strategies[0].example()

        return SearchStrategy(_factory)

    @staticmethod
    def lists(
        strategy: SearchStrategy[T],
        *,
        min_size: int = 0,
        max_size: int | None = None,
        unique: bool = False,
    ) -> SearchStrategy[list[T]]:
        def _factory() -> list[T]:
            count = max(min_size, 1 if min_size == 0 else min_size)
            if max_size is not None:
                count = min(count, max_size)
            values: list[T] = []
            for index in range(count):
                value = strategy.example()
                if unique and value in values:
                    if isinstance(value, str):
                        value = f"{value}{index}"  # type: ignore[assignment]
                    elif isinstance(value, int) and not isinstance(value, bool):
                        value = type(value)(value + index)  # type: ignore[assignment]
                values.append(value)
            return values

        return SearchStrategy(_factory)

    @staticmethod
    def dictionaries(
        keys: SearchStrategy[str],
        values: SearchStrategy[Any],
        *,
        max_size: int | None = None,
    ) -> SearchStrategy[dict[str, Any]]:
        def _factory() -> dict[str, Any]:
            count = 1 if max_size is None else min(1, max_size)
            result: dict[str, Any] = {}
            for index in range(count):
                key = keys.example()
                if key in result:
                    key = f"{key}{index}"
                result[key] = values.example()
            return result

        return SearchStrategy(_factory)

    @staticmethod
    def builds(constructor: Callable[..., T], /, **kwargs: Any) -> SearchStrategy[T]:
        def _factory() -> T:
            built_kwargs = {
                key: value.example() if isinstance(value, SearchStrategy) else value
                for key, value in kwargs.items()
            }
            return constructor(**built_kwargs)

        return SearchStrategy(_factory)

    @staticmethod
    def recursive(
        base: SearchStrategy[T],
        extend: Callable[[SearchStrategy[T]], SearchStrategy[T]],
        *,
        max_leaves: int = 1,
    ) -> SearchStrategy[T]:
        def _factory() -> T:
            return base.example()

        return SearchStrategy(_factory)

    @staticmethod
    def data() -> SearchStrategy[DataObject]:
        return SearchStrategy(DataObject)


strategies = _Strategies()


class HealthCheck:
    too_slow = "too_slow"


def settings(*args: Any, **kwargs: Any) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        return fn

    return decorator


def given(*given_args: Any, **given_kwargs: Any) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            positional = [arg.example() if isinstance(arg, SearchStrategy) else arg for arg in given_args]
            keyword = {
                key: value.example() if isinstance(value, SearchStrategy) else value
                for key, value in given_kwargs.items()
            }
            return fn(*args, *positional, **kwargs, **keyword)

        wrapper.__signature__ = inspect.Signature()  # type: ignore[attr-defined]
        return wrapper

    return decorator


__all__ = [
    "DataObject",
    "HealthCheck",
    "SearchStrategy",
    "given",
    "settings",
    "strategies",
]
