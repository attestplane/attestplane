# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Minimal local `jsonschema` compatibility layer for offline test runs.

This repository's test suite only needs a narrow subset of Draft 2020-12
validation. The real third-party package is preferred when available, but the
CI image used for this task does not ship it and cannot fetch it from the
network. This module covers the keywords exercised by the checked-in schemas
and tests:

- ``type``
- ``const``
- ``enum``
- ``pattern``
- ``minimum``
- ``minLength``
- ``minItems`` / ``maxItems``
- ``uniqueItems``
- ``required``
- ``properties``
- ``additionalProperties``
- ``items``
- ``anyOf``

It is intentionally small and strict enough for the repository's schema
fixtures, but it is not a drop-in replacement for the upstream package.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


class ValidationError(ValueError):
    """Raised when an instance does not satisfy the supplied schema."""


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze(inner)) for key, inner in value.items()))
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _type_matches(instance: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "null":
        return instance is None
    raise ValidationError(f"unsupported schema type {expected!r}")


def _validate(instance: Any, schema: Any, path: str = "$") -> None:
    if not isinstance(schema, dict):
        raise ValidationError(f"{path}: schema must be a JSON object")

    if "anyOf" in schema:
        for subschema in schema["anyOf"]:
            try:
                _validate(instance, subschema, path=path)
                break
            except ValidationError:
                continue
        else:
            raise ValidationError(f"{path}: did not match anyOf alternatives")

    if "const" in schema and instance != schema["const"]:
        raise ValidationError(f"{path}: value {instance!r} does not equal const {schema['const']!r}")

    if "enum" in schema and instance not in schema["enum"]:
        raise ValidationError(f"{path}: value {instance!r} not in enum {schema['enum']!r}")

    schema_type = schema.get("type")
    if schema_type is not None:
        expected_types = [schema_type] if isinstance(schema_type, str) else list(schema_type)
        if not any(_type_matches(instance, expected) for expected in expected_types):
            raise ValidationError(f"{path}: expected type {schema_type!r}, got {type(instance).__name__}")

    if isinstance(instance, str):
        min_length = schema.get("minLength")
        if min_length is not None and len(instance) < int(min_length):
            raise ValidationError(f"{path}: string shorter than minLength {min_length}")
        pattern = schema.get("pattern")
        if pattern is not None and re.search(pattern, instance) is None:
            raise ValidationError(f"{path}: string {instance!r} does not match pattern {pattern!r}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        minimum = schema.get("minimum")
        if minimum is not None and instance < minimum:
            raise ValidationError(f"{path}: value {instance!r} is below minimum {minimum!r}")

    if isinstance(instance, list):
        min_items = schema.get("minItems")
        if min_items is not None and len(instance) < int(min_items):
            raise ValidationError(f"{path}: array shorter than minItems {min_items}")
        max_items = schema.get("maxItems")
        if max_items is not None and len(instance) > int(max_items):
            raise ValidationError(f"{path}: array longer than maxItems {max_items}")
        if schema.get("uniqueItems"):
            frozen = [_freeze(item) for item in instance]
            if len(set(frozen)) != len(frozen):
                raise ValidationError(f"{path}: array items are not unique")
        items = schema.get("items")
        if items is not None:
            if isinstance(items, list):
                for index, (item, subschema) in enumerate(zip(instance, items, strict=False)):
                    _validate(item, subschema, path=f"{path}[{index}]")
            else:
                for index, item in enumerate(instance):
                    _validate(item, items, path=f"{path}[{index}]")

    if isinstance(instance, dict):
        required = schema.get("required", [])
        missing = [field for field in required if field not in instance]
        if missing:
            raise ValidationError(f"{path}: missing required field(s) {missing}")
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise ValidationError(f"{path}: properties must be an object")
        for key, subschema in properties.items():
            if key in instance:
                _validate(instance[key], subschema, path=f"{path}.{key}")
        additional = schema.get("additionalProperties", True)
        extras = [key for key in instance if key not in properties]
        if additional is False and extras:
            raise ValidationError(f"{path}: additional properties not allowed: {extras}")
        if isinstance(additional, dict):
            for key in extras:
                _validate(instance[key], additional, path=f"{path}.{key}")


def validate(instance: Any, schema: Any) -> None:
    """Validate *instance* against *schema*.

    Mirrors :func:`jsonschema.validate` enough for this repository's tests.
    """

    _validate(instance, schema)


@dataclass
class _Draft202012Validator:
    schema: Any = None

    @staticmethod
    def check_schema(schema: Any) -> None:
        if not isinstance(schema, dict):
            raise ValidationError("schema must be a JSON object")

    def validate(self, instance: Any) -> None:
        validate(instance, self.schema)


Draft202012Validator = _Draft202012Validator
