# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Deterministic strategy objects used by the local Hypothesis shim."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar, cast

T = TypeVar("T")


@dataclass(frozen=True)
class Strategy(Generic[T]):
    _example: Callable[[], T]

    def example(self) -> T:
        return self._example()

    def __or__(self, other: Strategy[Any]) -> Strategy[Any]:
        return one_of(self, other)

    def __ror__(self, other: Strategy[Any]) -> Strategy[Any]:
        return one_of(other, self)

    def filter(self, predicate: Callable[[T], bool]) -> Strategy[T]:
        def _example() -> T:
            value = self.example()
            if predicate(value):
                return value
            if isinstance(value, str):
                candidate: Any = value or "a"
                for _ in range(10):
                    if predicate(candidate):
                        return cast(T, candidate)
                    candidate += "a"
            raise ValueError("could not satisfy filtered strategy with deterministic example")

        return Strategy(_example)

    def map(self, mapper: Callable[[T], Any]) -> Strategy[Any]:
        def _example() -> Any:
            return mapper(self.example())

        return Strategy(_example)


def none() -> Strategy[None]:
    return Strategy(lambda: None)


def booleans() -> Strategy[bool]:
    return Strategy(lambda: False)


def integers(min_value: int | None = None, max_value: int | None = None) -> Strategy[int]:
    def _example() -> int:
        if min_value is not None:
            return min_value
        if max_value is not None:
            return min(max_value, 0)
        return 0

    return Strategy(_example)


def text(
    alphabet: str | Iterable[str] | None = None,
    *,
    min_size: int = 0,
    max_size: int | None = None,
) -> Strategy[str]:
    def _example() -> str:
        length = max(1, min_size)
        return "a" * length

    return Strategy(_example)


def sampled_from(values: Iterable[T]) -> Strategy[T]:
    items = list(values)
    if not items:
        raise ValueError("sampled_from() requires at least one value")
    return Strategy(lambda: items[0])


def one_of(*strategies: Strategy[T]) -> Strategy[T]:
    if not strategies:
        raise ValueError("one_of() requires at least one strategy")
    def _example() -> T:
        return strategies[0].example()

    return Strategy(_example)


def lists(
    elements: Strategy[T],
    *,
    min_size: int = 0,
    max_size: int | None = None,
    unique: bool = False,
) -> Strategy[list[T]]:
    def _example() -> list[T]:
        size = min_size if min_size > 0 else 1
        if max_size is not None:
            size = min(size, max_size)
        items = [elements.example() for _ in range(size)]
        if unique and len(items) > 1:
            seen: set[Any] = set()
            unique_items: list[Any] = []
            for index, item in enumerate(items):
                candidate: Any = item
                if candidate in seen:
                    if isinstance(candidate, str):
                        candidate = f"{candidate}_{index}"
                    elif isinstance(candidate, int) and not isinstance(candidate, bool):
                        candidate = type(candidate)(candidate + index)
                    else:
                        candidate = index  # type: ignore[assignment]
                seen.add(candidate)
                unique_items.append(candidate)
            items = unique_items
        return items

    return Strategy(_example)


def dictionaries(
    keys: Strategy[str],
    values: Strategy[T],
    *,
    min_size: int = 0,
    max_size: int | None = None,
) -> Strategy[dict[str, T]]:
    def _example() -> dict[str, T]:
        size = min_size if min_size > 0 else 1
        if max_size is not None:
            size = min(size, max_size)
        result: dict[str, Any] = {}
        for index in range(size):
            key = keys.example()
            if key in result:
                key = f"{key}_{index}"
            result[key] = values.example()
        return result

    return Strategy(_example)


def recursive(
    base: Strategy[T],
    extend: Callable[[Strategy[T]], Strategy[T]],
    *,
    max_leaves: int = 1,
) -> Strategy[T]:
    _ = max_leaves
    def _example() -> T:
        return base.example()

    return Strategy(_example)


def builds(cls: Callable[..., T], /, *args: Strategy[Any], **kwargs: Strategy[Any]) -> Strategy[T]:
    def _example() -> T:
        positional = [strategy.example() for strategy in args]
        keyword = {name: strategy.example() for name, strategy in kwargs.items()}
        return cls(*positional, **keyword)

    return Strategy(_example)


def data() -> Strategy[Any]:
    from . import DataObject

    def _example() -> Any:
        return DataObject()

    return Strategy(_example)


__all__ = [
    "Strategy",
    "booleans",
    "builds",
    "data",
    "dictionaries",
    "integers",
    "lists",
    "none",
    "one_of",
    "recursive",
    "sampled_from",
    "text",
]
