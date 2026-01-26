"""Tests for schema resolution and payload validation."""

import json

import pytest

from workman.errors import ValidationError
from workman.schema import resolve_schema, validate_payload


class TestResolveSchema:
    """Tests for resolve_schema function."""

    def test_invalid_iglu_ref_no_prefix(self):
        """Should raise ValidationError for refs without iglu: prefix."""
        with pytest.raises(ValidationError) as exc_info:
            resolve_schema("invalid/ref/format/1-0-0")
        assert "Invalid iglu ref format" in str(exc_info.value)

    def test_invalid_iglu_ref_wrong_parts(self):
        """Should raise ValidationError for refs with wrong number of parts."""
        with pytest.raises(ValidationError) as exc_info:
            resolve_schema("iglu:vendor/name/format")
        assert "Invalid iglu ref format" in str(exc_info.value)

    def test_invalid_iglu_ref_too_many_parts(self):
        """Should raise ValidationError for refs with too many parts."""
        with pytest.raises(ValidationError) as exc_info:
            resolve_schema("iglu:vendor/name/format/1-0-0/extra")
        assert "Invalid iglu ref format" in str(exc_info.value)

    def test_schema_not_found(self, tmp_path, monkeypatch):
        """Should raise ValidationError when schema file does not exist."""
        monkeypatch.setenv("SCHEMA_REGISTRY_ROOT", str(tmp_path))
        with pytest.raises(ValidationError) as exc_info:
            resolve_schema("iglu:com.example/test/jsonschema/1-0-0")
        assert "Schema not found" in str(exc_info.value)

    def test_resolve_valid_schema(self, tmp_path, monkeypatch):
        """Should load and return schema dict for valid iglu ref."""
        monkeypatch.setenv("SCHEMA_REGISTRY_ROOT", str(tmp_path))

        schema_dir = tmp_path / "schemas" / "com.example" / "test" / "jsonschema" / "1-0-0"
        schema_dir.mkdir(parents=True)
        schema_content = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        (schema_dir / "schema.json").write_text(json.dumps(schema_content))

        result = resolve_schema("iglu:com.example/test/jsonschema/1-0-0")
        assert result == schema_content

    def test_resolve_invalid_json(self, tmp_path, monkeypatch):
        """Should raise ValidationError for invalid JSON in schema file."""
        monkeypatch.setenv("SCHEMA_REGISTRY_ROOT", str(tmp_path))

        schema_dir = tmp_path / "schemas" / "com.example" / "broken" / "jsonschema" / "1-0-0"
        schema_dir.mkdir(parents=True)
        (schema_dir / "schema.json").write_text("{invalid json")

        with pytest.raises(ValidationError) as exc_info:
            resolve_schema("iglu:com.example/broken/jsonschema/1-0-0")
        assert "Invalid JSON" in str(exc_info.value)


class TestValidatePayload:
    """Tests for validate_payload function."""

    def test_valid_payload(self):
        """Should not raise for valid payload matching schema."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name"],
        }
        payload = {"name": "test", "age": 25}
        validate_payload(payload, schema)  # Should not raise

    def test_invalid_payload_missing_required(self):
        """Should raise ValidationError for missing required field."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        payload = {"age": 25}
        with pytest.raises(ValidationError) as exc_info:
            validate_payload(payload, schema)
        assert "Payload validation failed" in str(exc_info.value)
        assert len(exc_info.value.errors) == 1

    def test_invalid_payload_wrong_type(self):
        """Should raise ValidationError for wrong type."""
        schema = {
            "type": "object",
            "properties": {"age": {"type": "integer"}},
        }
        payload = {"age": "not an integer"}
        with pytest.raises(ValidationError) as exc_info:
            validate_payload(payload, schema)
        assert "Payload validation failed" in str(exc_info.value)

    def test_empty_payload_with_no_required(self):
        """Should pass for empty payload when no required fields."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }
        payload = {}
        validate_payload(payload, schema)  # Should not raise

    def test_additional_properties(self):
        """Should pass with additional properties by default."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }
        payload = {"name": "test", "extra": "allowed"}
        validate_payload(payload, schema)  # Should not raise

    def test_additional_properties_forbidden(self):
        """Should fail when additional properties are forbidden."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "additionalProperties": False,
        }
        payload = {"name": "test", "extra": "not allowed"}
        with pytest.raises(ValidationError):
            validate_payload(payload, schema)
