# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Minimal local ``jsonschema`` compatibility shim for the test suite.

The repository's tests only need a small subset of JSON Schema features:
``type``, ``const``, ``enum``, ``anyOf``, ``required``, ``properties``,
``items``, ``additionalProperties``, ``pattern``, ``minLength``,
``minItems``, ``minimum``, ``maximum``, and ``uniqueItems``.

This shim keeps the test environment self-contained when the third-party
package is unavailable. It is intentionally narrow and only implements the
behaviour exercised by the checked-in schemas and tests.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any


class ValidationError(ValueError):
    """Raised when an instance does not satisfy a schema."""


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _type_matches(instance: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "integer":
        return _is_integer(instance)
    if expected == "number":
        return (isinstance(instance, (int, float)) and not isinstance(instance, bool))
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "null":
        return instance is None
    raise ValidationError(f"unsupported schema type: {expected!r}")


def _validate(instance: Any, schema: dict[str, Any], path: str) -> None:
    if not isinstance(schema, dict):
        raise ValidationError(f"{path}: schema must be an object")

    if "anyOf" in schema:
        errors: list[ValidationError] = []
        for subschema in schema["anyOf"]:
            try:
                _validate(instance, subschema, path)
                break
            except ValidationError as exc:
                errors.append(exc)
        else:
            raise ValidationError(
                f"{path}: does not match any allowed schema"
                + (f" ({errors[-1]})" if errors else "")
            )
        return

    if "type" in schema:
        expected = schema["type"]
        if isinstance(expected, list):
            if not any(_type_matches(instance, item) for item in expected):
                raise ValidationError(f"{path}: expected one of {expected!r}, got {type(instance).__name__}")
        else:
            if not _type_matches(instance, expected):
                raise ValidationError(f"{path}: expected {expected!r}, got {type(instance).__name__}")

    if "const" in schema and instance != schema["const"]:
        raise ValidationError(f"{path}: expected constant {schema['const']!r}, got {instance!r}")

    if "enum" in schema and instance not in schema["enum"]:
        raise ValidationError(f"{path}: value {instance!r} is not in enum {schema['enum']!r}")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            raise ValidationError(f"{path}: string shorter than {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            raise ValidationError(f"{path}: string longer than {schema['maxLength']}")
        if "pattern" in schema and re.fullmatch(schema["pattern"], instance) is None:
            raise ValidationError(f"{path}: string does not match pattern {schema['pattern']!r}")

    if _is_integer(instance):
        if "minimum" in schema and instance < schema["minimum"]:
            raise ValidationError(f"{path}: integer smaller than {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            raise ValidationError(f"{path}: integer larger than {schema['maximum']}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise ValidationError(f"{path}: array shorter than {schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            raise ValidationError(f"{path}: array longer than {schema['maxItems']}")
        if schema.get("uniqueItems"):
            seen: set[str] = set()
            for item in instance:
                marker = repr(item)
                if marker in seen:
                    raise ValidationError(f"{path}: array items are not unique")
                seen.add(marker)
        if "items" in schema:
            for index, item in enumerate(instance):
                _validate(item, schema["items"], f"{path}/{index}")

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                raise ValidationError(f"{path}: missing required property {key!r}")

        properties = schema.get("properties", {})
        for key, subschema in properties.items():
            if key in instance:
                _validate(instance[key], subschema, f"{path}/{key}")

        additional = schema.get("additionalProperties", True)
        if additional is False:
            extra_keys = [key for key in instance if key not in properties]
            if extra_keys:
                raise ValidationError(f"{path}: additional properties are not allowed: {extra_keys!r}")
        elif isinstance(additional, dict):
            for key in instance:
                if key not in properties:
                    _validate(instance[key], additional, f"{path}/{key}")


class Draft202012Validator:
    """Tiny validator wrapper matching the test-suite API surface."""

    @staticmethod
    def check_schema(schema: dict[str, Any]) -> None:
        if not isinstance(schema, dict):
            raise ValidationError("schema must be a JSON object")


def validate(instance: Any, schema: dict[str, Any]) -> None:
    _validate(instance, schema, "$")


__all__ = ["Draft202012Validator", "ValidationError", "validate"]
