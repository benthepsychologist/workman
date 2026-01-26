"""Tests for execute() - the Callable Protocol interface."""

import os
from pathlib import Path

import pytest

from workman.errors import CompileError, ValidationError
from workman.execute import execute


def _write_schema(registry_root: Path, vendor: str, name: str, version: str, properties: dict):
    schema_path = registry_root / "schemas" / vendor / name / "jsonschema" / version / "schema.json"
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(
        __import__("json").dumps(
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": properties,
                "additionalProperties": True,
            }
        )
    )


def _make_registry(tmp_path: Path) -> Path:
    root = tmp_path / "schema-reg"
    vendor = "org1.workman"

    _write_schema(root, vendor, "pm.project.create", "1-0-0", {"project_id": {"type": "string"}})
    _write_schema(root, vendor, "pm.project.close", "1-0-0", {"project_id": {"type": "string"}})
    _write_schema(
        root,
        vendor,
        "pm.work_item.create",
        "1-0-0",
        {"work_item_id": {"type": "string"}, "project_id": {"type": "string"}},
    )
    _write_schema(root, vendor, "pm.work_item.complete", "1-0-0", {"work_item_id": {"type": "string"}})
    _write_schema(
        root,
        vendor,
        "pm.work_item.move",
        "1-0-0",
        {"work_item_id": {"type": "string"}, "project_id": {"type": "string"}},
    )
    _write_schema(
        root,
        vendor,
        "pm.deliverable.create",
        "1-0-0",
        {"deliverable_id": {"type": "string"}, "project_id": {"type": "string"}},
    )
    _write_schema(root, vendor, "pm.deliverable.complete", "1-0-0", {"deliverable_id": {"type": "string"}})

    return root


class TestExecuteCallableResult:
    """Tests for CallableResult structure."""

    def test_returns_schema_version(self, tmp_path):
        """execute() must return schema_version in result."""
        os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

        result = execute({
            "op": "pm.project.create",
            "payload": {},
            "ctx": {"correlation_id": "c1", "producer": "test"},
        })

        assert result["schema_version"] == "1.0"

    def test_returns_items_list(self, tmp_path):
        """execute() must return items list with domain events."""
        os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

        result = execute({
            "op": "pm.project.create",
            "payload": {},
            "ctx": {"correlation_id": "c1", "producer": "test"},
        })

        assert "items" in result
        assert isinstance(result["items"], list)
        assert len(result["items"]) == 1

    def test_returns_stats(self, tmp_path):
        """execute() must return stats with input/output/skipped/errors."""
        os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

        result = execute({
            "op": "pm.project.create",
            "payload": {},
            "ctx": {"correlation_id": "c1", "producer": "test"},
        })

        assert result["stats"] == {"input": 1, "output": 1, "skipped": 0, "errors": 0}


