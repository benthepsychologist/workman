"""Tests for workman.catalog module."""

import pytest

from workman.builders import generic_pm_builder
from workman.catalog import OP_CATALOG, OpSpec, get_op_spec


class TestOpSpec:
    """Tests for OpSpec dataclass."""

    def test_opspec_has_required_fields(self):
        """OpSpec should have all required fields."""
        spec = OpSpec(
            op="test.op",
            request_schema="iglu:test/schema/jsonschema/1-0-0",
            aggregate_type="test",
            id_prefix="tst",
            id_field="test_id",
            event_type="test.created",
            builder=generic_pm_builder,
        )
        assert spec.op == "test.op"
        assert spec.request_schema == "iglu:test/schema/jsonschema/1-0-0"
        assert spec.aggregate_type == "test"
        assert spec.id_prefix == "tst"
        assert spec.id_field == "test_id"
        assert spec.event_type == "test.created"
        assert spec.builder == generic_pm_builder

    def test_opspec_is_create_defaults_to_false(self):
        """OpSpec.is_create should default to False."""
        spec = OpSpec(
            op="test.op",
            request_schema="iglu:test/schema/jsonschema/1-0-0",
            aggregate_type="test",
            id_prefix="tst",
            id_field="test_id",
            event_type="test.created",
            builder=generic_pm_builder,
        )
        assert spec.is_create is False

    def test_opspec_fk_asserts_defaults_to_empty_list(self):
        """OpSpec.fk_asserts should default to empty list."""
        spec = OpSpec(
            op="test.op",
            request_schema="iglu:test/schema/jsonschema/1-0-0",
            aggregate_type="test",
            id_prefix="tst",
            id_field="test_id",
            event_type="test.created",
            builder=generic_pm_builder,
        )
        assert spec.fk_asserts == []

    def test_opspec_dynamic_fk_asserts_defaults_to_empty_list(self):
        """OpSpec.dynamic_fk_asserts should default to empty list."""
        spec = OpSpec(
            op="test.op",
            request_schema="iglu:test/schema/jsonschema/1-0-0",
            aggregate_type="test",
            id_prefix="tst",
            id_field="test_id",
            event_type="test.created",
            builder=generic_pm_builder,
        )
        assert spec.dynamic_fk_asserts == []

    def test_opspec_is_frozen(self):
        """OpSpec should be frozen (immutable)."""
        spec = OpSpec(
            op="test.op",
            request_schema="iglu:test/schema/jsonschema/1-0-0",
            aggregate_type="test",
            id_prefix="tst",
            id_field="test_id",
            event_type="test.created",
            builder=generic_pm_builder,
        )
        with pytest.raises(Exception):
            spec.op = "modified"


class TestOPCatalog:
    """Tests for OP_CATALOG registry."""

    def test_catalog_contains_pm_core_set(self):
        """Catalog should contain all PM core set v0.1 operations."""
        expected_ops = [
            "pm.project.create",
            "pm.project.close",
            "pm.work_item.create",
            "pm.work_item.complete",
            "pm.deliverable.create",
            "pm.deliverable.complete",
        ]
        for op in expected_ops:
            assert op in OP_CATALOG, f"Missing op: {op}"

    def test_all_ops_have_valid_namespace(self):
        """All ops should be under pm.* or link.* namespace."""
        for op_name in OP_CATALOG:
            assert op_name.startswith("pm.") or op_name.startswith("link."), (
                f"Op {op_name} not in pm.* or link.* namespace"
            )

    def test_all_ops_have_builder(self):
        """All ops should have a builder function."""
        for op_name, spec in OP_CATALOG.items():
            assert spec.builder is not None, f"Op {op_name} missing builder"
            assert callable(spec.builder), f"Op {op_name} builder not callable"


