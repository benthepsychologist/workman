"""Tests for OpsStream operations."""

from workman.assertions import reset_assertion_counter
from workman.builders import reset_write_counter
from workman.catalog import OP_CATALOG
from workman.compile import compile
from workman.execute import execute


class TestOpsStreamCreate:
    def setup_method(self):
        reset_assertion_counter()
        reset_write_counter()

    def test_compile_minimal(self):
        plan = compile("pm.opsstream.create", {"name": "Clinical Ops"}, {})
        assert len(plan["ops"]) == 1  # no assert (auto-gen ID)
        wal = plan["ops"][0]
        assert wal["params"]["event_type"] == "opsstream.created"
        assert wal["params"]["aggregate_type"] == "opsstream"
        assert wal["params"]["aggregate_id"].startswith("ops_")

    def test_compile_full(self):
        payload = {
            "name": "Clinic Alpha",
            "type": "CLINICAL_OPS",
            "owner": "ben",
            "status": "ACTIVE",
            "description": "Main clinical stream",
            "meta": {"region": "east"},
        }
        plan = compile("pm.opsstream.create", payload, {})
        p = plan["ops"][0]["params"]["payload"]
        assert p["type"] == "CLINICAL_OPS"
        assert p["owner"] == "ben"
        assert p["meta"]["region"] == "east"

    def test_caller_supplied_id(self):
        plan = compile("pm.opsstream.create", {"opsstream_id": "ops_CUSTOM", "name": "Custom"}, {})
        assert len(plan["ops"]) == 2
        assert plan["ops"][0]["method"] == "assert.not_exists"
        assert plan["ops"][0]["params"]["aggregate_id"] == "ops_CUSTOM"

    def test_execute(self):
        result = execute({"op": "pm.opsstream.create", "payload": {"name": "Test"}, "ctx": {}})
        item = result["items"][0]
        assert item["event_type"] == "opsstream.created"
        assert item["is_create"] is True
        assert item["aggregate_id"].startswith("ops_")


class TestOpsStreamUpdate:
    def setup_method(self):
        reset_assertion_counter()
        reset_write_counter()

    def test_compile(self):
        plan = compile("pm.opsstream.update", {"opsstream_id": "ops_T", "name": "Updated"}, {})
        assert plan["ops"][0]["method"] == "assert.exists"
        assert plan["ops"][1]["params"]["event_type"] == "opsstream.updated"

    def test_partial_status_only(self):
        plan = compile("pm.opsstream.update", {"opsstream_id": "ops_T", "status": "PAUSED"}, {})
        assert plan["ops"][1]["params"]["payload"]["status"] == "PAUSED"

    def test_execute(self):
        result = execute({"op": "pm.opsstream.update", "payload": {"opsstream_id": "ops_T", "name": "U"}, "ctx": {}})
        assert result["items"][0]["event_type"] == "opsstream.updated"
        assert result["items"][0]["is_create"] is False


class TestOpsStreamCatalog:
    def test_create_spec(self):
        spec = OP_CATALOG["pm.opsstream.create"]
        assert spec.id_prefix == "ops"
        assert spec.aggregate_type == "opsstream"
        assert spec.is_create is True

    def test_update_spec(self):
        spec = OP_CATALOG["pm.opsstream.update"]
        assert spec.id_prefix == "ops"
        assert spec.is_create is False

    def test_close_spec(self):
        spec = OP_CATALOG["pm.opsstream.close"]
        assert spec.id_prefix == "ops"
        assert spec.is_create is False
        assert spec.event_type == "opsstream.closed"
