"""PM Op Catalog: OpSpec definitions for the PM core set (v0.1)."""

from dataclasses import dataclass, field
from typing import Callable

from workman.builders import generic_pm_builder


@dataclass(frozen=True)
class OpSpec:
    op: str
    request_schema: str
    aggregate_type: str
    id_prefix: str
    id_field: str
    event_type: str
    builder: Callable[..., dict]
    is_create: bool = False
    fk_asserts: list[tuple[str, str]] = field(default_factory=list)


OP_CATALOG: dict[str, OpSpec] = {
    "pm.project.create": OpSpec(
        op="pm.project.create",
        request_schema="iglu:org1.workman/pm.project.create/jsonschema/1-0-0",
        aggregate_type="project",
        id_prefix="proj",
        id_field="project_id",
        event_type="project.created",
        builder=generic_pm_builder,
        is_create=True,
    ),
    "pm.project.close": OpSpec(
        op="pm.project.close",
        request_schema="iglu:org1.workman/pm.project.close/jsonschema/1-0-0",
        aggregate_type="project",
        id_prefix="proj",
        id_field="project_id",
        event_type="project.closed",
        builder=generic_pm_builder,
    ),
    "pm.work_item.create": OpSpec(
        op="pm.work_item.create",
        request_schema="iglu:org1.workman/pm.work_item.create/jsonschema/1-0-0",
        aggregate_type="work_item",
        id_prefix="wi",
        id_field="work_item_id",
        event_type="work_item.created",
        builder=generic_pm_builder,
        is_create=True,
        fk_asserts=[("project_id", "project")],
    ),
    "pm.work_item.complete": OpSpec(
        op="pm.work_item.complete",
        request_schema="iglu:org1.workman/pm.work_item.complete/jsonschema/1-0-0",
        aggregate_type="work_item",
        id_prefix="wi",
        id_field="work_item_id",
        event_type="work_item.completed",
        builder=generic_pm_builder,
    ),
    "pm.work_item.move": OpSpec(
        op="pm.work_item.move",
        request_schema="iglu:org1.workman/pm.work_item.move/jsonschema/1-0-0",
        aggregate_type="work_item",
        id_prefix="wi",
        id_field="work_item_id",
        event_type="work_item.moved",
        builder=generic_pm_builder,
        fk_asserts=[("project_id", "project")],
    ),
    "pm.deliverable.create": OpSpec(
        op="pm.deliverable.create",
        request_schema="iglu:org1.workman/pm.deliverable.create/jsonschema/1-0-0",
        aggregate_type="deliverable",
        id_prefix="del",
        id_field="deliverable_id",
        event_type="deliverable.created",
        builder=generic_pm_builder,
        is_create=True,
        fk_asserts=[("project_id", "project")],
    ),
    "pm.deliverable.complete": OpSpec(
        op="pm.deliverable.complete",
        request_schema="iglu:org1.workman/pm.deliverable.complete/jsonschema/1-0-0",
        aggregate_type="deliverable",
        id_prefix="del",
        id_field="deliverable_id",
        event_type="deliverable.completed",
        builder=generic_pm_builder,
    ),
}


def get_op_spec(op: str) -> OpSpec | None:
    return OP_CATALOG.get(op)