class TestExecuteDomainEvents:
    """Tests for domain event item structure."""

    def test_item_has_event_type(self, tmp_path):
        """Domain event item must have event_type."""
        os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

        result = execute({
            "op": "pm.project.create",
            "payload": {},
            "ctx": {"correlation_id": "c1", "producer": "test"},
        })

        item = result["items"][0]
        assert item["event_type"] == "project.created"

    def test_item_has_aggregate_type(self, tmp_path):
        """Domain event item must have aggregate_type."""
        os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

        result = execute({
            "op": "pm.project.create",
            "payload": {},
            "ctx": {"correlation_id": "c1", "producer": "test"},
        })

        item = result["items"][0]
        assert item["aggregate_type"] == "project"

    def test_item_has_aggregate_id(self, tmp_path):
        """Domain event item must have aggregate_id."""
        os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

        result = execute({
            "op": "pm.project.create",
            "payload": {"project_id": "proj_TEST123"},
            "ctx": {"correlation_id": "c1", "producer": "test"},
        })

        item = result["items"][0]
        assert item["aggregate_id"] == "proj_TEST123"

    def test_item_has_payload(self, tmp_path):
        """Domain event item must have payload."""
        os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

        result = execute({
            "op": "pm.project.create",
            "payload": {"project_id": "proj_TEST123", "name": "My Project"},
            "ctx": {"correlation_id": "c1", "producer": "test"},
        })

        item = result["items"][0]
        assert item["payload"]["project_id"] == "proj_TEST123"
        assert item["payload"]["name"] == "My Project"

    def test_item_has_idempotency_key(self, tmp_path):
        """Domain event item must have idempotency_key."""
        os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

        result = execute({
            "op": "pm.project.create",
            "payload": {"project_id": "proj_TEST123"},
            "ctx": {"correlation_id": "corr-123", "producer": "test-producer"},
        })

        item = result["items"][0]
        expected_key = "test-producer:pm.project.create:project:proj_TEST123:corr-123"
        assert item["idempotency_key"] == expected_key

    def test_item_has_is_create_flag(self, tmp_path):
        """Domain event item must have is_create flag."""
        os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

        # CREATE op
        result_create = execute({
            "op": "pm.project.create",
            "payload": {},
            "ctx": {"correlation_id": "c1", "producer": "test"},
        })
        assert result_create["items"][0]["is_create"] is True

        # MUTATION op
        result_mutation = execute({
            "op": "pm.project.close",
            "payload": {"project_id": "proj_TEST"},
            "ctx": {"correlation_id": "c1", "producer": "test"},
        })
        assert result_mutation["items"][0]["is_create"] is False

    def test_item_has_caller_supplied_id_flag(self, tmp_path):
        """Domain event item must have caller_supplied_id flag."""
        os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

        # Caller-supplied ID
        result_supplied = execute({
            "op": "pm.project.create",
            "payload": {"project_id": "proj_TEST123"},
            "ctx": {"correlation_id": "c1", "producer": "test"},
        })
        assert result_supplied["items"][0]["caller_supplied_id"] is True

        # Generated ID
        result_generated = execute({
            "op": "pm.project.create",
            "payload": {},
            "ctx": {"correlation_id": "c1", "producer": "test"},
        })
        assert result_generated["items"][0]["caller_supplied_id"] is False


class TestExecuteFkRefs:
    """Tests for FK reference hints in domain events."""

    def test_item_has_fk_refs_when_present(self, tmp_path):
        """Domain event item must have fk_refs when FK fields present."""
        os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

        result = execute({
            "op": "pm.work_item.create",
            "payload": {"project_id": "proj_PARENT123"},
            "ctx": {"correlation_id": "c1", "producer": "test"},
        })

        item = result["items"][0]
        assert item["fk_refs"] == [
            {"aggregate_type": "project", "aggregate_id": "proj_PARENT123"}
        ]

    def test_item_has_empty_fk_refs_when_no_fk(self, tmp_path):
        """Domain event item must have empty fk_refs when no FK fields."""
        os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

        result = execute({
            "op": "pm.project.create",
            "payload": {},
            "ctx": {"correlation_id": "c1", "producer": "test"},
        })

        item = result["items"][0]
        assert item["fk_refs"] == []

    def test_item_has_empty_fk_refs_when_fk_not_provided(self, tmp_path):
        """Domain event item must have empty fk_refs when FK field not in payload."""
        os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

        result = execute({
            "op": "pm.work_item.create",
            "payload": {},  # No project_id provided
            "ctx": {"correlation_id": "c1", "producer": "test"},
        })

        item = result["items"][0]
        assert item["fk_refs"] == []


class TestExecuteIdGeneration:
    """Tests for ID generation in execute()."""

    def test_generates_id_when_not_provided(self, tmp_path):
        """execute() should generate ID when not provided in payload."""
        os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

        payload = {}
        result = execute({
            "op": "pm.project.create",
            "payload": payload,
            "ctx": {"correlation_id": "c1", "producer": "test"},
        })

        item = result["items"][0]
        assert item["aggregate_id"].startswith("proj_")
        # ID should be injected into payload
        assert "project_id" in payload
        assert payload["project_id"] == item["aggregate_id"]

    def test_uses_caller_supplied_id(self, tmp_path):
        """execute() should use caller-supplied ID when provided."""
        os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

        result = execute({
            "op": "pm.project.create",
            "payload": {"project_id": "proj_CALLER123"},
            "ctx": {"correlation_id": "c1", "producer": "test"},
        })

        item = result["items"][0]
        assert item["aggregate_id"] == "proj_CALLER123"


