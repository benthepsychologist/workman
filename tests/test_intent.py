"""Tests for PMIntent compilation (compile_intent)."""

import re

import pytest

from workman.errors import CompileError
from workman.intent import compile_intent


_ACTOR = {"actor_type": "human", "actor_id": "u_test"}


def _compile(**kwargs):
    """Shorthand: inject default source/actor if not provided."""
    kwargs.setdefault("source", "test-suite")
    kwargs.setdefault("actor", _ACTOR)
    return compile_intent(**kwargs)


class TestCompileIntentBasic:
    def test_single_op(self):
        result = _compile(op_name="pm.project.create", payload={"name": "Alpha"})
        assert result["schema_version"] == "1.0"
        assert len(result["items"]) == 1
        envelope = result["items"][0]
        assert "intent" in envelope
        assert "plan" in envelope
        assert "diff" in envelope
        assert "plan_hash" in envelope
        assert result["stats"]["input"] == 1
        assert result["stats"]["output"] == 1
        assert result["stats"]["errors"] == 0

    def test_multi_op(self):
        result = _compile(ops=[
            {"op": "pm.project.create", "payload": {"name": "Alpha"}},
            {"op": "pm.opsstream.create", "payload": {"name": "Ops"}},
        ])
        assert len(result["items"]) == 1
        merged_plan = result["items"][0]["plan"]
        wal_ops = [op for op in merged_plan["ops"] if op["method"] == "wal.append"]
        assert len(wal_ops) == 2
        assert result["stats"]["input"] == 2
        assert result["stats"]["output"] == 2

    def test_returns_plan_hash(self):
        result = _compile(op_name="pm.project.create", payload={"name": "Alpha"})
        plan_hash = result["items"][0]["plan_hash"]
        assert isinstance(plan_hash, str)
        assert len(plan_hash) == 64  # SHA256 hex

    def test_plan_hash_deterministic(self):
        result = _compile(
            op_name="pm.project.create",
            payload={"project_id": "proj_FIXED", "name": "Alpha"},
        )
        assert isinstance(result["items"][0]["plan_hash"], str)

    def test_context_passed_through(self):
        result = _compile(op_name="pm.project.create", payload={"name": "Alpha"})
        plan = result["items"][0]["plan"]
        assert plan["meta"]["correlation_id"] == result["items"][0]["intent"]["intent_id"]
        assert plan["meta"]["op"] == "pm.compile_intent"

    def test_merged_plan_structure(self):
        result = _compile(op_name="pm.project.create", payload={"name": "Alpha"})
        plan = result["items"][0]["plan"]
        assert plan["plan_version"] == "storacle.plan/1.0.0"
        assert plan["jsonrpc"] == "2.0"
        assert plan["plan_id"].startswith("ulid:")
        assert plan["meta"]["source"] == "workman"

    def test_merged_plan_renumbers_ids(self):
        result = _compile(ops=[
            {"op": "pm.project.create", "payload": {"name": "Alpha"}},
            {"op": "pm.opsstream.create", "payload": {"name": "Ops"}},
        ])
        plan = result["items"][0]["plan"]
        ids = [op["id"] for op in plan["ops"]]
        assert_ids = [i for i in ids if i.startswith("a")]
        write_ids = [i for i in ids if i.startswith("w")]
        assert assert_ids == [f"a{i}" for i in range(1, len(assert_ids) + 1)]
        assert write_ids == [f"w{i}" for i in range(1, len(write_ids) + 1)]


class TestCompileIntentDiff:
    def test_diff_generated(self):
        result = _compile(op_name="pm.project.create", payload={"name": "Alpha"})
        diff = result["items"][0]["diff"]
        assert len(diff) == 1
        assert "CREATE" in diff[0]
        assert "project" in diff[0]

    def test_diff_shows_payload_fields(self):
        result = _compile(op_name="pm.project.create", payload={"name": "Alpha"})
        diff = result["items"][0]["diff"]
        assert "name=" in diff[0]

    def test_diff_multi_ops(self):
        result = _compile(ops=[
            {"op": "pm.project.create", "payload": {"name": "Alpha"}},
            {"op": "pm.opsstream.create", "payload": {"name": "Stream"}},
        ])
        diff = result["items"][0]["diff"]
        assert len(diff) == 2
        assert "CREATE" in diff[0]
        assert "CREATE" in diff[1]


