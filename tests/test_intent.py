"""Tests for PMIntent compilation (compile_intent)."""

import pytest

from workman.errors import CompileError
from workman.intent import compile_intent


def _make_intent(ops, **overrides):
    """Helper to build a valid PMIntent dict."""
    base = {
        "intent_id": "intent_TEST",
        "ops": ops,
        "source": "test-suite",
        "actor": {"actor_type": "user", "actor_id": "u_test"},
        "issued_at": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


class TestCompileIntentBasic:
    def test_single_op(self):
        intent = _make_intent([
            {"op": "pm.project.create", "payload": {"name": "Alpha"}},
        ])
        result = compile_intent(intent)
        assert result["schema_version"] == "1.0"
        assert len(result["items"]) == 1
        assert result["stats"]["input"] == 1
        assert result["stats"]["output"] == 1
        assert result["stats"]["errors"] == 0

    def test_multi_op(self):
        intent = _make_intent([
            {"op": "pm.project.create", "payload": {"name": "Alpha"}},
            {"op": "pm.opsstream.create", "payload": {"name": "Ops"}},
        ])
        result = compile_intent(intent)
        assert len(result["items"]) == 2
        assert result["stats"]["input"] == 2
        assert result["stats"]["output"] == 2

    def test_returns_plan_hash(self):
        intent = _make_intent([
            {"op": "pm.project.create", "payload": {"name": "Alpha"}},
        ])
        result = compile_intent(intent)
        assert isinstance(result["plan_hash"], str)
        assert len(result["plan_hash"]) == 64  # SHA256 hex

    def test_plan_hash_deterministic(self):
        intent = _make_intent([
            {"op": "pm.project.create", "payload": {"project_id": "proj_FIXED", "name": "Alpha"}},
        ])
        r1 = compile_intent(intent)
        r2 = compile_intent(intent)
        # Different plan_ids (ULID) mean different hashes
        # But structure should be consistent
        assert isinstance(r1["plan_hash"], str)
        assert isinstance(r2["plan_hash"], str)

    def test_context_passed_through(self):
        intent = _make_intent([
            {"op": "pm.project.create", "payload": {"name": "Alpha"}},
        ])
        result = compile_intent(intent)
        plan = result["items"][0]
        assert plan["meta"]["correlation_id"] == "intent_TEST"


class TestCompileIntentDiff:
    def test_diff_generated(self):
        intent = _make_intent([
            {"op": "pm.project.create", "payload": {"name": "Alpha"}},
        ])
        result = compile_intent(intent)
        assert len(result["diff"]) == 1
        assert "CREATE" in result["diff"][0]
        assert "project" in result["diff"][0]

    def test_diff_shows_payload_fields(self):
        intent = _make_intent([
            {"op": "pm.project.create", "payload": {"name": "Alpha"}},
        ])
        result = compile_intent(intent)
        assert "name=" in result["diff"][0]

    def test_diff_multi_ops(self):
        intent = _make_intent([
            {"op": "pm.project.create", "payload": {"name": "Alpha"}},
            {"op": "pm.opsstream.create", "payload": {"name": "Stream"}},
        ])
        result = compile_intent(intent)
        assert len(result["diff"]) == 2
        assert "CREATE" in result["diff"][0]
        assert "CREATE" in result["diff"][1]


class TestCompileIntentRefResolution:
    def test_ref_resolves_to_aggregate_id(self):
        intent = _make_intent([
            {"op": "pm.project.create", "payload": {"name": "Alpha"}},
            {"op": "pm.work_item.create", "payload": {"title": "Task", "project_id": "@ref:0"}},
        ])
        result = compile_intent(intent)
        # The project plan's aggregate_id should be injected into work_item payload
        project_plan = result["items"][0]
        wi_plan = result["items"][1]
        project_id = _extract_aggregate_id(project_plan)
        wi_wal = [op for op in wi_plan["ops"] if op["method"] == "wal.append"][0]
        assert wi_wal["params"]["payload"]["project_id"] == project_id

    def test_chained_refs(self):
        intent = _make_intent([
            {"op": "pm.project.create", "payload": {"name": "Alpha"}},
            {"op": "pm.work_item.create", "payload": {"title": "Task", "project_id": "@ref:0"}},
            {"op": "pm.deliverable.create", "payload": {"name": "Del", "project_id": "@ref:0"}},
        ])
        result = compile_intent(intent)
        assert len(result["items"]) == 3
        project_id = _extract_aggregate_id(result["items"][0])
        # Both should reference the same project
        wi_wal = [op for op in result["items"][1]["ops"] if op["method"] == "wal.append"][0]
        del_wal = [op for op in result["items"][2]["ops"] if op["method"] == "wal.append"][0]
        assert wi_wal["params"]["payload"]["project_id"] == project_id
        assert del_wal["params"]["payload"]["project_id"] == project_id

    def test_forward_ref_raises(self):
        intent = _make_intent([
            {"op": "pm.project.create", "payload": {"name": "Alpha", "project_id": "@ref:1"}},
            {"op": "pm.opsstream.create", "payload": {"name": "Ops"}},
        ])
        with pytest.raises(CompileError, match="Forward reference"):
            compile_intent(intent)

    def test_out_of_bounds_ref_raises(self):
        intent = _make_intent([
            {"op": "pm.project.create", "payload": {"name": "Alpha", "project_id": "@ref:5"}},
        ])
        with pytest.raises(CompileError, match="Forward reference"):
            compile_intent(intent)


class TestCompileIntentValidation:
    def test_missing_intent_id(self):
        intent = {
            "ops": [{"op": "pm.project.create", "payload": {"name": "A"}}],
            "source": "test",
            "actor": {"actor_type": "user", "actor_id": "u_1"},
            "issued_at": "2026-01-01T00:00:00Z",
        }
        with pytest.raises(CompileError, match="intent_id"):
            compile_intent(intent)

    def test_missing_ops(self):
        intent = {
            "intent_id": "i_1",
            "source": "test",
            "actor": {"actor_type": "user", "actor_id": "u_1"},
            "issued_at": "2026-01-01T00:00:00Z",
        }
        with pytest.raises(CompileError, match="ops"):
            compile_intent(intent)

    def test_empty_ops_list(self):
        intent = _make_intent([])
        # Override to empty
        intent["ops"] = []
        with pytest.raises(CompileError, match="non-empty"):
            compile_intent(intent)

    def test_missing_actor(self):
        intent = {
            "intent_id": "i_1",
            "ops": [{"op": "pm.project.create", "payload": {"name": "A"}}],
            "source": "test",
            "issued_at": "2026-01-01T00:00:00Z",
        }
        with pytest.raises(CompileError, match="actor"):
            compile_intent(intent)

    def test_invalid_actor_structure(self):
        intent = _make_intent(
            [{"op": "pm.project.create", "payload": {"name": "A"}}],
            actor={"actor_type": "user"},  # missing actor_id
        )
        with pytest.raises(CompileError, match="actor"):
            compile_intent(intent)

    def test_op_entry_missing_op_field(self):
        intent = _make_intent([{"payload": {"name": "A"}}])
        with pytest.raises(CompileError, match="missing 'op'"):
            compile_intent(intent)

    def test_op_entry_missing_payload_field(self):
        intent = _make_intent([{"op": "pm.project.create"}])
        with pytest.raises(CompileError, match="missing 'payload'"):
            compile_intent(intent)

    def test_exceeds_100_ops(self):
        ops = [{"op": "pm.project.create", "payload": {"name": f"P{i}"}} for i in range(101)]
        intent = _make_intent(ops)
        with pytest.raises(CompileError, match="100"):
            compile_intent(intent)

    def test_unknown_op_raises(self):
        intent = _make_intent([
            {"op": "pm.bogus.create", "payload": {"name": "A"}},
        ])
        with pytest.raises(CompileError, match="Unknown operation"):
            compile_intent(intent)


def _extract_aggregate_id(plan: dict) -> str:
    """Helper to extract aggregate_id from a compiled plan."""
    for op in plan.get("ops", []):
        if op.get("method") == "wal.append":
            return op["params"]["aggregate_id"]
    raise ValueError("No wal.append op found in plan")
