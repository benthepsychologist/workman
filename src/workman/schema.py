"""Schema resolution and payload validation."""

import json
import os
from pathlib import Path

import jsonschema

from workman.errors import ValidationError


def _schema_registry_root() -> Path:
    return Path(
        os.environ.get(
            "SCHEMA_REGISTRY_ROOT",
            os.path.expanduser("~/.local/schema-transform-registry"),
        )
    )


def resolve_schema(iglu_ref: str) -> dict:
    if not iglu_ref.startswith("iglu:"):
        raise ValidationError(f"Invalid iglu ref format: {iglu_ref}")

    parts = iglu_ref[5:].split("/")
    if len(parts) != 4:
        raise ValidationError(f"Invalid iglu ref format: {iglu_ref}")

    vendor, name, fmt, version = parts
    schema_path = _schema_registry_root() / "schemas" / vendor / name / fmt / version / "schema.json"

    if not schema_path.exists():
        raise ValidationError(f"Schema not found: {schema_path}")

    try:
        with open(schema_path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON in schema {schema_path}: {e}")


def validate_payload(payload: dict, schema: dict) -> None:
    try:
        jsonschema.validate(instance=payload, schema=schema)
    except jsonschema.ValidationError as e:
        raise ValidationError(f"Payload validation failed: {e.message}", errors=[e])