class TestCompileIntentEnvelopeGeneration:
    def test_intent_returned_in_result(self):
        result = _compile(op_name="pm.project.create", payload={"name": "Alpha"})
        intent = result["items"][0]["intent"]
        assert "intent_id" in intent
        assert "ops" in intent
        assert "source" in intent
        assert "actor" in intent
        assert "issued_at" in intent

    def test_intent_id_has_pmi_prefix_and_ulid(self):
        result = _compile(op_name="pm.project.create", payload={"name": "Alpha"})
        intent_id = result["items"][0]["intent"]["intent_id"]
        assert intent_id.startswith("pmi_")
        ulid_part = intent_id[4:]
        assert len(ulid_part) == 26
        assert re.match(r"^[0-9A-Z]{26}$", ulid_part)

    def test_issued_at_is_iso8601_utc(self):
        result = _compile(op_name="pm.project.create", payload={"name": "Alpha"})
        issued_at = result["items"][0]["intent"]["issued_at"]
        assert "+00:00" in issued_at

    def test_ops_wraps_single_operation(self):
        result = _compile(
            op_name="pm.work_item.create",
            payload={"title": "Task", "project_id": "proj_P"},
            source="life-cli",
        )
        ops = result["items"][0]["intent"]["ops"]
        assert len(ops) == 1
        assert ops[0]["op"] == "pm.work_item.create"
        assert ops[0]["payload"]["title"] == "Task"

    def test_source_preserved(self):
        result = _compile(
            op_name="pm.project.create", payload={"name": "Alpha"}, source="life-cli",
        )
        assert result["items"][0]["intent"]["source"] == "life-cli"

    def test_actor_preserved(self):
        actor = {"actor_type": "ai", "actor_id": "agent_001"}
        result = _compile(
            op_name="pm.project.create", payload={"name": "Alpha"}, actor=actor,
        )
        assert result["items"][0]["intent"]["actor"] == actor

    def test_unique_intent_ids(self):
        ids = set()
        for _ in range(10):
            result = _compile(op_name="pm.project.create", payload={"name": "Alpha"})
            ids.add(result["items"][0]["intent"]["intent_id"])
        assert len(ids) == 10

    def test_multi_op_intent_has_all_ops(self):
        result = _compile(ops=[
            {"op": "pm.project.create", "payload": {"name": "Alpha"}},
            {"op": "pm.opsstream.create", "payload": {"name": "Ops"}},
        ])
        intent = result["items"][0]["intent"]
        assert len(intent["ops"]) == 2


class TestCompileIntentRefResolution:
    def test_ref_resolves_to_aggregate_id(self):
        result = _compile(ops=[
            {"op": "pm.project.create", "payload": {"name": "Alpha"}},
            {"op": "pm.work_item.create", "payload": {"title": "Task", "project_id": "@ref:0"}},
        ])
        plan = result["items"][0]["plan"]
        wal_ops = [op for op in plan["ops"] if op["method"] == "wal.append"]
        project_id = wal_ops[0]["params"]["aggregate_id"]
        assert wal_ops[1]["params"]["payload"]["project_id"] == project_id

    def test_chained_refs(self):
        result = _compile(ops=[
            {"op": "pm.project.create", "payload": {"name": "Alpha"}},
            {"op": "pm.work_item.create", "payload": {"title": "Task", "project_id": "@ref:0"}},
            {"op": "pm.deliverable.create", "payload": {"name": "Del", "project_id": "@ref:0"}},
        ])
        plan = result["items"][0]["plan"]
        wal_ops = [op for op in plan["ops"] if op["method"] == "wal.append"]
        project_id = wal_ops[0]["params"]["aggregate_id"]
        assert wal_ops[1]["params"]["payload"]["project_id"] == project_id
        assert wal_ops[2]["params"]["payload"]["project_id"] == project_id

    def test_forward_ref_raises(self):
        with pytest.raises(CompileError, match="Forward reference"):
            _compile(ops=[
                {"op": "pm.project.create", "payload": {"name": "Alpha", "project_id": "@ref:1"}},
                {"op": "pm.opsstream.create", "payload": {"name": "Ops"}},
            ])

    def test_out_of_bounds_ref_raises(self):
        with pytest.raises(CompileError, match="Forward reference"):
            _compile(ops=[
                {"op": "pm.project.create", "payload": {"name": "Alpha", "project_id": "@ref:5"}},
            ])


