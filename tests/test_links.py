"""Tests for AKM link operations."""

from workman.assertions import reset_assertion_counter
from workman.builders import reset_write_counter
from workman.catalog import OP_CATALOG
from workman.compile import compile
from workman.execute import execute


class TestLinkCreate:
    def setup_method(self):
        reset_assertion_counter()
        reset_write_counter()

    def test_compile_minimal(self):
        payload = {
            "source_id": "wi_A",
            "source_type": "work_item",
            "target_id": "wi_B",
            "target_type": "work_item",
            "predicate": "BLOCKS",
        }
        plan = compile("link.create", payload, {})
        wal = [op for op in plan["ops"] if op["method"] == "wal.append"][0]
        assert wal["params"]["event_type"] == "link.created"
        assert wal["params"]["aggregate_type"] == "link"
        assert wal["params"]["aggregate_id"].startswith("lnk_")
        assert wal["params"]["payload"]["predicate"] == "BLOCKS"

        # Dynamic FK assertions: assert.exists for source and target
        exists_ops = [op for op in plan["ops"] if op["method"] == "assert.exists"]
        assert len(exists_ops) == 2
        assert exists_ops[0]["params"] == {"aggregate_type": "work_item", "aggregate_id": "wi_A"}
        assert exists_ops[1]["params"] == {"aggregate_type": "work_item", "aggregate_id": "wi_B"}

    def test_compile_caller_supplied_id(self):
        payload = {
            "link_id": "lnk_CUSTOM",
            "source_id": "proj_A",
            "source_type": "project",
            "target_id": "proj_B",
            "target_type": "project",
            "predicate": "DEPENDS_ON",
        }
        plan = compile("link.create", payload, {})
        not_exists = [op for op in plan["ops"] if op["method"] == "assert.not_exists"]
        assert len(not_exists) == 1
        assert not_exists[0]["params"]["aggregate_id"] == "lnk_CUSTOM"

    def test_compile_with_meta(self):
        payload = {
            "source_id": "wi_A",
            "source_type": "work_item",
            "target_id": "del_B",
            "target_type": "deliverable",
            "predicate": "RELATED_TO",
            "meta": {"weight": 0.8},
        }
        plan = compile("link.create", payload, {})
        wal = [op for op in plan["ops"] if op["method"] == "wal.append"][0]
        assert wal["params"]["payload"]["meta"]["weight"] == 0.8

    def test_execute(self):
        payload = {
            "source_id": "wi_A",
            "source_type": "work_item",
            "target_id": "wi_B",
            "target_type": "work_item",
            "predicate": "BLOCKS",
        }
        result = execute({"op": "link.create", "payload": payload, "ctx": {}})
        item = result["items"][0]
        assert item["event_type"] == "link.created"
        assert item["is_create"] is True
        assert item["aggregate_id"].startswith("lnk_")


class TestLinkRemove:
    def setup_method(self):
        reset_assertion_counter()
        reset_write_counter()

    def test_compile(self):
        plan = compile("link.remove", {"link_id": "lnk_T"}, {})
        assert plan["ops"][0]["method"] == "assert.exists"
        assert plan["ops"][0]["params"]["aggregate_type"] == "link"
        assert plan["ops"][1]["params"]["event_type"] == "link.removed"

    def test_compile_with_reason(self):
        plan = compile("link.remove", {"link_id": "lnk_T", "reason": "Invalid"}, {})
        assert plan["ops"][1]["params"]["payload"]["reason"] == "Invalid"

    def test_execute(self):
        result = execute({"op": "link.remove", "payload": {"link_id": "lnk_T"}, "ctx": {}})
        item = result["items"][0]
        assert item["event_type"] == "link.removed"
        assert item["is_create"] is False
        assert item["aggregate_id"] == "lnk_T"


class TestLinkCatalog:
    def test_link_ops_exist(self):
        assert "link.create" in OP_CATALOG
        assert "link.remove" in OP_CATALOG

    def test_link_create_spec(self):
        spec = OP_CATALOG["link.create"]
        assert spec.aggregate_type == "link"
        assert spec.id_prefix == "lnk"
        assert spec.id_field == "link_id"
        assert spec.event_type == "link.created"
        assert spec.is_create is True

    def test_link_remove_spec(self):
        spec = OP_CATALOG["link.remove"]
        assert spec.aggregate_type == "link"
        assert spec.id_prefix == "lnk"
        assert spec.id_field == "link_id"
        assert spec.event_type == "link.removed"
        assert spec.is_create is False

    def test_link_ops_have_no_static_fk_asserts(self):
        assert OP_CATALOG["link.create"].fk_asserts == []
        assert OP_CATALOG["link.remove"].fk_asserts == []

    def test_link_create_has_dynamic_fk_asserts(self):
        spec = OP_CATALOG["link.create"]
        assert spec.dynamic_fk_asserts == [("source_id", "source_type"), ("target_id", "target_type")]

    def test_link_remove_has_no_dynamic_fk_asserts(self):
        assert OP_CATALOG["link.remove"].dynamic_fk_asserts == []
