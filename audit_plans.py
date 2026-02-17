#!/usr/bin/env python3
"""Audit script: compile all 24 PM ops and dump their full StoraclePlans."""

import json
import os
import sys
import tempfile
from pathlib import Path


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


def setup_registry(tmpdir: Path) -> Path:
    root = tmpdir / "schema-reg"
    vendor = "org1.workman"

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
    _write_schema(root, vendor, "pm.opsstream.create", "1-0-0", {
        "opsstream_id": {"type": "string"}, "name": {"type": "string"},
        "type": {"type": "string"}, "owner": {"type": "string"},
        "status": {"type": "string"}, "description": {"type": "string"},
        "meta": {"type": "object"},
    })
    _write_schema(root, vendor, "pm.opsstream.update", "1-0-0", {"opsstream_id": {"type": "string"}, "name": {"type": "string"}, "status": {"type": "string"}})
    _write_schema(root, vendor, "pm.opsstream.close", "1-0-0", {"opsstream_id": {"type": "string"}, "reason": {"type": "string"}})
    _write_schema(root, vendor, "pm.artifact.create", "1-0-0", {
        "artifact_id": {"type": "string"}, "name": {"type": "string"},
        "kind": {"type": "string"}, "work_item_id": {"type": "string"},
        "deliverable_id": {"type": "string"}, "project_id": {"type": "string"},
        "opsstream_id": {"type": "string"},
    })
    _write_schema(root, vendor, "pm.artifact.update", "1-0-0", {"artifact_id": {"type": "string"}, "name": {"type": "string"}})
    _write_schema(root, vendor, "pm.artifact.finalize", "1-0-0", {"artifact_id": {"type": "string"}})
    _write_schema(root, vendor, "pm.artifact.deliver", "1-0-0", {"artifact_id": {"type": "string"}, "delivered_via": {"type": "string"}, "content_ref": {"type": "string"}})
    _write_schema(root, vendor, "pm.artifact.defer", "1-0-0", {"artifact_id": {"type": "string"}, "reason": {"type": "string"}})
    _write_schema(root, vendor, "pm.artifact.supersede", "1-0-0", {"artifact_id": {"type": "string"}, "superseded_by": {"type": "string"}, "superseded_by_id": {"type": "string"}})
    _write_schema(root, vendor, "pm.artifact.archive", "1-0-0", {"artifact_id": {"type": "string"}})
    _write_schema(root, vendor, "link.create", "1-0-0", {
        "link_id": {"type": "string"}, "source_id": {"type": "string"},
        "source_type": {"type": "string"}, "target_id": {"type": "string"},
        "target_type": {"type": "string"}, "predicate": {"type": "string"},
        "meta": {"type": "object"},
    })
    _write_schema(root, vendor, "link.remove", "1-0-0", {"link_id": {"type": "string"}, "reason": {"type": "string"}})

    return root