class TestCompileIntentInheritance:
    def test_work_item_inherits_project_from_deliverable(self):
        result = _compile(ops=[
            {"op": "pm.project.create", "payload": {"name": "Alpha"}},
            {"op": "pm.deliverable.create", "payload": {"name": "Del", "project_id": "@ref:0"}},
            {"op": "pm.work_item.create", "payload": {"title": "Task", "deliverable_id": "@ref:1"}},
        ])
        plan = result["items"][0]["plan"]
        wal_ops = [op for op in plan["ops"] if op["method"] == "wal.append"]
        project_id = wal_ops[0]["params"]["aggregate_id"]
        wi_payload = wal_ops[2]["params"]["payload"]
        assert wi_payload["project_id"] == project_id

    def test_deliverable_overwrites_explicit_project(self):
        result = _compile(ops=[
            {"op": "pm.project.create", "payload": {"name": "Alpha"}},
            {"op": "pm.project.create", "payload": {"name": "Beta"}},
            {"op": "pm.deliverable.create", "payload": {"name": "Del", "project_id": "@ref:1"}},
            {"op": "pm.work_item.create", "payload": {"title": "Task", "deliverable_id": "@ref:2", "project_id": "@ref:0"}},
        ])
        plan = result["items"][0]["plan"]
        wal_ops = [op for op in plan["ops"] if op["method"] == "wal.append"]
        beta_id = wal_ops[1]["params"]["aggregate_id"]
        wi_payload = wal_ops[3]["params"]["payload"]
        assert wi_payload["project_id"] == beta_id

    def test_explicit_matching_project_is_ok(self):
        result = _compile(ops=[
            {"op": "pm.project.create", "payload": {"name": "Alpha"}},
            {"op": "pm.deliverable.create", "payload": {"name": "Del", "project_id": "@ref:0"}},
            {"op": "pm.work_item.create", "payload": {"title": "Task", "deliverable_id": "@ref:1", "project_id": "@ref:0"}},
        ])
        assert result["stats"]["output"] == 3

    def test_no_inheritance_when_parent_not_in_prior_ops(self):
        result = _compile(ops=[
            {"op": "pm.work_item.create", "payload": {"title": "Task", "deliverable_id": "del_EXTERNAL", "project_id": "proj_GIVEN"}},
        ])
        plan = result["items"][0]["plan"]
        wal_ops = [op for op in plan["ops"] if op["method"] == "wal.append"]
        assert wal_ops[0]["params"]["payload"]["project_id"] == "proj_GIVEN"

    def test_move_to_different_deliverable_changes_project(self):
        result = _compile(ops=[
            {"op": "pm.project.create", "payload": {"name": "Alpha"}},
            {"op": "pm.project.create", "payload": {"name": "Beta"}},
            {"op": "pm.deliverable.create", "payload": {"name": "D-A", "project_id": "@ref:0"}},
            {"op": "pm.deliverable.create", "payload": {"name": "D-B", "project_id": "@ref:1"}},
            {"op": "pm.work_item.create", "payload": {"title": "Task", "deliverable_id": "@ref:2"}},
            {"op": "pm.work_item.move", "payload": {"work_item_id": "@ref:4", "deliverable_id": "@ref:3"}},
        ])
        plan = result["items"][0]["plan"]
        wal_ops = [op for op in plan["ops"] if op["method"] == "wal.append"]
        beta_id = wal_ops[1]["params"]["aggregate_id"]
        move_payload = wal_ops[5]["params"]["payload"]
        assert move_payload["project_id"] == beta_id

    def test_move_project_blocked_by_deliverable_anchor(self):
        with pytest.raises(CompileError, match="Cannot reassign project"):
            _compile(ops=[
                {"op": "pm.project.create", "payload": {"name": "Alpha"}},
                {"op": "pm.project.create", "payload": {"name": "Beta"}},
                {"op": "pm.deliverable.create", "payload": {"name": "Del", "project_id": "@ref:0"}},
                {"op": "pm.work_item.create", "payload": {"title": "Task", "deliverable_id": "@ref:2"}},
                {"op": "pm.work_item.move", "payload": {"work_item_id": "@ref:3", "project_id": "@ref:1"}},
            ])

    def test_deliverable_with_no_project_clears_work_item_project(self):
        result = _compile(ops=[
            {"op": "pm.project.create", "payload": {"name": "Alpha"}},
            {"op": "pm.deliverable.create", "payload": {"name": "Orphan Del"}},
            {"op": "pm.work_item.create", "payload": {"title": "Task", "project_id": "@ref:0", "deliverable_id": "@ref:1"}},
        ])
        plan = result["items"][0]["plan"]
        wal_ops = [op for op in plan["ops"] if op["method"] == "wal.append"]
        wi_payload = wal_ops[2]["params"]["payload"]
        assert "project_id" not in wi_payload or not wi_payload.get("project_id")


