"""Shared test fixtures for workman tests."""

import json
import os
from pathlib import Path

import pytest


def _write_schema(registry_root: Path, vendor: str, name: str, version: str, properties: dict, **extra):
    """Write a minimal JSON schema to the test registry."""
    schema_path = registry_root / "schemas" / vendor / name / "jsonschema" / version / "schema.json"
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": properties,
        "additionalProperties": True,
    }
    schema.update(extra)
    schema_path.write_text(json.dumps(schema))


@pytest.fixture(autouse=True)
def schema_registry(tmp_path):
    """Set up a temporary schema registry with all op schemas."""
    root = tmp_path / "schema-reg"
    vendor = "org1.workman"

    # Core ops (already tested in test_compile.py but needed by new tests too)
    _write_schema(root, vendor, "pm.project.create", "1-0-0", {"project_id": {"type": "string"}, "name": {"type": "string"}})
    _write_schema(root, vendor, "pm.project.close", "1-0-0", {"project_id": {"type": "string"}})
    _write_schema(root, vendor, "pm.project.update", "1-0-0", {"project_id": {"type": "string"}, "name": {"type": "string"}, "status": {"type": "string"}})
    _write_schema(root, vendor, "pm.work_item.create", "1-0-0", {"work_item_id": {"type": "string"}, "project_id": {"type": "string"}, "title": {"type": "string"}})
    _write_schema(root, vendor, "pm.work_item.complete", "1-0-0", {"work_item_id": {"type": "string"}})
    _write_schema(root, vendor, "pm.work_item.move", "1-0-0", {"work_item_id": {"type": "string"}, "project_id": {"type": "string"}, "opsstream_id": {"type": "string"}, "parent_id": {"type": "string"}})
    _write_schema(root, vendor, "pm.work_item.update", "1-0-0", {
        "work_item_id": {"type": "string"}, "title": {"type": "string"},
        "description": {"type": "string"}, "kind": {"type": "string"},
        "state": {"type": "string"}, "priority": {"type": "string"},
        "severity": {"type": "string"}, "labels": {"type": "array"},
        "assignees": {"type": "array"}, "due_at": {"type": "string"},
        "time_estimate": {"type": "number"}, "time_spent": {"type": "number"},
    })
    _write_schema(root, vendor, "pm.work_item.cancel", "1-0-0", {"work_item_id": {"type": "string"}, "reason": {"type": "string"}})
    _write_schema(root, vendor, "pm.deliverable.create", "1-0-0", {"deliverable_id": {"type": "string"}, "project_id": {"type": "string"}, "name": {"type": "string"}})
    _write_schema(root, vendor, "pm.deliverable.complete", "1-0-0", {"deliverable_id": {"type": "string"}})
    _write_schema(root, vendor, "pm.deliverable.update", "1-0-0", {"deliverable_id": {"type": "string"}, "name": {"type": "string"}})
    _write_schema(root, vendor, "pm.deliverable.reject", "1-0-0", {"deliverable_id": {"type": "string"}, "reason": {"type": "string"}})

    # OpsStream ops
    _write_schema(root, vendor, "pm.opsstream.create", "1-0-0", {
        "opsstream_id": {"type": "string"}, "name": {"type": "string"},
        "type": {"type": "string"}, "owner": {"type": "string"},
        "status": {"type": "string"}, "description": {"type": "string"},
        "meta": {"type": "object"},
    })
    _write_schema(root, vendor, "pm.opsstream.update", "1-0-0", {"opsstream_id": {"type": "string"}, "name": {"type": "string"}, "status": {"type": "string"}})
    _write_schema(root, vendor, "pm.opsstream.close", "1-0-0", {"opsstream_id": {"type": "string"}, "reason": {"type": "string"}})

    # Artifact ops
    _write_schema(root, vendor, "pm.artifact.create", "1-0-0", {
        "artifact_id": {"type": "string"}, "name": {"type": "string"},
        "kind": {"type": "string"}, "work_item_id": {"type": "string"},
        "deliverable_id": {"type": "string"}, "project_id": {"type": "string"},
        "opsstream_id": {"type": "string"},
    })
    _write_schema(root, vendor, "pm.artifact.update", "1-0-0", {"artifact_id": {"type": "string"}, "name": {"type": "string"}})
    _write_schema(root, vendor, "pm.artifact.finalize", "1-0-0", {"artifact_id": {"type": "string"}})
    _write_schema(root, vendor, "pm.artifact.deliver", "1-0-0", {"artifact_id": {"type": "string"}, "delivered_via": {"type": "string"}})
    _write_schema(root, vendor, "pm.artifact.defer", "1-0-0", {"artifact_id": {"type": "string"}, "reason": {"type": "string"}})
    _write_schema(root, vendor, "pm.artifact.supersede", "1-0-0", {"artifact_id": {"type": "string"}, "superseded_by": {"type": "string"}})
    _write_schema(root, vendor, "pm.artifact.archive", "1-0-0", {"artifact_id": {"type": "string"}})

    # Link ops
    _write_schema(root, vendor, "link.create", "1-0-0", {
        "link_id": {"type": "string"}, "source_id": {"type": "string"},
        "source_type": {"type": "string"}, "target_id": {"type": "string"},
        "target_type": {"type": "string"}, "predicate": {"type": "string"},
        "meta": {"type": "object"},
    })
    _write_schema(root, vendor, "link.remove", "1-0-0", {"link_id": {"type": "string"}, "reason": {"type": "string"}})

    old_val = os.environ.get("SCHEMA_REGISTRY_ROOT")
    os.environ["SCHEMA_REGISTRY_ROOT"] = str(root)
    yield root
    if old_val is None:
        del os.environ["SCHEMA_REGISTRY_ROOT"]
    else:
        os.environ["SCHEMA_REGISTRY_ROOT"] = old_val
