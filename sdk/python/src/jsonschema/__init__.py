# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Minimal local ``jsonschema`` compatibility layer for the test suite.

The repository's test environment does not ship the third-party
``jsonschema`` package.  The tests only need a small subset of draft
2020-12 validation behavior, so this module implements enough of that
surface for the repo-local schemas and fixtures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


class ValidationError(Exception):
    """Raised when validation fails."""


@dataclass
class _ValidationContext:
    schema_path: str = "$"
    instance_path: str = "$"

    def child(
        self,
        *,
        schema_key: str | int | None = None,
        instance_key: str | int | None = None,
    ) -> _ValidationContext:
        schema_path = self.schema_path
        if schema_key is not None:
            schema_path = f"{schema_path}/{schema_key}"
        instance_path = self.instance_path
        if instance_key is not None:
            instance_path = f"{instance_path}/{instance_key}"
        return _ValidationContext(schema_path=schema_path, instance_path=instance_path)


def _fail(message: str, ctx: _ValidationContext) -> None:
    raise ValidationError(f"{ctx.instance_path}: {message}")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_type(instance: Any, expected: Any, ctx: _ValidationContext) -> None:
    if isinstance(expected, list):
        for item in expected:
            try:
                _validate_type(instance, item, ctx)
                return
            except ValidationError:
                continue
        _fail(f"is not of type {expected!r}", ctx)
        return

    if expected == "object":
        if not isinstance(instance, dict):
            _fail("is not of type 'object'", ctx)
    elif expected == "array":
        if not isinstance(instance, list):
            _fail("is not of type 'array'", ctx)
    elif expected == "string":
        if not isinstance(instance, str):
            _fail("is not of type 'string'", ctx)
    elif expected == "integer":
        if not _is_int(instance):
            _fail("is not of type 'integer'", ctx)
    elif expected == "number":
        if not isinstance(instance, (int, float)) or isinstance(instance, bool):
            _fail("is not of type 'number'", ctx)
    elif expected == "boolean":
        if not isinstance(instance, bool):
            _fail("is not of type 'boolean'", ctx)
    elif expected == "null":
        if instance is not None:
            _fail("is not of type 'null'", ctx)
    else:
        raise ValidationError(f"{ctx.schema_path}: unsupported schema type {expected!r}")


def _validate_schema(instance: Any, schema: dict[str, Any], ctx: _ValidationContext) -> None:
    if "anyOf" in schema:
        for index, subschema in enumerate(schema["anyOf"]):
            try:
                _validate_schema(instance, subschema, ctx.child(schema_key=f"anyOf/{index}"))
                break
            except ValidationError:
                continue
        else:
            _fail("does not match any of anyOf alternatives", ctx)
        return

    if "allOf" in schema:
        for index, subschema in enumerate(schema["allOf"]):
            _validate_schema(instance, subschema, ctx.child(schema_key=f"allOf/{index}"))
        return

    if "oneOf" in schema:
        matches = 0
        for index, subschema in enumerate(schema["oneOf"]):
            try:
                _validate_schema(instance, subschema, ctx.child(schema_key=f"oneOf/{index}"))
            except ValidationError:
                continue
            else:
                matches += 1
        if matches != 1:
            _fail("does not match exactly one oneOf alternative", ctx)
        return

    if "const" in schema and instance != schema["const"]:
        _fail(f"does not equal const {schema['const']!r}", ctx)

    if "enum" in schema and instance not in schema["enum"]:
        _fail(f"is not one of {schema['enum']!r}", ctx)

    if "type" in schema:
        _validate_type(instance, schema["type"], ctx)

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            _fail(f"is shorter than minLength {schema['minLength']}", ctx)
        if "pattern" in schema and re.fullmatch(schema["pattern"], instance) is None:
            _fail(f"does not match pattern {schema['pattern']!r}", ctx)

    if _is_int(instance):
        if "minimum" in schema and instance < schema["minimum"]:
            _fail(f"is less than minimum {schema['minimum']}", ctx)
        if "maximum" in schema and instance > schema["maximum"]:
            _fail(f"is greater than maximum {schema['maximum']}", ctx)

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            _fail(f"has fewer than minItems {schema['minItems']}", ctx)
        if "items" in schema:
            for idx, item in enumerate(instance):
                _validate_schema(item, schema["items"], ctx.child(instance_key=idx))
        return

    if isinstance(instance, dict):
        if "minProperties" in schema and len(instance) < schema["minProperties"]:
            _fail(f"has fewer than minProperties {schema['minProperties']}", ctx)
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                _fail(f"missing required property {key!r}", ctx)

        properties = schema.get("properties", {})
        for key, subschema in properties.items():
            if key in instance:
                _validate_schema(instance[key], subschema, ctx.child(instance_key=key, schema_key=f"properties/{key}"))

        additional_properties = schema.get("additionalProperties", True)
        if additional_properties is False:
            allowed = set(properties) | set(required)
            extra = [key for key in instance if key not in allowed]
            if extra:
                _fail(f"additional properties are not allowed: {extra}", ctx)
        elif isinstance(additional_properties, dict):
            allowed = set(properties)
            for key, value in instance.items():
                if key not in allowed:
                    _validate_schema(
                        value,
                        additional_properties,
                        ctx.child(instance_key=key, schema_key="additionalProperties"),
                    )
        return


def validate(instance: Any, schema: dict[str, Any]) -> None:
    """Validate ``instance`` against ``schema`` and raise ``ValidationError`` on mismatch."""
    _validate_schema(instance, schema, _ValidationContext())


class Draft202012Validator:
    """Compatibility shim exposing the subset used by the tests."""

    @staticmethod
    def check_schema(schema: dict[str, Any]) -> None:
        if not isinstance(schema, dict):
            raise ValidationError("schema must be a JSON object")
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise ValidationError("unsupported schema dialect")


__all__ = [
    "Draft202012Validator",
    "ValidationError",
    "validate",
]
