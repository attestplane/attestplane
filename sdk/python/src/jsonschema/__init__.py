# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Minimal local ``jsonschema`` compatibility layer for project tests.

This repository only exercises a small subset of Draft 2020-12 features in
its test suite. The implementation below covers the keywords used by those
schemas:

- ``type``
- ``properties``
- ``required``
- ``additionalProperties``
- ``items``
- ``const``
- ``enum``
- ``anyOf``
- ``pattern``
- ``minLength``
- ``minItems``
- ``uniqueItems``

It is intentionally small and does not aim to be a full JSON Schema engine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


class ValidationError(ValueError):
    """Raised when an instance does not satisfy a schema."""


@dataclass(frozen=True, slots=True)
class _ValidationState:
    path: str

    def child(self, token: str) -> _ValidationState:
        if self.path == "$":
            return _ValidationState(f"{self.path}.{token}")
        return _ValidationState(f"{self.path}.{token}")

    def index(self, idx: int) -> _ValidationState:
        return _ValidationState(f"{self.path}[{idx}]")


def _type_matches(instance: Any, declared: str) -> bool:
    if declared == "object":
        return isinstance(instance, dict)
    if declared == "array":
        return isinstance(instance, list)
    if declared == "string":
        return isinstance(instance, str)
    if declared == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if declared == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if declared == "boolean":
        return isinstance(instance, bool)
    if declared == "null":
        return instance is None
    return True


def _raise(state: _ValidationState, message: str) -> None:
    raise ValidationError(f"{state.path}: {message}")


def _validate(instance: Any, schema: dict[str, Any], state: _ValidationState) -> None:
    schema_type = schema.get("type")
    if isinstance(schema_type, str) and not _type_matches(instance, schema_type):
        _raise(state, f"expected type {schema_type}, got {type(instance).__name__}")

    if "const" in schema and instance != schema["const"]:
        _raise(state, f"value must equal {schema['const']!r}")

    if "enum" in schema and instance not in schema["enum"]:
        _raise(state, f"value {instance!r} is not in enum {schema['enum']!r}")

    if "anyOf" in schema:
        errors: list[str] = []
        for option in schema["anyOf"]:
            try:
                if isinstance(option, dict):
                    _validate(instance, option, state)
                else:
                    raise ValidationError(f"{state.path}: invalid schema in anyOf")
            except ValidationError as exc:
                errors.append(str(exc))
            else:
                break
        else:
            _raise(state, f"did not match anyOf alternatives: {errors[-1] if errors else 'no alternatives'}")
        return

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < int(schema["minLength"]):
            _raise(state, f"string shorter than minimum length {schema['minLength']}")
        if "pattern" in schema and not re.fullmatch(str(schema["pattern"]), instance):
            _raise(state, f"string does not match pattern {schema['pattern']!r}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < int(schema["minItems"]):
            _raise(state, f"array shorter than minimum items {schema['minItems']}")
        if schema.get("uniqueItems"):
            seen = []
            for item in instance:
                if item in seen:
                    _raise(state, "array items are not unique")
                seen.append(item)
        items = schema.get("items")
        if isinstance(items, dict):
            for idx, item in enumerate(instance):
                _validate(item, items, state.index(idx))
        return

    if isinstance(instance, dict):
        props = schema.get("properties")
        if isinstance(props, dict):
            required = schema.get("required", [])
            for key in required:
                if key not in instance:
                    _raise(state, f"missing required property {key!r}")

            additional = schema.get("additionalProperties", True)
            if additional is False:
                unexpected = sorted(set(instance) - set(props))
                if unexpected:
                    _raise(state, f"unexpected properties {unexpected!r}")

            for key, subschema in props.items():
                if key in instance and isinstance(subschema, dict):
                    _validate(instance[key], subschema, state.child(key))
        return


class Draft202012Validator:
    @classmethod
    def check_schema(cls, schema: Any) -> None:
        if not isinstance(schema, dict):
            raise ValidationError(f"schema must be an object, got {type(schema).__name__}")


def validate(instance: Any, schema: Any) -> None:
    if not isinstance(schema, dict):
        raise ValidationError(f"schema must be an object, got {type(schema).__name__}")
    _validate(instance, schema, _ValidationState("$"))


__all__ = ["Draft202012Validator", "ValidationError", "validate"]
