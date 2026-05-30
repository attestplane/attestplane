# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Minimal local ``jsonschema`` compatibility shim for the test suite.

The repository's Python tests only rely on a very small subset of JSON Schema
validation features. This shim keeps the suite self-contained in offline
environments without pulling the third-party dependency.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


class ValidationError(Exception):
    """Raised when a JSON instance does not satisfy the provided schema."""


class Draft202012Validator:
    @staticmethod
    def check_schema(schema: Any) -> None:
        if not isinstance(schema, Mapping):
            raise ValidationError("schema must be a JSON object")


def validate(instance: Any, schema: Any) -> None:
    _validate(instance, schema, path="$")


def _validate(instance: Any, schema: Any, *, path: str) -> None:
    if not isinstance(schema, Mapping):
        raise ValidationError(f"{path}: schema must be a JSON object")

    if "anyOf" in schema:
        any_of = schema["anyOf"]
        if not isinstance(any_of, Sequence) or isinstance(any_of, (str, bytes)):
            raise ValidationError(f"{path}: anyOf must be an array")
        last_error: ValidationError | None = None
        for candidate in any_of:
            try:
                _validate(instance, candidate, path=path)
                break
            except ValidationError as exc:
                last_error = exc
        else:
            raise ValidationError(f"{path}: does not match any allowed schema") from last_error
        return

    if "const" in schema and instance != schema["const"]:
        raise ValidationError(f"{path}: value {instance!r} != const {schema['const']!r}")

    if "enum" in schema:
        enum = schema["enum"]
        if instance not in enum:
            raise ValidationError(f"{path}: value {instance!r} not in enum {enum!r}")

    schema_type = schema.get("type")
    if schema_type is not None:
        _validate_type(instance, schema_type, path=path)

    if isinstance(instance, Mapping):
        _validate_object(instance, schema, path=path)
    elif isinstance(instance, list):
        _validate_array(instance, schema, path=path)
    elif isinstance(instance, str):
        _validate_string(instance, schema, path=path)
    elif isinstance(instance, bool):
        _validate_boolean(instance, schema, path=path)
    elif isinstance(instance, int):
        _validate_integer(instance, schema, path=path)
    elif instance is None:
        _validate_null(instance, schema, path=path)


def _validate_type(instance: Any, schema_type: Any, *, path: str) -> None:
    if isinstance(schema_type, Sequence) and not isinstance(schema_type, (str, bytes)):
        for candidate in schema_type:
            try:
                _validate_type(instance, candidate, path=path)
                return
            except ValidationError:
                continue
        raise ValidationError(f"{path}: type mismatch")

    if schema_type == "object" and not isinstance(instance, Mapping):
        raise ValidationError(f"{path}: expected object")
    if schema_type == "array" and not isinstance(instance, list):
        raise ValidationError(f"{path}: expected array")
    if schema_type == "string" and not isinstance(instance, str):
        raise ValidationError(f"{path}: expected string")
    if schema_type == "boolean" and not isinstance(instance, bool):
        raise ValidationError(f"{path}: expected boolean")
    if schema_type == "integer" and not (isinstance(instance, int) and not isinstance(instance, bool)):
        raise ValidationError(f"{path}: expected integer")
    if schema_type == "number" and not (isinstance(instance, (int, float)) and not isinstance(instance, bool)):
        raise ValidationError(f"{path}: expected number")
    if schema_type == "null" and instance is not None:
        raise ValidationError(f"{path}: expected null")


def _validate_object(instance: Mapping[str, Any], schema: Mapping[str, Any], *, path: str) -> None:
    properties = schema.get("properties")
    if properties is not None and not isinstance(properties, Mapping):
        raise ValidationError(f"{path}: properties must be an object")

    required = schema.get("required", [])
    if not isinstance(required, list):
        raise ValidationError(f"{path}: required must be an array")
    for key in required:
        if key not in instance:
            raise ValidationError(f"{path}: missing required property {key!r}")

    if properties is not None:
        for key, value in instance.items():
            child_schema = properties.get(key)
            if child_schema is not None:
                _validate(value, child_schema, path=f"{path}.{key}")
                continue
            additional = schema.get("additionalProperties", True)
            if additional is False:
                raise ValidationError(f"{path}: additional property {key!r} is not allowed")
            if additional is True or additional is None:
                continue
            _validate(value, additional, path=f"{path}.{key}")

    if properties is None:
        additional = schema.get("additionalProperties", True)
        if additional is False and instance:
            raise ValidationError(f"{path}: additional properties are not allowed")
        if additional not in (True, False, None):
            for key, value in instance.items():
                _validate(value, additional, path=f"{path}.{key}")


def _validate_array(instance: list[Any], schema: Mapping[str, Any], *, path: str) -> None:
    items = schema.get("items")
    if items is not None:
        if isinstance(items, list):
            for i, item_schema in enumerate(items):
                if i < len(instance):
                    _validate(instance[i], item_schema, path=f"{path}[{i}]")
        else:
            for i, item in enumerate(instance):
                _validate(item, items, path=f"{path}[{i}]")


def _validate_string(instance: str, schema: Mapping[str, Any], *, path: str) -> None:
    min_length = schema.get("minLength")
    if isinstance(min_length, int) and len(instance) < min_length:
        raise ValidationError(f"{path}: string too short")
    max_length = schema.get("maxLength")
    if isinstance(max_length, int) and len(instance) > max_length:
        raise ValidationError(f"{path}: string too long")
    pattern = schema.get("pattern")
    if isinstance(pattern, str) and re.fullmatch(pattern, instance) is None:
        raise ValidationError(f"{path}: string does not match pattern {pattern!r}")


def _validate_integer(instance: int, schema: Mapping[str, Any], *, path: str) -> None:
    minimum = schema.get("minimum")
    if isinstance(minimum, (int, float)) and instance < minimum:
        raise ValidationError(f"{path}: integer below minimum")
    maximum = schema.get("maximum")
    if isinstance(maximum, (int, float)) and instance > maximum:
        raise ValidationError(f"{path}: integer above maximum")


def _validate_boolean(instance: bool, schema: Mapping[str, Any], *, path: str) -> None:
    del instance, schema, path


def _validate_null(instance: None, schema: Mapping[str, Any], *, path: str) -> None:
    del instance, schema, path