class TestExecuteIdempotency:
    """Tests for idempotency key generation."""

    def test_idempotency_key_is_deterministic(self, tmp_path):
        """Same inputs should produce same idempotency_key."""
        os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

        params = {
            "op": "pm.project.create",
            "payload": {"project_id": "proj_SAME"},
            "ctx": {"correlation_id": "same-corr", "producer": "same-producer"},
        }

        result1 = execute(params.copy())
        # Need a fresh payload dict for second call
        params["payload"] = {"project_id": "proj_SAME"}
        result2 = execute(params)

        assert result1["items"][0]["idempotency_key"] == result2["items"][0]["idempotency_key"]


class TestExecuteErrorHandling:
    """Tests for error handling in execute()."""

    def test_unknown_op_raises_compile_error(self, tmp_path):
        """Unknown operation should raise CompileError."""
        with pytest.raises(CompileError) as exc_info:
            execute({
                "op": "unknown.nonexistent.op",
                "payload": {},
                "ctx": {"correlation_id": "c1", "producer": "test"},
            })

        assert "Unknown operation" in str(exc_info.value)
        assert exc_info.value.op == "unknown.nonexistent.op"

    def test_invalid_payload_raises_validation_error(self, tmp_path):
        """Invalid payload should raise ValidationError."""
        # Create schema with required field
        root = tmp_path / "schema-reg"
        vendor = "org1.workman"
        schema_path = root / "schemas" / vendor / "pm.project.create" / "jsonschema" / "1-0-0" / "schema.json"
        schema_path.parent.mkdir(parents=True, exist_ok=True)
        schema_path.write_text(
            __import__("json").dumps(
                {
                    "$schema": "http://json-schema.org/draft-07/schema#",
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "name": {"type": "string"},
                    },
                    "required": ["name"],
                }
            )
        )

        os.environ["SCHEMA_REGISTRY_ROOT"] = str(root)

        with pytest.raises(ValidationError) as exc_info:
            execute({
                "op": "pm.project.create",
                "payload": {},  # Missing required 'name' field
                "ctx": {"correlation_id": "c1", "producer": "test"},
            })

        assert "Payload validation failed" in str(exc_info.value)


class TestExecuteNoStoraclePlan:
    """Tests ensuring execute() does NOT return StoraclePlan structures."""

    def test_no_plan_version_in_result(self, tmp_path):
        """execute() should NOT return plan_version (that's compile() behavior)."""
        os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

        result = execute({
            "op": "pm.project.create",
            "payload": {},
            "ctx": {"correlation_id": "c1", "producer": "test"},
        })

        assert "plan_version" not in result

    def test_no_ops_in_result(self, tmp_path):
        """execute() should NOT return ops list (that's compile() behavior)."""
        os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

        result = execute({
            "op": "pm.project.create",
            "payload": {},
            "ctx": {"correlation_id": "c1", "producer": "test"},
        })

        assert "ops" not in result

    def test_no_wal_append_in_items(self, tmp_path):
        """execute() items should NOT contain wal.append methods."""
        os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

        result = execute({
            "op": "pm.project.create",
            "payload": {},
            "ctx": {"correlation_id": "c1", "producer": "test"},
        })

        for item in result["items"]:
            assert "method" not in item
            assert "jsonrpc" not in item


class TestExecuteWorkItemMove:
    """Tests for pm.work_item.move operation."""

    def test_work_item_move_returns_domain_event(self, tmp_path):
        """pm.work_item.move should return proper domain event."""
        os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

        result = execute({
            "op": "pm.work_item.move",
            "payload": {"work_item_id": "wi_TEST123", "project_id": "proj_DEST"},
            "ctx": {"correlation_id": "c1", "producer": "test"},
        })

        item = result["items"][0]
        assert item["event_type"] == "work_item.moved"
        assert item["aggregate_type"] == "work_item"
        assert item["aggregate_id"] == "wi_TEST123"
        assert item["is_create"] is False
        assert item["fk_refs"] == [{"aggregate_type": "project", "aggregate_id": "proj_DEST"}]