class TestCompileIntentValidation:
    def test_empty_op_name_raises(self):
        with pytest.raises(CompileError, match="op_name must be a non-empty string"):
            _compile(op_name="", payload={"name": "A"})

    def test_payload_not_dict_raises(self):
        with pytest.raises(CompileError, match="payload must be a dict"):
            _compile(op_name="pm.project.create", payload="not-a-dict")

    def test_empty_source_raises(self):
        with pytest.raises(CompileError, match="source must be a non-empty string"):
            compile_intent(
                op_name="pm.project.create",
                payload={"name": "A"},
                source="",
                actor=_ACTOR,
            )

    def test_actor_not_dict_raises(self):
        with pytest.raises(CompileError, match="actor must be a dict"):
            compile_intent(
                op_name="pm.project.create",
                payload={"name": "A"},
                source="test",
                actor="not-a-dict",
            )

    def test_missing_actor_type_raises(self):
        with pytest.raises(CompileError, match="actor_type"):
            compile_intent(
                op_name="pm.project.create",
                payload={"name": "A"},
                source="test",
                actor={"actor_id": "u_1"},
            )

    def test_missing_actor_id_raises(self):
        with pytest.raises(CompileError, match="actor_id"):
            compile_intent(
                op_name="pm.project.create",
                payload={"name": "A"},
                source="test",
                actor={"actor_type": "human"},
            )

    def test_invalid_actor_type_raises(self):
        with pytest.raises(CompileError, match="actor_type must be one of"):
            compile_intent(
                op_name="pm.project.create",
                payload={"name": "A"},
                source="test",
                actor={"actor_type": "robot", "actor_id": "r_1"},
            )

    def test_valid_actor_types_accepted(self):
        for actor_type in ("human", "system", "ai"):
            result = compile_intent(
                op_name="pm.project.create",
                payload={"name": "A"},
                source="test",
                actor={"actor_type": actor_type, "actor_id": "u_1"},
            )
            assert result["schema_version"] == "1.0"

    def test_unknown_op_raises(self):
        with pytest.raises(CompileError, match="Unknown operation"):
            _compile(op_name="pm.bogus.create", payload={"name": "A"})

    def test_both_op_name_and_ops_raises(self):
        with pytest.raises(CompileError, match="not both"):
            _compile(
                op_name="pm.project.create",
                payload={"name": "A"},
                ops=[{"op": "pm.project.create", "payload": {"name": "A"}}],
            )

    def test_neither_op_name_nor_ops_raises(self):
        with pytest.raises(CompileError, match="Must provide"):
            compile_intent(source="test", actor=_ACTOR)

    def test_empty_ops_list_raises(self):
        with pytest.raises(CompileError, match="non-empty"):
            _compile(ops=[])

    def test_exceeds_100_ops(self):
        ops = [{"op": "pm.project.create", "payload": {"name": f"P{i}"}} for i in range(101)]
        with pytest.raises(CompileError, match="100"):
            _compile(ops=ops)
