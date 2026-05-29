# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Test import setup for the sdk/python test suite."""

from __future__ import annotations

import json
import re
import sys
import types
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
SDK_SRC = REPO_ROOT / "sdk" / "python" / "src"

for path in (REPO_ROOT, SDK_SRC):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)


def _install_jsonschema_stub() -> None:
    try:
        import jsonschema  # type: ignore  # noqa: F401
    except ModuleNotFoundError:
        pass
    else:
        return

    class ValidationError(Exception):
        """Raised when a payload does not satisfy the test-local schema subset."""

    def _type_matches(instance: Any, schema_type: str) -> bool:
        if schema_type == "object":
            return isinstance(instance, dict)
        if schema_type == "array":
            return isinstance(instance, list)
        if schema_type == "string":
            return isinstance(instance, str)
        if schema_type == "integer":
            return isinstance(instance, int) and not isinstance(instance, bool)
        if schema_type == "number":
            return isinstance(instance, (int, float)) and not isinstance(instance, bool)
        if schema_type == "boolean":
            return isinstance(instance, bool)
        if schema_type == "null":
            return instance is None
        raise ValidationError(f"unsupported schema type: {schema_type}")

    def _validate(instance: Any, schema: dict[str, Any], *, path: str = "$") -> None:
        if "anyOf" in schema:
            errors: list[str] = []
            for candidate in schema["anyOf"]:
                try:
                    _validate(instance, candidate, path=path)
                except ValidationError as exc:
                    errors.append(str(exc))
                else:
                    break
            else:
                raise ValidationError(f"{path}: no anyOf branch matched: {errors[0] if errors else 'no match'}")
            return

        if "enum" in schema and instance not in schema["enum"]:
            raise ValidationError(f"{path}: value {instance!r} not in enum")
        if "const" in schema and instance != schema["const"]:
            raise ValidationError(f"{path}: expected const {schema['const']!r}, got {instance!r}")
        if "type" in schema:
            schema_type = schema["type"]
            if isinstance(schema_type, list):
                if not any(_type_matches(instance, item) for item in schema_type):
                    raise ValidationError(f"{path}: type mismatch, got {type(instance).__name__}")
            elif not _type_matches(instance, schema_type):
                raise ValidationError(f"{path}: type mismatch, got {type(instance).__name__}")
        if isinstance(instance, str):
            if "minLength" in schema and len(instance) < int(schema["minLength"]):
                raise ValidationError(f"{path}: string shorter than minLength")
            if "pattern" in schema and re.fullmatch(schema["pattern"], instance) is None:
                raise ValidationError(f"{path}: string does not match pattern")
        if isinstance(instance, (int, float)) and not isinstance(instance, bool):
            if "minimum" in schema and instance < schema["minimum"]:
                raise ValidationError(f"{path}: value below minimum")
        if isinstance(instance, list):
            if "minItems" in schema and len(instance) < int(schema["minItems"]):
                raise ValidationError(f"{path}: list shorter than minItems")
            if schema.get("uniqueItems"):
                serialised = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in instance]
                if len(serialised) != len(set(serialised)):
                    raise ValidationError(f"{path}: list items are not unique")
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                for index, item in enumerate(instance):
                    _validate(item, item_schema, path=f"{path}/{index}")
        if isinstance(instance, dict):
            required = schema.get("required", [])
            missing = [key for key in required if key not in instance]
            if missing:
                raise ValidationError(f"{path}: missing required keys {missing}")
            properties = schema.get("properties", {})
            for key, subschema in properties.items():
                if key in instance:
                    _validate(instance[key], subschema, path=f"{path}/{key}")
            additional = schema.get("additionalProperties", True)
            if additional is False:
                unknown = [key for key in instance if key not in properties]
                if unknown:
                    raise ValidationError(f"{path}: unknown keys {unknown}")
            elif isinstance(additional, dict):
                for key in instance:
                    if key not in properties:
                        _validate(instance[key], additional, path=f"{path}/{key}")

    class Draft202012Validator:
        @staticmethod
        def check_schema(schema: Any) -> None:
            if not isinstance(schema, dict):
                raise ValidationError("schema must be a JSON object")

    def validate(instance: Any, schema: Any) -> None:
        if not isinstance(schema, dict):
            raise ValidationError("schema must be a JSON object")
        _validate(instance, schema)

    module = types.ModuleType("jsonschema")
    module.ValidationError = ValidationError
    module.Draft202012Validator = Draft202012Validator
    module.validate = validate
    sys.modules["jsonschema"] = module


_install_jsonschema_stub()
