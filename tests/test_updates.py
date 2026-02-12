"""Tests for PM update/cancel/reject/close operations."""

from workman.assertions import reset_assertion_counter
from workman.builders import reset_write_counter
from workman.compile import compile
from workman.execute import execute


class TestWorkItemUpdate:
    def setup_method(self):
        reset_assertion_counter()
        reset_write_counter()

    def test_compile_minimal(self):
        payload = {"work_item_id": "wi_TEST", "title": "Updated"}
        plan = compile("pm.work_item.update", payload, {})
        assert plan["ops"][0]["method"] == "assert.exists"
        assert plan["ops"][0]["params"]["aggregate_type"] == "work_item"
        wal = plan["ops"][1]
        assert wal["params"]["event_type"] == "work_item.updated"
        assert wal["params"]["aggregate_id"] == "wi_TEST"

    def test_compile_all_fields(self):
        payload = {
            "work_item_id": "wi_TEST",
            "title": "New",
            "description": "Desc",
            "kind": "ISSUE",
            "state": "IN_PROGRESS",
            "priority": "HIGH",
            "severity": "MEDIUM",
            "labels": ["a", "b"],
            "assignees": ["ben"],
            "due_at": "2026-03-01T00:00:00Z",
            "time_estimate": 8,
            "time_spent": 2,
        }
        plan = compile("pm.work_item.update", payload, {})
        p = plan["ops"][1]["params"]["payload"]
        assert p["kind"] == "ISSUE"
        assert p["labels"] == ["a", "b"]
        assert p["time_spent"] == 2

    def test_execute(self):
        result = execute({"op": "pm.work_item.update", "payload": {"work_item_id": "wi_T", "title": "U"}, "ctx": {}})
        item = result["items"][0]
        assert item["event_type"] == "work_item.updated"
        assert item["is_create"] is False
        assert item["fk_refs"] == []


class TestProjectUpdate:
    def setup_method(self):
        reset_assertion_counter()
        reset_write_counter()

    def test_compile(self):
        plan = compile("pm.project.update", {"project_id": "proj_T", "name": "New"}, {})
        assert plan["ops"][0]["method"] == "assert.exists"
        assert plan["ops"][1]["params"]["event_type"] == "project.updated"

    def test_partial_status_only(self):
        plan = compile("pm.project.update", {"project_id": "proj_T", "status": "PAUSED"}, {})
        assert plan["ops"][1]["params"]["payload"]["status"] == "PAUSED"

    def test_execute(self):
        result = execute({"op": "pm.project.update", "payload": {"project_id": "proj_T", "name": "N"}, "ctx": {}})
        assert result["items"][0]["event_type"] == "project.updated"
        assert result["items"][0]["is_create"] is False


class TestDeliverableUpdate:
    def setup_method(self):
        reset_assertion_counter()
        reset_write_counter()

    def test_compile(self):
        plan = compile("pm.deliverable.update", {"deliverable_id": "del_T", "name": "New"}, {})
        assert plan["ops"][0]["method"] == "assert.exists"
        assert plan["ops"][1]["params"]["event_type"] == "deliverable.updated"

    def test_execute(self):
        result = execute({"op": "pm.deliverable.update", "payload": {"deliverable_id": "del_T", "name": "N"}, "ctx": {}})
        assert result["items"][0]["event_type"] == "deliverable.updated"
        assert result["items"][0]["is_create"] is False


class TestWorkItemCancel:
    def setup_method(self):
        reset_assertion_counter()
        reset_write_counter()

    def test_compile_minimal(self):
        plan = compile("pm.work_item.cancel", {"work_item_id": "wi_T"}, {})
        assert plan["ops"][0]["method"] == "assert.exists"
        assert plan["ops"][1]["params"]["event_type"] == "work_item.cancelled"

    def test_compile_with_reason(self):
        plan = compile("pm.work_item.cancel", {"work_item_id": "wi_T", "reason": "No longer needed"}, {})
        assert plan["ops"][1]["params"]["payload"]["reason"] == "No longer needed"

    def test_execute(self):
        result = execute({"op": "pm.work_item.cancel", "payload": {"work_item_id": "wi_T"}, "ctx": {}})
        assert result["items"][0]["event_type"] == "work_item.cancelled"
        assert result["items"][0]["is_create"] is False


class TestDeliverableReject:
    def setup_method(self):
        reset_assertion_counter()
        reset_write_counter()

    def test_compile(self):
        plan = compile("pm.deliverable.reject", {"deliverable_id": "del_T"}, {})
        assert plan["ops"][0]["method"] == "assert.exists"
        assert plan["ops"][1]["params"]["event_type"] == "deliverable.rejected"

    def test_with_reason(self):
        plan = compile("pm.deliverable.reject", {"deliverable_id": "del_T", "reason": "Quality"}, {})
        assert plan["ops"][1]["params"]["payload"]["reason"] == "Quality"

    def test_execute(self):
        result = execute({"op": "pm.deliverable.reject", "payload": {"deliverable_id": "del_T"}, "ctx": {}})
        assert result["items"][0]["event_type"] == "deliverable.rejected"
        assert result["items"][0]["is_create"] is False


class TestOpsStreamClose:
    def setup_method(self):
        reset_assertion_counter()
        reset_write_counter()

    def test_compile(self):
        plan = compile("pm.opsstream.close", {"opsstream_id": "ops_T"}, {})
        assert plan["ops"][0]["method"] == "assert.exists"
        assert plan["ops"][1]["params"]["event_type"] == "opsstream.closed"

    def test_with_reason(self):
        plan = compile("pm.opsstream.close", {"opsstream_id": "ops_T", "reason": "Done"}, {})
        assert plan["ops"][1]["params"]["payload"]["reason"] == "Done"

    def test_execute(self):
        result = execute({"op": "pm.opsstream.close", "payload": {"opsstream_id": "ops_T"}, "ctx": {}})
        assert result["items"][0]["event_type"] == "opsstream.closed"
        assert result["items"][0]["is_create"] is False


class TestAllUpdateOpsAssertExists:
    def setup_method(self):
        reset_assertion_counter()
        reset_write_counter()

    def test_all_generate_assert_exists(self):
        cases = [
            ("pm.work_item.update", {"work_item_id": "wi_T", "title": "U"}),
            ("pm.project.update", {"project_id": "proj_T", "name": "U"}),
            ("pm.deliverable.update", {"deliverable_id": "del_T", "name": "U"}),
            ("pm.work_item.cancel", {"work_item_id": "wi_T"}),
            ("pm.deliverable.reject", {"deliverable_id": "del_T"}),
            ("pm.opsstream.close", {"opsstream_id": "ops_T"}),
        ]
        for op, payload in cases:
            reset_assertion_counter()
            reset_write_counter()
            plan = compile(op, payload, {})
            assert plan["ops"][0]["method"] == "assert.exists", f"{op} should assert.exists"
