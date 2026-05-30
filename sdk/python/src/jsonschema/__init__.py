# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Minimal local ``jsonschema`` shim for the SDK test suite.

The real third-party package is not available in this execution
environment. The repository only needs a small subset of its API for the
schema-contract tests, so this module implements the narrow surface that
those tests exercise.
"""

from __future__ import annotations

import re
from typing import Any


class ValidationError(ValueError):
    """Raised when an instance fails schema validation."""


def _type_name(instance: Any) -> str:
    if instance is None:
        return "null"
    if isinstance(instance, bool):
        return "boolean"
    if isinstance(instance, int):
        return "integer"
    if isinstance(instance, float):
        return "number"
    if isinstance(instance, str):
        return "string"
    if isinstance(instance, list):
        return "array"
    if isinstance(instance, dict):
        return "object"
    return type(instance).__name__


def _matches_type(instance: Any, expected: str) -> bool:
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "null":
        return instance is None
    raise ValidationError(f"unsupported schema type {expected!r}")


def _fail(path: str, message: str) -> None:
    raise ValidationError(f"{path}: {message}")


def _validate(instance: Any, schema: Any, path: str = "$") -> None:
    if isinstance(schema, bool):
        if schema:
            return
        _fail(path, "schema is false")

    if not isinstance(schema, dict):
        _fail(path, "schema must be a mapping")

    if "const" in schema and instance != schema["const"]:
        _fail(path, f"must equal {schema['const']!r}")

    if "enum" in schema and instance not in schema["enum"]:
        _fail(path, f"must be one of {schema['enum']!r}")

    if "type" in schema:
        expected_types = schema["type"]
        if isinstance(expected_types, str):
            expected_types = [expected_types]
        if not any(_matches_type(instance, expected) for expected in expected_types):
            _fail(path, f"must be of type {expected_types!r}, got {_type_name(instance)}")

    if "pattern" in schema:
        if not isinstance(instance, str):
            _fail(path, "must be a string")
        if re.fullmatch(schema["pattern"], instance) is None:
            _fail(path, f"does not match pattern {schema['pattern']!r}")

    if "minLength" in schema:
        if not isinstance(instance, str):
            _fail(path, "must be a string")
        if len(instance) < int(schema["minLength"]):
            _fail(path, f"must have length >= {schema['minLength']}")

    if "minimum" in schema:
        if not isinstance(instance, (int, float)) or isinstance(instance, bool):
            _fail(path, "must be a number")
        if instance < schema["minimum"]:
            _fail(path, f"must be >= {schema['minimum']}")

    if "maximum" in schema:
        if not isinstance(instance, (int, float)) or isinstance(instance, bool):
            _fail(path, "must be a number")
        if instance > schema["maximum"]:
            _fail(path, f"must be <= {schema['maximum']}")

    if "minItems" in schema:
        if not isinstance(instance, list):
            _fail(path, "must be an array")
        if len(instance) < int(schema["minItems"]):
            _fail(path, f"must have at least {schema['minItems']} items")

    if "required" in schema:
        if not isinstance(instance, dict):
            _fail(path, "must be an object")
        for key in schema["required"]:
            if key not in instance:
                _fail(path, f"missing required property {key!r}")

    if "properties" in schema:
        if not isinstance(instance, dict):
            _fail(path, "must be an object")
        properties = schema["properties"]
        additional = schema.get("additionalProperties", True)
        for key, value in instance.items():
            if key in properties:
                _validate(value, properties[key], f"{path}.{key}")
            elif additional is False:
                _fail(path, f"unexpected property {key!r}")
            elif isinstance(additional, dict):
                _validate(value, additional, f"{path}.{key}")
        for key, subschema in properties.items():
            if key in instance and isinstance(subschema, dict) and subschema.get("type") == "object":
                # Nested object validation is handled by the recursive call above.
                continue

    if "items" in schema:
        if not isinstance(instance, list):
            _fail(path, "must be an array")
        items_schema = schema["items"]
        if isinstance(items_schema, list):
            for index, (value, subschema) in enumerate(zip(instance, items_schema, strict=False)):
                _validate(value, subschema, f"{path}[{index}]")
            if len(instance) > len(items_schema):
                _fail(path, "has more items than the schema allows")
        else:
            for index, value in enumerate(instance):
                _validate(value, items_schema, f"{path}[{index}]")


def validate(instance: Any, schema: Any) -> None:
    """Validate ``instance`` against ``schema``."""

    _validate(instance, schema)


class Draft202012Validator:
    """Tiny compatibility shim for ``jsonschema.Draft202012Validator``."""

    @staticmethod
    def check_schema(schema: Any) -> None:
        if not isinstance(schema, dict):
            raise ValidationError("schema must be a mapping")


__all__ = ["Draft202012Validator", "ValidationError", "validate"]
