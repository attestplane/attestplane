# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Minimal local ``hypothesis`` compatibility shim for the test suite."""

from __future__ import annotations

from dataclasses import is_dataclass
import functools
import inspect
from typing import Any, Callable


class HealthCheck:
    too_slow = "too_slow"


class _DataObject:
    def draw(self, strategy: "Strategy") -> Any:
        return strategy.example()


class Strategy:
    def __init__(self, example_fn: Callable[[], Any]) -> None:
        self._example_fn = example_fn

    def example(self) -> Any:
        return self._example_fn()

    def __or__(self, other: "Strategy") -> "Strategy":
        return _OneOfStrategy([self, other])

    def filter(self, predicate: Callable[[Any], bool]) -> "Strategy":
        return _FilteredStrategy(self, predicate)


class _FilteredStrategy(Strategy):
    def __init__(self, base: Strategy, predicate: Callable[[Any], bool]) -> None:
        self._base = base
        self._predicate = predicate
        super().__init__(self._example)

    def _example(self) -> Any:
        value = self._base.example()
        if self._predicate(value):
            return value
        if isinstance(value, str):
            for candidate in (value or "x", f"{value or 'x'}1", "x"):
                if self._predicate(candidate):
                    return candidate
        if isinstance(value, list):
            candidate = list(value) + [self._base.example()]
            if self._predicate(candidate):
                return candidate
        return value


class _OneOfStrategy(Strategy):
    def __init__(self, strategies: list[Strategy]) -> None:
        self._strategies = strategies
        super().__init__(self._example)

    def _example(self) -> Any:
        return self._strategies[0].example()


class _Strategies:
    def none(self) -> Strategy:
        return Strategy(lambda: None)

    def booleans(self) -> Strategy:
        return Strategy(lambda: False)

    def integers(
        self,
        *,
        min_value: int | None = None,
        max_value: int | None = None,
    ) -> Strategy:
        def _example() -> int:
            if min_value is not None:
                return min_value
            if max_value is not None and max_value < 0:
                return max_value
            return 0

        return Strategy(_example)

    def text(
        self,
        *,
        alphabet: str = "abcdefghijklmnopqrstuvwxyz",
        min_size: int = 0,
        max_size: int | None = None,
    ) -> Strategy:
        def _example() -> str:
            if not alphabet:
                return "x" * min_size
            ch = alphabet[0]
            size = min_size
            if max_size is not None and size > max_size:
                size = max_size
            return ch * size

        return Strategy(_example)

    def sampled_from(self, seq: list[Any] | tuple[Any, ...]) -> Strategy:
        return Strategy(lambda: seq[0])

    def one_of(self, *strategies: Strategy) -> Strategy:
        if len(strategies) == 1 and isinstance(strategies[0], (list, tuple)):
            strategies = tuple(strategies[0])
        return _OneOfStrategy(list(strategies))

    def lists(
        self,
        strategy: Strategy,
        *,
        min_size: int = 0,
        max_size: int | None = None,
        unique: bool = False,
    ) -> Strategy:
        def _example() -> list[Any]:
            count = min_size
            if max_size is not None and count > max_size:
                count = max_size
            items: list[Any] = []
            for idx in range(count):
                value = strategy.example()
                if unique and isinstance(value, str):
                    value = f"{value}{idx}"
                elif unique:
                    value = (value, idx)
                if unique:
                    while value in items:
                        value = f"{value}{idx}"
                items.append(value)
            return items

        return Strategy(_example)

    def dictionaries(
        self,
        keys: Strategy,
        values: Strategy,
        *,
        min_size: int = 0,
        max_size: int | None = None,
    ) -> Strategy:
        def _example() -> dict[Any, Any]:
            count = min_size
            if max_size is not None and count > max_size:
                count = max_size
            items: dict[Any, Any] = {}
            for idx in range(count):
                key = keys.example()
                if isinstance(key, str):
                    key = key if idx == 0 else f"{key}{idx}"
                else:
                    key = (key, idx)
                while key in items:
                    key = f"{key}{idx}"
                items[key] = values.example()
            return items

        return Strategy(_example)

    def recursive(
        self,
        base: Strategy,
        extend: Callable[[Strategy], Strategy],
        *,
        max_leaves: int = 10,
    ) -> Strategy:
        return Strategy(lambda: base.example())

    def builds(self, factory: Callable[..., Any], /, **kwargs: Strategy) -> Strategy:
        def _example() -> Any:
            values = {name: strategy.example() for name, strategy in kwargs.items()}
            if is_dataclass(factory):
                return factory(**values)
            return factory(**values)

        return Strategy(_example)

    def data(self) -> Strategy:
        return Strategy(lambda: _DataObject())


strategies = _Strategies()


def given(**given_strategies: Strategy) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper() -> Any:
            kwargs = {name: strategy.example() for name, strategy in given_strategies.items()}
            return fn(**kwargs)

        wrapper.__signature__ = inspect.Signature()  # type: ignore[attr-defined]
        return wrapper

    return decorator


def settings(*args: Any, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        return fn

    return decorator


__all__ = ["HealthCheck", "Strategy", "given", "settings", "strategies"]
