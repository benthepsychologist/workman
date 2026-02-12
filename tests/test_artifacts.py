"""Tests for PM artifact lifecycle operations."""

import pytest

from workman.assertions import reset_assertion_counter
from workman.builders import reset_write_counter
from workman.catalog import OP_CATALOG
from workman.compile import compile
from workman.errors import ValidationError
from workman.execute import execute


class TestArtifactCreate:
    def setup_method(self):
        reset_assertion_counter()
        reset_write_counter()

    def test_compile_with_work_item(self):
        payload = {"name": "Design Doc", "kind": "DOCUMENT", "work_item_id": "wi_T"}
        plan = compile("pm.artifact.create", payload, {})
        wal = [op for op in plan["ops"] if op["method"] == "wal.append"][0]
        assert wal["params"]["event_type"] == "artifact.created"
        assert wal["params"]["aggregate_id"].startswith("art_")
        assert wal["params"]["payload"]["kind"] == "DOCUMENT"

    def test_compile_with_project(self):
        payload = {"name": "Spec", "kind": "DOCUMENT", "project_id": "proj_T"}
        plan = compile("pm.artifact.create", payload, {})
        wal = [op for op in plan["ops"] if op["method"] == "wal.append"][0]
        assert wal["params"]["event_type"] == "artifact.created"

    def test_compile_with_deliverable(self):
        payload = {"name": "Report", "kind": "DOCUMENT", "deliverable_id": "del_T"}
        plan = compile("pm.artifact.create", payload, {})
        wal = [op for op in plan["ops"] if op["method"] == "wal.append"][0]
        assert wal["params"]["event_type"] == "artifact.created"

    def test_compile_with_opsstream(self):
        payload = {"name": "Runbook", "kind": "DOCUMENT", "opsstream_id": "ops_T"}
        plan = compile("pm.artifact.create", payload, {})
        wal = [op for op in plan["ops"] if op["method"] == "wal.append"][0]
        assert wal["params"]["event_type"] == "artifact.created"

    def test_compile_requires_container_fk(self):
        payload = {"name": "Orphan", "kind": "DOCUMENT"}
        with pytest.raises(ValidationError, match="at least one container FK"):
            compile("pm.artifact.create", payload, {})

    def test_compile_fk_assertions(self):
        payload = {
            "name": "Doc",
            "kind": "DOCUMENT",
            "work_item_id": "wi_T",
            "project_id": "proj_T",
        }
        plan = compile("pm.artifact.create", payload, {})
        assert_ops = [op for op in plan["ops"] if op["method"] == "assert.exists"]
        fk_types = {op["params"]["aggregate_type"] for op in assert_ops}
        assert "work_item" in fk_types
        assert "project" in fk_types

    def test_compile_caller_supplied_id(self):
        payload = {"artifact_id": "art_CUSTOM", "name": "Doc", "kind": "DOCUMENT", "work_item_id": "wi_T"}
        plan = compile("pm.artifact.create", payload, {})
        not_exists = [op for op in plan["ops"] if op["method"] == "assert.not_exists"]
        assert len(not_exists) == 1
        assert not_exists[0]["params"]["aggregate_id"] == "art_CUSTOM"

    def test_execute(self):
        result = execute({
            "op": "pm.artifact.create",
            "payload": {"name": "Doc", "kind": "DOCUMENT", "work_item_id": "wi_T"},
            "ctx": {},
        })
        item = result["items"][0]
        assert item["event_type"] == "artifact.created"
        assert item["is_create"] is True
        assert item["aggregate_id"].startswith("art_")
        assert any(r["aggregate_type"] == "work_item" for r in item["fk_refs"])

    def test_execute_requires_container_fk(self):
        with pytest.raises(ValidationError, match="at least one container FK"):
            execute({
                "op": "pm.artifact.create",
                "payload": {"name": "Orphan", "kind": "DOCUMENT"},
                "ctx": {},
            })


class TestArtifactUpdate:
    def setup_method(self):
        reset_assertion_counter()
        reset_write_counter()

    def test_compile(self):
        plan = compile("pm.artifact.update", {"artifact_id": "art_T", "name": "Updated"}, {})
        assert plan["ops"][0]["method"] == "assert.exists"
        assert plan["ops"][1]["params"]["event_type"] == "artifact.updated"

    def test_execute(self):
        result = execute({"op": "pm.artifact.update", "payload": {"artifact_id": "art_T", "name": "U"}, "ctx": {}})
        assert result["items"][0]["event_type"] == "artifact.updated"
        assert result["items"][0]["is_create"] is False


class TestArtifactFinalize:
    def setup_method(self):
        reset_assertion_counter()
        reset_write_counter()

    def test_compile(self):
        plan = compile("pm.artifact.finalize", {"artifact_id": "art_T"}, {})
        assert plan["ops"][0]["method"] == "assert.exists"
        assert plan["ops"][1]["params"]["event_type"] == "artifact.finalized"

    def test_execute(self):
        result = execute({"op": "pm.artifact.finalize", "payload": {"artifact_id": "art_T"}, "ctx": {}})
        assert result["items"][0]["event_type"] == "artifact.finalized"
        assert result["items"][0]["is_create"] is False


