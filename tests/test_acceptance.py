"""Acceptance tests: call every op live, check the actual plan output.

Each test calls compile() and execute() against the real iglu schemas
and checks the concrete output structure — no mocks, no fake schemas.
"""

import os
from pathlib import Path

import pytest

from workman.assertions import reset_assertion_counter
from workman.builders import reset_write_counter
from workman.compile import compile
from workman.execute import execute

REAL_REGISTRY = Path.home() / ".local" / "schema-transform-registry"


@pytest.fixture(autouse=True)
def real_schemas(monkeypatch):
    if not REAL_REGISTRY.exists():
        pytest.skip("Real schema registry not available")
    monkeypatch.setenv("SCHEMA_REGISTRY_ROOT", str(REAL_REGISTRY))
    reset_assertion_counter()
    reset_write_counter()


CTX = {"correlation_id": "corr_1", "producer": "test-harness"}


# ── pm.project.create ─────────────────────────────────────────────────

def test_project_create_plan():
    plan = compile("pm.project.create", {"name": "Alpha"}, CTX)

    assert plan["plan_version"] == "storacle.plan/1.0.0"
    assert plan["meta"]["op"] == "pm.project.create"
    assert len(plan["ops"]) == 1  # auto-gen ID → no assert.not_exists

    wal = plan["ops"][0]
    assert wal["method"] == "wal.append"
    assert wal["params"]["event_type"] == "project.created"
    assert wal["params"]["aggregate_type"] == "project"
    assert wal["params"]["aggregate_id"].startswith("proj_")
    assert wal["params"]["payload"]["name"] == "Alpha"
    assert wal["params"]["payload"]["project_id"] == wal["params"]["aggregate_id"]


def test_project_create_execute():
    result = execute({"op": "pm.project.create", "payload": {"name": "Alpha"}, "ctx": CTX})

    assert result["stats"] == {"input": 1, "output": 1, "skipped": 0, "errors": 0}
    item = result["items"][0]
    assert item["event_type"] == "project.created"
    assert item["is_create"] is True
    assert item["aggregate_id"].startswith("proj_")
    assert item["payload"]["name"] == "Alpha"
    assert item["fk_refs"] == []


# ── pm.project.update ─────────────────────────────────────────────────

def test_project_update_plan():
    plan = compile("pm.project.update", {"project_id": "proj_T", "name": "Beta"}, CTX)

    assert len(plan["ops"]) == 2
    assert plan["ops"][0]["method"] == "assert.exists"
    assert plan["ops"][0]["params"] == {"aggregate_type": "project", "aggregate_id": "proj_T"}

    wal = plan["ops"][1]
    assert wal["params"]["event_type"] == "project.updated"
    assert wal["params"]["aggregate_id"] == "proj_T"
    assert wal["params"]["payload"]["name"] == "Beta"