class TestProjectOps:
    """Tests for pm.project.* operations."""

    def test_project_create_spec(self):
        """pm.project.create should have correct spec."""
        spec = OP_CATALOG["pm.project.create"]
        assert spec.op == "pm.project.create"
        assert spec.request_schema == "iglu:org1.workman/pm.project.create/jsonschema/1-0-0"
        assert spec.aggregate_type == "project"
        assert spec.id_prefix == "proj"
        assert spec.id_field == "project_id"
        assert spec.event_type == "project.created"
        assert spec.is_create is True
        assert spec.fk_asserts == []
        assert spec.builder == generic_pm_builder

    def test_project_close_spec(self):
        """pm.project.close should have correct spec."""
        spec = OP_CATALOG["pm.project.close"]
        assert spec.op == "pm.project.close"
        assert spec.request_schema == "iglu:org1.workman/pm.project.close/jsonschema/1-0-0"
        assert spec.aggregate_type == "project"
        assert spec.id_prefix == "proj"
        assert spec.id_field == "project_id"
        assert spec.event_type == "project.closed"
        assert spec.is_create is False
        assert spec.fk_asserts == []
        assert spec.builder == generic_pm_builder


class TestWorkItemOps:
    """Tests for pm.work_item.* operations."""

    def test_work_item_create_spec(self):
        """pm.work_item.create should have correct spec."""
        spec = OP_CATALOG["pm.work_item.create"]
        assert spec.op == "pm.work_item.create"
        assert spec.request_schema == "iglu:org1.workman/pm.work_item.create/jsonschema/1-0-0"
        assert spec.aggregate_type == "work_item"
        assert spec.id_prefix == "wi"
        assert spec.id_field == "work_item_id"
        assert spec.event_type == "work_item.created"
        assert spec.is_create is True
        assert spec.fk_asserts == [("project_id", "project"), ("deliverable_id", "deliverable"), ("opsstream_id", "opsstream")]
        assert spec.builder == generic_pm_builder

    def test_work_item_complete_spec(self):
        """pm.work_item.complete should have correct spec."""
        spec = OP_CATALOG["pm.work_item.complete"]
        assert spec.op == "pm.work_item.complete"
        assert spec.request_schema == "iglu:org1.workman/pm.work_item.complete/jsonschema/1-0-0"
        assert spec.aggregate_type == "work_item"
        assert spec.id_prefix == "wi"
        assert spec.id_field == "work_item_id"
        assert spec.event_type == "work_item.completed"
        assert spec.is_create is False
        assert spec.fk_asserts == []
        assert spec.builder == generic_pm_builder


class TestDeliverableOps:
    """Tests for pm.deliverable.* operations."""

    def test_deliverable_create_spec(self):
        """pm.deliverable.create should have correct spec."""
        spec = OP_CATALOG["pm.deliverable.create"]
        assert spec.op == "pm.deliverable.create"
        assert spec.request_schema == "iglu:org1.workman/pm.deliverable.create/jsonschema/1-0-0"
        assert spec.aggregate_type == "deliverable"
        assert spec.id_prefix == "del"
        assert spec.id_field == "deliverable_id"
        assert spec.event_type == "deliverable.created"
        assert spec.is_create is True
        assert spec.fk_asserts == [("project_id", "project"), ("opsstream_id", "opsstream")]
        assert spec.builder == generic_pm_builder

    def test_deliverable_complete_spec(self):
        """pm.deliverable.complete should have correct spec."""
        spec = OP_CATALOG["pm.deliverable.complete"]
        assert spec.op == "pm.deliverable.complete"
        assert spec.request_schema == "iglu:org1.workman/pm.deliverable.complete/jsonschema/1-0-0"
        assert spec.aggregate_type == "deliverable"
        assert spec.id_prefix == "del"
        assert spec.id_field == "deliverable_id"
        assert spec.event_type == "deliverable.completed"
        assert spec.is_create is False
        assert spec.fk_asserts == []
        assert spec.builder == generic_pm_builder


class TestGetOpSpec:
    """Tests for get_op_spec function."""

    def test_returns_spec_for_valid_op(self):
        """get_op_spec should return OpSpec for valid operation."""
        spec = get_op_spec("pm.project.create")
        assert spec is not None
        assert spec.op == "pm.project.create"

    def test_returns_none_for_unknown_op(self):
        """get_op_spec should return None for unknown operation."""
        spec = get_op_spec("unknown.op")
        assert spec is None

    def test_returns_correct_spec_for_each_op(self):
        """get_op_spec should return correct spec for each registered op."""
        for op_name, expected_spec in OP_CATALOG.items():
            spec = get_op_spec(op_name)
            assert spec == expected_spec


