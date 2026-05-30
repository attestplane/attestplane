# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Minimal offline jsonschema subset for the sdk/python test suite.

This implements just enough of Draft 2020-12 validation for the locked
schemas in this repository. It is intentionally small and strict rather than
feature-complete.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any


class ValidationError(ValueError):
    """Raised when an instance does not satisfy a schema."""


class Draft202012Validator:
    """Compatibility shim for the subset used by the tests."""

    @staticmethod
    def check_schema(schema: Any) -> None:
        if not isinstance(schema, dict):
            raise ValidationError(f"schema must be a JSON object, got {type(schema).__name__}")


def validate(instance: Any, schema: Any) -> None:
    """Validate ``instance`` against ``schema`` using a locked subset."""

    _validate(instance, schema, path="$")


def _validate(instance: Any, schema: Any, *, path: str) -> None:
    if not isinstance(schema, dict):
        raise ValidationError(f"{path}: schema must be a JSON object")

    if "anyOf" in schema:
        errors: list[str] = []
        for option in schema["anyOf"]:
            try:
                _validate(instance, option, path=path)
            except ValidationError as exc:
                errors.append(str(exc))
            else:
                break
        else:
            raise ValidationError(f"{path}: no anyOf branch matched: {errors[0] if errors else 'no branches'}")
        return

    if "const" in schema and instance != schema["const"]:
        raise ValidationError(f"{path}: expected const {schema['const']!r}, got {instance!r}")

    if "enum" in schema and instance not in schema["enum"]:
        raise ValidationError(f"{path}: expected one of {schema['enum']!r}, got {instance!r}")

    schema_type = schema.get("type")
    if schema_type is not None:
        _validate_type(instance, schema_type, path=path)

    if isinstance(instance, str):
        _validate_string(instance, schema, path=path)
    elif isinstance(instance, bool):
        pass
    elif isinstance(instance, int):
        _validate_number(instance, schema, path=path)
    elif isinstance(instance, Sequence) and not isinstance(instance, (str, bytes, bytearray)):
        _validate_array(instance, schema, path=path)
    elif isinstance(instance, Mapping):
        _validate_object(instance, schema, path=path)


def _validate_type(instance: Any, schema_type: Any, *, path: str) -> None:
    types = schema_type if isinstance(schema_type, list) else [schema_type]
    for expected in types:
        if expected == "null" and instance is None:
            return
        if expected == "boolean" and isinstance(instance, bool):
            return
        if expected == "integer" and isinstance(instance, int) and not isinstance(instance, bool):
            return
        if expected == "number" and isinstance(instance, (int, float)) and not isinstance(instance, bool):
            return
        if expected == "string" and isinstance(instance, str):
            return
        if expected == "object" and isinstance(instance, Mapping):
            return
        if expected == "array" and isinstance(instance, Sequence) and not isinstance(instance, (str, bytes, bytearray)):
            return
    raise ValidationError(f"{path}: expected type {schema_type!r}, got {type(instance).__name__}")


def _validate_string(instance: str, schema: dict[str, Any], *, path: str) -> None:
    min_length = schema.get("minLength")
    if isinstance(min_length, int) and len(instance) < min_length:
        raise ValidationError(f"{path}: string shorter than minLength {min_length}")
    max_length = schema.get("maxLength")
    if isinstance(max_length, int) and len(instance) > max_length:
        raise ValidationError(f"{path}: string longer than maxLength {max_length}")
    pattern = schema.get("pattern")
    if isinstance(pattern, str) and re.fullmatch(pattern, instance) is None:
        raise ValidationError(f"{path}: string does not match pattern {pattern!r}")


def _validate_number(instance: int | float, schema: dict[str, Any], *, path: str) -> None:
    minimum = schema.get("minimum")
    if isinstance(minimum, (int, float)) and instance < minimum:
        raise ValidationError(f"{path}: value below minimum {minimum}")
    maximum = schema.get("maximum")
    if isinstance(maximum, (int, float)) and instance > maximum:
        raise ValidationError(f"{path}: value above maximum {maximum}")


def _validate_array(instance: Sequence[Any], schema: dict[str, Any], *, path: str) -> None:
    min_items = schema.get("minItems")
    if isinstance(min_items, int) and len(instance) < min_items:
        raise ValidationError(f"{path}: array shorter than minItems {min_items}")
    max_items = schema.get("maxItems")
    if isinstance(max_items, int) and len(instance) > max_items:
        raise ValidationError(f"{path}: array longer than maxItems {max_items}")
    if schema.get("uniqueItems"):
        seen: set[str] = set()
        for item in instance:
            marker = json.dumps(item, sort_keys=True, separators=(",", ":"), default=str)
            if marker in seen:
                raise ValidationError(f"{path}: array has duplicate items")
            seen.add(marker)
    items_schema = schema.get("items")
    if isinstance(items_schema, dict):
        for index, item in enumerate(instance):
            _validate(item, items_schema, path=f"{path}[{index}]")


def _validate_object(instance: Mapping[str, Any], schema: dict[str, Any], *, path: str) -> None:
    required = schema.get("required")
    if isinstance(required, list):
        for key in required:
            if key not in instance:
                raise ValidationError(f"{path}: missing required property {key!r}")

    properties = schema.get("properties")
    if isinstance(properties, dict):
        for key, value_schema in properties.items():
            if key in instance:
                _validate(instance[key], value_schema, path=f"{path}.{key}" if path != "$" else f"$.{key}")

    additional = schema.get("additionalProperties", True)
    if additional is False:
        allowed = set(properties or {})
        extras = [key for key in instance if key not in allowed]
        if extras:
            raise ValidationError(f"{path}: unexpected properties {extras!r}")
    elif isinstance(additional, dict):
        allowed = set(properties or {})
        for key, value in instance.items():
            if key not in allowed:
                _validate(value, additional, path=f"{path}.{key}" if path != "$" else f"$.{key}")
