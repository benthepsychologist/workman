import os
from pathlib import Path


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