class TestOpSpecIdField:
    """Tests for id_field configuration."""

    def test_create_ops_have_id_field(self):
        """Create ops should have id_field defined."""
        create_ops = [k for k, v in OP_CATALOG.items() if v.is_create]
        for op_name in create_ops:
            spec = OP_CATALOG[op_name]
            assert spec.id_field, f"Create op {op_name} missing id_field"

    def test_mutation_ops_have_id_field(self):
        """Mutation ops should have id_field defined."""
        mutation_ops = [k for k, v in OP_CATALOG.items() if not v.is_create]
        for op_name in mutation_ops:
            spec = OP_CATALOG[op_name]
            assert spec.id_field, f"Mutation op {op_name} missing id_field"

    def test_project_ops_use_project_id(self):
        """Project ops should use project_id as id_field."""
        project_ops = [k for k in OP_CATALOG if k.startswith("pm.project.")]
        for op_name in project_ops:
            spec = OP_CATALOG[op_name]
            assert spec.id_field == "project_id"

    def test_work_item_ops_use_work_item_id(self):
        """Work item ops should use work_item_id as id_field."""
        work_item_ops = [k for k in OP_CATALOG if k.startswith("pm.work_item.")]
        for op_name in work_item_ops:
            spec = OP_CATALOG[op_name]
            assert spec.id_field == "work_item_id"

    def test_deliverable_ops_use_deliverable_id(self):
        """Deliverable ops should use deliverable_id as id_field."""
        deliverable_ops = [k for k in OP_CATALOG if k.startswith("pm.deliverable.")]
        for op_name in deliverable_ops:
            spec = OP_CATALOG[op_name]
            assert spec.id_field == "deliverable_id"


class TestForeignKeyAsserts:
    """Tests for fk_asserts configuration."""

    def test_work_item_create_has_project_fk(self):
        """pm.work_item.create should assert project FK."""
        spec = OP_CATALOG["pm.work_item.create"]
        assert ("project_id", "project") in spec.fk_asserts

    def test_work_item_create_has_deliverable_fk(self):
        """pm.work_item.create should assert deliverable FK."""
        spec = OP_CATALOG["pm.work_item.create"]
        assert ("deliverable_id", "deliverable") in spec.fk_asserts

    def test_work_item_create_has_opsstream_fk(self):
        """pm.work_item.create should assert opsstream FK."""
        spec = OP_CATALOG["pm.work_item.create"]
        assert ("opsstream_id", "opsstream") in spec.fk_asserts

    def test_deliverable_create_has_project_fk(self):
        """pm.deliverable.create should assert project FK."""
        spec = OP_CATALOG["pm.deliverable.create"]
        assert ("project_id", "project") in spec.fk_asserts

    def test_deliverable_create_has_opsstream_fk(self):
        """pm.deliverable.create should assert opsstream FK."""
        spec = OP_CATALOG["pm.deliverable.create"]
        assert ("opsstream_id", "opsstream") in spec.fk_asserts

    def test_work_item_move_has_deliverable_fk(self):
        """pm.work_item.move should assert deliverable FK."""
        spec = OP_CATALOG["pm.work_item.move"]
        assert ("deliverable_id", "deliverable") in spec.fk_asserts

    def test_artifact_supersede_has_replacement_fk(self):
        """pm.artifact.supersede should assert superseded_by_id FK."""
        spec = OP_CATALOG["pm.artifact.supersede"]
        assert ("superseded_by_id", "artifact") in spec.fk_asserts

    def test_project_create_has_no_fk(self):
        """pm.project.create should have no FK assertions."""
        spec = OP_CATALOG["pm.project.create"]
        assert spec.fk_asserts == []

    def test_mutation_ops_have_no_fk_asserts(self):
        """Mutation ops (complete/close) should have no FK assertions."""
        mutation_ops = ["pm.project.close", "pm.work_item.complete", "pm.deliverable.complete"]
        for op_name in mutation_ops:
            spec = OP_CATALOG[op_name]
            assert spec.fk_asserts == [], f"Mutation op {op_name} should have no FK asserts"
