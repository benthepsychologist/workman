import os
from pathlib import Path

import pytest

from workman.errors import CompileError, ValidationError


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


def test_compile_create_generates_id_no_not_exists(tmp_path):
    os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

    from workman.compile import compile

    ctx = {
        "occurred_at": "2026-01-01T00:00:00Z",
        "actor": {"type": "user", "id": "u1"},
        "correlation_id": "c1",
        "producer": "life",
    }

    payload = {}
    plan = compile("pm.project.create", payload, ctx)

    assert plan["plan_version"] == "storacle.plan/1.0.0"
    assert plan["jsonrpc"] == "2.0"
    assert plan["meta"]["op"] == "pm.project.create"

    # create without caller-provided ID => no assert.not_exists
    assert len(plan["ops"]) == 1
    assert plan["ops"][0]["method"] == "wal.append"
    assert "project_id" in payload


def test_compile_create_with_id_adds_not_exists(tmp_path):
    os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

    from workman.compile import compile

    ctx = {"correlation_id": "c1", "producer": "life"}
    payload = {"project_id": "proj_01HZYTEST"}

    plan = compile("pm.project.create", payload, ctx)

    assert plan["ops"][0]["method"] == "assert.not_exists"
    assert plan["ops"][0]["params"] == {"aggregate_type": "project", "aggregate_id": "proj_01HZYTEST"}
    assert plan["ops"][1]["method"] == "wal.append"


def test_compile_mutation_adds_exists(tmp_path):
    os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

    from workman.compile import compile

    ctx = {"correlation_id": "c1", "producer": "life"}
    payload = {"project_id": "proj_01HZYTEST"}

    plan = compile("pm.project.close", payload, ctx)

    assert plan["ops"][0]["method"] == "assert.exists"
    assert plan["ops"][1]["method"] == "wal.append"


def test_compile_fk_asserts_only_when_present(tmp_path):
    os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

    from workman.compile import compile

    ctx = {"correlation_id": "c1", "producer": "life"}

    payload = {"work_item_id": "wi_01HZYTEST", "project_id": "proj_01HZYPARENT"}
    plan = compile("pm.work_item.create", payload, ctx)

    # caller-supplied id => not_exists on work_item, then exists on project
    assert [op["method"] for op in plan["ops"][:2]] == ["assert.not_exists", "assert.exists"]
    assert plan["ops"][1]["params"]["aggregate_type"] == "project"
    assert plan["ops"][1]["params"]["aggregate_id"] == "proj_01HZYPARENT"


def test_compile_work_item_move_has_exists_and_fk(tmp_path):
    """pm.work_item.move should assert work_item exists and project FK exists."""
    os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

    from workman.compile import compile

    ctx = {"correlation_id": "c1", "producer": "life"}
    payload = {"work_item_id": "wi_01HZYTEST", "project_id": "proj_DEST"}

    plan = compile("pm.work_item.move", payload, ctx)

    # mutation => assert.exists on work_item, then assert.exists on project (FK), then wal.append
    methods = [op["method"] for op in plan["ops"]]
    assert methods == ["assert.exists", "assert.exists", "wal.append"]

    # First assertion: work_item exists
    assert plan["ops"][0]["params"]["aggregate_type"] == "work_item"
    assert plan["ops"][0]["params"]["aggregate_id"] == "wi_01HZYTEST"

    # Second assertion: project FK exists
    assert plan["ops"][1]["params"]["aggregate_type"] == "project"
    assert plan["ops"][1]["params"]["aggregate_id"] == "proj_DEST"

    # wal.append has correct event_type
    wal_op = plan["ops"][2]
    assert wal_op["params"]["event_type"] == "work_item.moved"
    assert wal_op["params"]["payload"]["work_item_id"] == "wi_01HZYTEST"
    assert wal_op["params"]["payload"]["project_id"] == "proj_DEST"


def test_compile_unknown_op_raises_compile_error(tmp_path):
    """Unknown operation should raise CompileError."""
    from workman.compile import compile

    ctx = {"correlation_id": "c1", "producer": "life"}
    payload = {}

    with pytest.raises(CompileError) as exc_info:
        compile("unknown.nonexistent.op", payload, ctx)

    assert "Unknown operation" in str(exc_info.value)
    assert exc_info.value.op == "unknown.nonexistent.op"


def test_compile_invalid_payload_raises_validation_error(tmp_path):
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

    from workman.compile import compile

    ctx = {"correlation_id": "c1", "producer": "life"}
    payload = {}  # Missing required 'name' field
    payload_before = payload.copy()

    with pytest.raises(ValidationError) as exc_info:
        compile("pm.project.create", payload, ctx)

    assert "Payload validation failed" in str(exc_info.value)
    assert payload == payload_before
    assert "project_id" not in payload


def test_wal_append_has_deterministic_idempotency_key(tmp_path):
    """wal.append should have deterministic idempotency_key based on ctx and op."""
    os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

    from workman.compile import compile

    ctx = {
        "occurred_at": "2026-01-01T00:00:00Z",
        "actor": {"type": "user", "id": "u1"},
        "correlation_id": "corr-123",
        "producer": "test-producer",
    }
    payload = {"project_id": "proj_01HZYTEST"}

    plan = compile("pm.project.create", payload, ctx)

    wal_op = [op for op in plan["ops"] if op["method"] == "wal.append"][0]

    # Idempotency key format: {producer}:{op}:{aggregate_type}:{aggregate_id}:{correlation_id}
    expected_key = "test-producer:pm.project.create:project:proj_01HZYTEST:corr-123"
    assert wal_op["params"]["idempotency_key"] == expected_key


def test_wal_append_has_proper_ctx_fields(tmp_path):
    """wal.append should include actor, correlation_id, occurred_at, and producer from ctx."""
    os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

    from workman.compile import compile

    ctx = {
        "occurred_at": "2026-01-01T12:00:00Z",
        "actor": {"type": "service", "id": "svc-abc"},
        "correlation_id": "corr-456",
        "producer": "api-gateway",
    }
    payload = {"project_id": "proj_01HZYTEST"}

    plan = compile("pm.project.create", payload, ctx)

    wal_op = [op for op in plan["ops"] if op["method"] == "wal.append"][0]
    params = wal_op["params"]

    assert params["occurred_at"] == "2026-01-01T12:00:00Z"
    assert params["actor"] == {"type": "service", "id": "svc-abc"}
    assert params["correlation_id"] == "corr-456"
    assert params["producer"] == "api-gateway"


def test_wal_append_idempotency_key_is_deterministic_across_calls(tmp_path):
    """Same inputs should produce same idempotency_key."""
    os.environ["SCHEMA_REGISTRY_ROOT"] = str(_make_registry(tmp_path))

    from workman.compile import compile

    ctx = {
        "correlation_id": "same-corr",
        "producer": "same-producer",
    }
    payload1 = {"project_id": "proj_SAME"}
    payload2 = {"project_id": "proj_SAME"}

    plan1 = compile("pm.project.create", payload1, ctx)
    plan2 = compile("pm.project.create", payload2, ctx)

    wal_op1 = [op for op in plan1["ops"] if op["method"] == "wal.append"][0]
    wal_op2 = [op for op in plan2["ops"] if op["method"] == "wal.append"][0]

    assert wal_op1["params"]["idempotency_key"] == wal_op2["params"]["idempotency_key"]