class TestArtifactDeliver:
    def setup_method(self):
        reset_assertion_counter()
        reset_write_counter()

    def test_compile(self):
        plan = compile("pm.artifact.deliver", {"artifact_id": "art_T"}, {})
        assert plan["ops"][0]["method"] == "assert.exists"
        assert plan["ops"][1]["params"]["event_type"] == "artifact.delivered"

    def test_compile_with_delivered_via(self):
        plan = compile("pm.artifact.deliver", {"artifact_id": "art_T", "delivered_via": "EMAIL"}, {})
        assert plan["ops"][1]["params"]["payload"]["delivered_via"] == "EMAIL"

    def test_execute(self):
        result = execute({"op": "pm.artifact.deliver", "payload": {"artifact_id": "art_T"}, "ctx": {}})
        assert result["items"][0]["event_type"] == "artifact.delivered"


class TestArtifactDefer:
    def setup_method(self):
        reset_assertion_counter()
        reset_write_counter()

    def test_compile(self):
        plan = compile("pm.artifact.defer", {"artifact_id": "art_T"}, {})
        assert plan["ops"][0]["method"] == "assert.exists"
        assert plan["ops"][1]["params"]["event_type"] == "artifact.deferred"

    def test_compile_with_reason(self):
        plan = compile("pm.artifact.defer", {"artifact_id": "art_T", "reason": "Blocked"}, {})
        assert plan["ops"][1]["params"]["payload"]["reason"] == "Blocked"

    def test_execute(self):
        result = execute({"op": "pm.artifact.defer", "payload": {"artifact_id": "art_T"}, "ctx": {}})
        assert result["items"][0]["event_type"] == "artifact.deferred"


class TestArtifactSupersede:
    def setup_method(self):
        reset_assertion_counter()
        reset_write_counter()

    def test_compile(self):
        plan = compile("pm.artifact.supersede", {"artifact_id": "art_T"}, {})
        assert plan["ops"][0]["method"] == "assert.exists"
        assert plan["ops"][1]["params"]["event_type"] == "artifact.superseded"

    def test_compile_with_superseded_by(self):
        plan = compile("pm.artifact.supersede", {"artifact_id": "art_T", "superseded_by": "art_NEW"}, {})
        assert plan["ops"][1]["params"]["payload"]["superseded_by"] == "art_NEW"

    def test_execute(self):
        result = execute({"op": "pm.artifact.supersede", "payload": {"artifact_id": "art_T"}, "ctx": {}})
        assert result["items"][0]["event_type"] == "artifact.superseded"


class TestArtifactArchive:
    def setup_method(self):
        reset_assertion_counter()
        reset_write_counter()

    def test_compile(self):
        plan = compile("pm.artifact.archive", {"artifact_id": "art_T"}, {})
        assert plan["ops"][0]["method"] == "assert.exists"
        assert plan["ops"][1]["params"]["event_type"] == "artifact.archived"

    def test_execute(self):
        result = execute({"op": "pm.artifact.archive", "payload": {"artifact_id": "art_T"}, "ctx": {}})
        assert result["items"][0]["event_type"] == "artifact.archived"
        assert result["items"][0]["is_create"] is False


class TestArtifactCatalog:
    def test_all_artifact_ops_exist(self):
        expected = [
            "pm.artifact.create",
            "pm.artifact.update",
            "pm.artifact.finalize",
            "pm.artifact.deliver",
            "pm.artifact.defer",
            "pm.artifact.supersede",
            "pm.artifact.archive",
        ]
        for op in expected:
            assert op in OP_CATALOG, f"Missing artifact op: {op}"

    def test_all_use_art_prefix(self):
        for name, spec in OP_CATALOG.items():
            if name.startswith("pm.artifact."):
                assert spec.id_prefix == "art"
                assert spec.id_field == "artifact_id"
                assert spec.aggregate_type == "artifact"

    def test_only_create_is_create(self):
        for name, spec in OP_CATALOG.items():
            if name.startswith("pm.artifact."):
                if name == "pm.artifact.create":
                    assert spec.is_create is True
                else:
                    assert spec.is_create is False, f"{name} should not be is_create"

    def test_create_has_container_fk_asserts(self):
        spec = OP_CATALOG["pm.artifact.create"]
        fk_fields = [f for f, _ in spec.fk_asserts]
        assert "work_item_id" in fk_fields
        assert "deliverable_id" in fk_fields
        assert "project_id" in fk_fields
        assert "opsstream_id" in fk_fields

    def test_mutation_ops_have_no_fk_asserts(self):
        mutation_ops = [
            "pm.artifact.update",
            "pm.artifact.finalize",
            "pm.artifact.deliver",
            "pm.artifact.defer",
            "pm.artifact.supersede",
            "pm.artifact.archive",
        ]
        for op_name in mutation_ops:
            spec = OP_CATALOG[op_name]
            assert spec.fk_asserts == [], f"{op_name} should have no FK asserts"