def main():
    tmpdir = Path(tempfile.mkdtemp())
    registry_root = setup_registry(tmpdir)
    os.environ["SCHEMA_REGISTRY_ROOT"] = str(registry_root)

    from workman.compile import compile  # noqa: import after env set

    ctx = {
        "actor": "audit_user",
        "producer": "audit_script",
        "correlation_id": "corr_AUDIT",
        "occurred_at": "2026-02-13T00:00:00Z",
    }

    ops = [
        ("pm.project.create", {"name": "Test Project"}),
        ("pm.project.update", {"project_id": "proj_EXIST", "name": "Updated"}),
        ("pm.project.close", {"project_id": "proj_EXIST"}),
        ("pm.work_item.create", {"title": "Test Task", "project_id": "proj_FK"}),
        ("pm.work_item.update", {"work_item_id": "wi_EXIST", "title": "Updated"}),
        ("pm.work_item.complete", {"work_item_id": "wi_EXIST"}),
        ("pm.work_item.move", {"work_item_id": "wi_EXIST", "project_id": "proj_FK", "opsstream_id": "ops_FK"}),
        ("pm.work_item.cancel", {"work_item_id": "wi_EXIST"}),
        ("pm.deliverable.create", {"name": "Test Del", "project_id": "proj_FK"}),
        ("pm.deliverable.update", {"deliverable_id": "del_EXIST", "name": "Updated"}),
        ("pm.deliverable.complete", {"deliverable_id": "del_EXIST"}),
        ("pm.deliverable.reject", {"deliverable_id": "del_EXIST"}),
        ("pm.opsstream.create", {"name": "Test Stream"}),
        ("pm.opsstream.update", {"opsstream_id": "ops_EXIST", "name": "Updated"}),
        ("pm.opsstream.close", {"opsstream_id": "ops_EXIST"}),
        ("pm.artifact.create", {"name": "Test Art", "kind": "SESSION_NOTE", "work_item_id": "wi_FK"}),
        ("pm.artifact.update", {"artifact_id": "art_EXIST", "name": "Updated"}),
        ("pm.artifact.finalize", {"artifact_id": "art_EXIST"}),
        ("pm.artifact.deliver", {"artifact_id": "art_EXIST", "content_ref": "https://example.com", "delivered_via": "gdrive"}),
        ("pm.artifact.defer", {"artifact_id": "art_EXIST"}),
        ("pm.artifact.supersede", {"artifact_id": "art_EXIST", "superseded_by_id": "art_OTHER"}),
        ("pm.artifact.archive", {"artifact_id": "art_EXIST"}),
        ("link.create", {"source_id": "proj_A", "source_type": "project", "target_id": "wi_B", "target_type": "work_item", "predicate": "contains"}),
        ("link.remove", {"link_id": "lnk_EXIST"}),
    ]

    # Pin IDs for create ops so we get deterministic output
    pins_for_creates = {"id": "GENERATED_ID"}

    for i, (op_name, payload) in enumerate(ops, 1):
        payload_copy = dict(payload)  # don't mutate the original across iterations
        print(f"\n{'='*80}")
        print(f"  [{i:02d}/24] {op_name}")
        print(f"  Input payload: {json.dumps(payload_copy)}")
        print(f"{'='*80}")
        try:
            # Determine if this is a create op (id not supplied in payload)
            from workman.catalog import get_op_spec
            spec = get_op_spec(op_name)
            is_auto_id = spec and spec.is_create and spec.id_field not in payload_copy
            pins = pins_for_creates if is_auto_id else None

            plan = compile(op_name, payload_copy, ctx, pins=pins)

            # Pretty-print the plan
            print(json.dumps(plan, indent=2))

            # Extract summary
            assertions = [o for o in plan["ops"] if o["method"].startswith("assert.")]
            writes = [o for o in plan["ops"] if o["method"] == "wal.append"]

            print(f"\n  --- SUMMARY ---")
            print(f"  aggregate_type: {writes[0]['params']['aggregate_type'] if writes else 'N/A'}")
            print(f"  event_type:     {writes[0]['params']['event_type'] if writes else 'N/A'}")
            print(f"  aggregate_id:   {writes[0]['params']['aggregate_id'] if writes else 'N/A'}")
            print(f"  id_prefix:      {spec.id_prefix if spec else 'N/A'}")
            print(f"  is_create:      {spec.is_create if spec else 'N/A'}")
            print(f"  auto_gen_id:    {is_auto_id}")
            print(f"  assertions:     {len(assertions)}")
            for a in assertions:
                print(f"    - {a['method']}({a['params']['aggregate_type']}, {a['params']['aggregate_id']})")
            print(f"  payload_fields: {list(writes[0]['params']['payload'].keys()) if writes else []}")
            fk_fields = spec.fk_asserts if spec else []
            print(f"  fk_asserts (catalog): {fk_fields}")

        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")

    print(f"\n{'='*80}")
    print(f"  AUDIT COMPLETE: {len(ops)} ops compiled")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