def test_project_update_execute():
    result = execute({"op": "pm.project.update", "payload": {"project_id": "proj_T", "name": "Beta"}, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "project.updated"
    assert item["is_create"] is False
    assert item["aggregate_id"] == "proj_T"
    assert item["payload"]["name"] == "Beta"


# ── pm.project.close ──────────────────────────────────────────────────

def test_project_close_plan():
    plan = compile("pm.project.close", {"project_id": "proj_T", "resolution": "COMPLETED"}, CTX)

    assert plan["ops"][0]["method"] == "assert.exists"
    wal = plan["ops"][1]
    assert wal["params"]["event_type"] == "project.closed"
    assert wal["params"]["aggregate_id"] == "proj_T"
    assert wal["params"]["payload"]["resolution"] == "COMPLETED"


def test_project_close_execute():
    result = execute({"op": "pm.project.close", "payload": {"project_id": "proj_T", "resolution": "COMPLETED"}, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "project.closed"
    assert item["is_create"] is False
    assert item["payload"]["resolution"] == "COMPLETED"


# ── pm.work_item.create ───────────────────────────────────────────────

def test_work_item_create_plan():
    plan = compile("pm.work_item.create", {"title": "Fix bug", "project_id": "proj_P"}, CTX)

    assert len(plan["ops"]) == 2  # auto-gen ID → no not_exists, but FK → assert.exists on project
    assert plan["ops"][0]["method"] == "assert.exists"
    assert plan["ops"][0]["params"] == {"aggregate_type": "project", "aggregate_id": "proj_P"}

    wal = plan["ops"][1]
    assert wal["params"]["event_type"] == "work_item.created"
    assert wal["params"]["aggregate_id"].startswith("wi_")
    assert wal["params"]["payload"]["title"] == "Fix bug"
    assert wal["params"]["payload"]["project_id"] == "proj_P"


def test_work_item_create_execute():
    result = execute({"op": "pm.work_item.create", "payload": {"title": "Fix bug", "project_id": "proj_P"}, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "work_item.created"
    assert item["is_create"] is True
    assert item["payload"]["title"] == "Fix bug"
    assert item["fk_refs"] == [{"aggregate_type": "project", "aggregate_id": "proj_P"}]


# ── pm.work_item.update ───────────────────────────────────────────────

def test_work_item_update_plan():
    plan = compile("pm.work_item.update", {"work_item_id": "wi_T", "title": "New title"}, CTX)

    assert plan["ops"][0]["method"] == "assert.exists"
    assert plan["ops"][0]["params"]["aggregate_type"] == "work_item"
    wal = plan["ops"][1]
    assert wal["params"]["event_type"] == "work_item.updated"
    assert wal["params"]["payload"]["title"] == "New title"


def test_work_item_update_execute():
    result = execute({"op": "pm.work_item.update", "payload": {"work_item_id": "wi_T", "title": "New title"}, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "work_item.updated"
    assert item["is_create"] is False
    assert item["payload"]["title"] == "New title"


# ── pm.work_item.complete ─────────────────────────────────────────────

def test_work_item_complete_plan():
    plan = compile("pm.work_item.complete", {"work_item_id": "wi_T"}, CTX)

    assert plan["ops"][0]["method"] == "assert.exists"
    wal = plan["ops"][1]
    assert wal["params"]["event_type"] == "work_item.completed"
    assert wal["params"]["aggregate_id"] == "wi_T"


def test_work_item_complete_execute():
    result = execute({"op": "pm.work_item.complete", "payload": {"work_item_id": "wi_T"}, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "work_item.completed"
    assert item["is_create"] is False


# ── pm.work_item.move ─────────────────────────────────────────────────

def test_work_item_move_plan():
    plan = compile("pm.work_item.move", {"work_item_id": "wi_T", "project_id": "proj_DEST"}, CTX)

    methods = [op["method"] for op in plan["ops"]]
    assert methods == ["assert.exists", "assert.exists", "wal.append"]
    # First: work_item exists. Second: project FK exists.
    assert plan["ops"][0]["params"] == {"aggregate_type": "work_item", "aggregate_id": "wi_T"}
    assert plan["ops"][1]["params"] == {"aggregate_type": "project", "aggregate_id": "proj_DEST"}

    wal = plan["ops"][2]
    assert wal["params"]["event_type"] == "work_item.moved"
    assert wal["params"]["payload"]["project_id"] == "proj_DEST"


def test_work_item_move_execute():
    result = execute({"op": "pm.work_item.move", "payload": {"work_item_id": "wi_T", "project_id": "proj_DEST"}, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "work_item.moved"
    assert item["is_create"] is False
    assert item["fk_refs"] == [{"aggregate_type": "project", "aggregate_id": "proj_DEST"}]


# ── pm.work_item.cancel ───────────────────────────────────────────────

def test_work_item_cancel_plan():
    plan = compile("pm.work_item.cancel", {"work_item_id": "wi_T"}, CTX)

    assert plan["ops"][0]["method"] == "assert.exists"
    wal = plan["ops"][1]
    assert wal["params"]["event_type"] == "work_item.cancelled"
    assert wal["params"]["aggregate_id"] == "wi_T"


def test_work_item_cancel_execute():
    result = execute({"op": "pm.work_item.cancel", "payload": {"work_item_id": "wi_T"}, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "work_item.cancelled"
    assert item["is_create"] is False


# ── pm.deliverable.create ─────────────────────────────────────────────

def test_deliverable_create_plan():
    plan = compile("pm.deliverable.create", {"name": "Q1 Report", "project_id": "proj_P"}, CTX)

    assert plan["ops"][0]["method"] == "assert.exists"  # project FK
    assert plan["ops"][0]["params"]["aggregate_type"] == "project"

    wal = plan["ops"][1]
    assert wal["params"]["event_type"] == "deliverable.created"
    assert wal["params"]["aggregate_id"].startswith("del_")
    assert wal["params"]["payload"]["name"] == "Q1 Report"
    assert wal["params"]["payload"]["project_id"] == "proj_P"


def test_deliverable_create_execute():
    result = execute({"op": "pm.deliverable.create", "payload": {"name": "Q1 Report", "project_id": "proj_P"}, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "deliverable.created"
    assert item["is_create"] is True
    assert item["fk_refs"] == [{"aggregate_type": "project", "aggregate_id": "proj_P"}]


# ── pm.deliverable.update ─────────────────────────────────────────────

def test_deliverable_update_plan():
    plan = compile("pm.deliverable.update", {"deliverable_id": "del_T", "name": "Updated"}, CTX)

    assert plan["ops"][0]["method"] == "assert.exists"
    wal = plan["ops"][1]
    assert wal["params"]["event_type"] == "deliverable.updated"
    assert wal["params"]["payload"]["name"] == "Updated"


def test_deliverable_update_execute():
    result = execute({"op": "pm.deliverable.update", "payload": {"deliverable_id": "del_T", "name": "Updated"}, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "deliverable.updated"
    assert item["is_create"] is False


# ── pm.deliverable.complete ───────────────────────────────────────────

def test_deliverable_complete_plan():
    plan = compile("pm.deliverable.complete", {"deliverable_id": "del_T"}, CTX)

    assert plan["ops"][0]["method"] == "assert.exists"
    wal = plan["ops"][1]
    assert wal["params"]["event_type"] == "deliverable.completed"
    assert wal["params"]["aggregate_id"] == "del_T"


def test_deliverable_complete_execute():
    result = execute({"op": "pm.deliverable.complete", "payload": {"deliverable_id": "del_T"}, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "deliverable.completed"
    assert item["is_create"] is False


# ── pm.deliverable.reject ─────────────────────────────────────────────

def test_deliverable_reject_plan():
    plan = compile("pm.deliverable.reject", {"deliverable_id": "del_T"}, CTX)

    assert plan["ops"][0]["method"] == "assert.exists"
    wal = plan["ops"][1]
    assert wal["params"]["event_type"] == "deliverable.rejected"
    assert wal["params"]["aggregate_id"] == "del_T"


def test_deliverable_reject_execute():
    result = execute({"op": "pm.deliverable.reject", "payload": {"deliverable_id": "del_T"}, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "deliverable.rejected"
    assert item["is_create"] is False


# ── pm.opsstream.create ───────────────────────────────────────────────

def test_opsstream_create_plan():
    plan = compile("pm.opsstream.create", {"name": "Clinical Ops"}, CTX)

    assert len(plan["ops"]) == 1  # auto-gen ID, no FK
    wal = plan["ops"][0]
    assert wal["method"] == "wal.append"
    assert wal["params"]["event_type"] == "opsstream.created"
    assert wal["params"]["aggregate_type"] == "opsstream"
    assert wal["params"]["aggregate_id"].startswith("ops_")
    assert wal["params"]["payload"]["name"] == "Clinical Ops"


def test_opsstream_create_execute():
    result = execute({"op": "pm.opsstream.create", "payload": {"name": "Clinical Ops"}, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "opsstream.created"
    assert item["is_create"] is True
    assert item["aggregate_id"].startswith("ops_")
    assert item["payload"]["name"] == "Clinical Ops"
    assert item["fk_refs"] == []


# ── pm.opsstream.update ───────────────────────────────────────────────

def test_opsstream_update_plan():
    plan = compile("pm.opsstream.update", {"opsstream_id": "ops_T", "name": "Renamed"}, CTX)

    assert plan["ops"][0]["method"] == "assert.exists"
    wal = plan["ops"][1]
    assert wal["params"]["event_type"] == "opsstream.updated"
    assert wal["params"]["payload"]["name"] == "Renamed"


def test_opsstream_update_execute():
    result = execute({"op": "pm.opsstream.update", "payload": {"opsstream_id": "ops_T", "name": "Renamed"}, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "opsstream.updated"
    assert item["is_create"] is False


# ── pm.opsstream.close ────────────────────────────────────────────────

def test_opsstream_close_plan():
    plan = compile("pm.opsstream.close", {"opsstream_id": "ops_T"}, CTX)

    assert plan["ops"][0]["method"] == "assert.exists"
    wal = plan["ops"][1]
    assert wal["params"]["event_type"] == "opsstream.closed"
    assert wal["params"]["aggregate_id"] == "ops_T"


def test_opsstream_close_execute():
    result = execute({"op": "pm.opsstream.close", "payload": {"opsstream_id": "ops_T"}, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "opsstream.closed"
    assert item["is_create"] is False


# ── pm.artifact.create ────────────────────────────────────────────────

def test_artifact_create_plan():
    payload = {"title": "Session Note", "kind": "SESSION_NOTE", "work_item_id": "wi_P"}
    plan = compile("pm.artifact.create", payload, CTX)

    # auto-gen ID, one FK assert
    assert plan["ops"][0]["method"] == "assert.exists"
    assert plan["ops"][0]["params"] == {"aggregate_type": "work_item", "aggregate_id": "wi_P"}

    wal = plan["ops"][1]
    assert wal["params"]["event_type"] == "artifact.created"
    assert wal["params"]["aggregate_id"].startswith("art_")
    assert wal["params"]["payload"]["title"] == "Session Note"
    assert wal["params"]["payload"]["kind"] == "SESSION_NOTE"
    assert wal["params"]["payload"]["work_item_id"] == "wi_P"


def test_artifact_create_execute():
    payload = {"title": "Session Note", "kind": "SESSION_NOTE", "work_item_id": "wi_P"}
    result = execute({"op": "pm.artifact.create", "payload": payload, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "artifact.created"
    assert item["is_create"] is True
    assert item["payload"]["title"] == "Session Note"
    assert item["payload"]["kind"] == "SESSION_NOTE"
    assert item["fk_refs"] == [{"aggregate_type": "work_item", "aggregate_id": "wi_P"}]


def test_artifact_create_multi_fk():
    payload = {"title": "Doc", "kind": "REPORT", "work_item_id": "wi_T", "project_id": "proj_T"}
    plan = compile("pm.artifact.create", payload, CTX)
    exists_ops = [op for op in plan["ops"] if op["method"] == "assert.exists"]
    assert len(exists_ops) == 2
    fk_types = {op["params"]["aggregate_type"] for op in exists_ops}
    assert fk_types == {"work_item", "project"}


def test_artifact_create_requires_container_fk():
    from workman.errors import ValidationError
    with pytest.raises(ValidationError, match="at least one container FK"):
        compile("pm.artifact.create", {"title": "Orphan", "kind": "MEMO"}, CTX)


# ── pm.artifact.update ────────────────────────────────────────────────

def test_artifact_update_plan():
    plan = compile("pm.artifact.update", {"artifact_id": "art_T", "title": "Revised"}, CTX)

    assert plan["ops"][0]["method"] == "assert.exists"
    wal = plan["ops"][1]
    assert wal["params"]["event_type"] == "artifact.updated"
    assert wal["params"]["payload"]["title"] == "Revised"


def test_artifact_update_execute():
    result = execute({"op": "pm.artifact.update", "payload": {"artifact_id": "art_T", "title": "Revised"}, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "artifact.updated"
    assert item["is_create"] is False


# ── pm.artifact.finalize ──────────────────────────────────────────────

def test_artifact_finalize_plan():
    plan = compile("pm.artifact.finalize", {"artifact_id": "art_T"}, CTX)

    assert plan["ops"][0]["method"] == "assert.exists"
    wal = plan["ops"][1]
    assert wal["params"]["event_type"] == "artifact.finalized"
    assert wal["params"]["aggregate_id"] == "art_T"


def test_artifact_finalize_execute():
    result = execute({"op": "pm.artifact.finalize", "payload": {"artifact_id": "art_T"}, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "artifact.finalized"
    assert item["is_create"] is False


# ── pm.artifact.deliver ───────────────────────────────────────────────

def test_artifact_deliver_plan():
    payload = {"artifact_id": "art_T", "content_ref": "https://drive.google.com/doc/x", "delivered_via": "gdrive"}
    plan = compile("pm.artifact.deliver", payload, CTX)

    assert plan["ops"][0]["method"] == "assert.exists"
    wal = plan["ops"][1]
    assert wal["params"]["event_type"] == "artifact.delivered"
    assert wal["params"]["payload"]["content_ref"] == "https://drive.google.com/doc/x"
    assert wal["params"]["payload"]["delivered_via"] == "gdrive"


def test_artifact_deliver_execute():
    payload = {"artifact_id": "art_T", "content_ref": "https://drive.google.com/doc/x", "delivered_via": "gdrive"}
    result = execute({"op": "pm.artifact.deliver", "payload": payload, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "artifact.delivered"
    assert item["payload"]["delivered_via"] == "gdrive"
    assert item["payload"]["content_ref"] == "https://drive.google.com/doc/x"


# ── pm.artifact.defer ─────────────────────────────────────────────────

def test_artifact_defer_plan():
    plan = compile("pm.artifact.defer", {"artifact_id": "art_T"}, CTX)

    assert plan["ops"][0]["method"] == "assert.exists"
    wal = plan["ops"][1]
    assert wal["params"]["event_type"] == "artifact.deferred"
    assert wal["params"]["aggregate_id"] == "art_T"


def test_artifact_defer_execute():
    result = execute({"op": "pm.artifact.defer", "payload": {"artifact_id": "art_T"}, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "artifact.deferred"
    assert item["is_create"] is False


# ── pm.artifact.supersede ─────────────────────────────────────────────

def test_artifact_supersede_plan():
    plan = compile("pm.artifact.supersede", {"artifact_id": "art_T", "superseded_by_id": "art_NEW"}, CTX)

    assert plan["ops"][0]["method"] == "assert.exists"
    wal = plan["ops"][1]
    assert wal["params"]["event_type"] == "artifact.superseded"
    assert wal["params"]["payload"]["superseded_by_id"] == "art_NEW"


def test_artifact_supersede_execute():
    result = execute({"op": "pm.artifact.supersede", "payload": {"artifact_id": "art_T", "superseded_by_id": "art_NEW"}, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "artifact.superseded"
    assert item["payload"]["superseded_by_id"] == "art_NEW"


# ── pm.artifact.archive ───────────────────────────────────────────────

def test_artifact_archive_plan():
    plan = compile("pm.artifact.archive", {"artifact_id": "art_T"}, CTX)

    assert plan["ops"][0]["method"] == "assert.exists"
    wal = plan["ops"][1]
    assert wal["params"]["event_type"] == "artifact.archived"
    assert wal["params"]["aggregate_id"] == "art_T"


def test_artifact_archive_execute():
    result = execute({"op": "pm.artifact.archive", "payload": {"artifact_id": "art_T"}, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "artifact.archived"
    assert item["is_create"] is False


# ── link.create ────────────────────────────────────────────────────────

def test_link_create_plan():
    payload = {"from_atom_id": "wi_A", "to_atom_id": "wi_B", "predicate": "blocks"}
    plan = compile("link.create", payload, CTX)

    assert len(plan["ops"]) == 1  # auto-gen ID, no FKs
    wal = plan["ops"][0]
    assert wal["method"] == "wal.append"
    assert wal["params"]["event_type"] == "link.created"
    assert wal["params"]["aggregate_type"] == "link"
    assert wal["params"]["aggregate_id"].startswith("lnk_")
    assert wal["params"]["payload"]["from_atom_id"] == "wi_A"
    assert wal["params"]["payload"]["to_atom_id"] == "wi_B"
    assert wal["params"]["payload"]["predicate"] == "blocks"


def test_link_create_execute():
    payload = {"from_atom_id": "wi_A", "to_atom_id": "wi_B", "predicate": "blocks"}
    result = execute({"op": "link.create", "payload": payload, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "link.created"
    assert item["is_create"] is True
    assert item["aggregate_id"].startswith("lnk_")
    assert item["payload"]["predicate"] == "blocks"


# ── link.remove ────────────────────────────────────────────────────────

def test_link_remove_plan():
    payload = {"from_atom_id": "wi_A", "to_atom_id": "wi_B", "predicate": "blocks"}
    plan = compile("link.remove", payload, CTX)

    assert plan["ops"][0]["method"] == "assert.exists"
    assert plan["ops"][0]["params"]["aggregate_type"] == "link"

    wal = plan["ops"][1]
    assert wal["params"]["event_type"] == "link.removed"
    assert wal["params"]["payload"]["from_atom_id"] == "wi_A"
    assert wal["params"]["payload"]["predicate"] == "blocks"


def test_link_remove_execute():
    payload = {"from_atom_id": "wi_A", "to_atom_id": "wi_B", "predicate": "blocks"}
    result = execute({"op": "link.remove", "payload": payload, "ctx": CTX})
    item = result["items"][0]
    assert item["event_type"] == "link.removed"
    assert item["is_create"] is False
