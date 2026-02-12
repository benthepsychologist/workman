"""PM Op Catalog: OpSpec definitions for the PM core set (v0.2).

v0.2: Added update/cancel/reject/close ops, OpsStream entity,
      Artifact lifecycle ops, AKM link ops.
"""

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
    # ── Project ──────────────────────────────────────────────
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
    "pm.project.update": OpSpec(
        op="pm.project.update",
        request_schema="iglu:org1.workman/pm.project.update/jsonschema/1-0-0",
        aggregate_type="project",
        id_prefix="proj",
        id_field="project_id",
        event_type="project.updated",
        builder=generic_pm_builder,
    ),
    # ── WorkItem ─────────────────────────────────────────────
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
        fk_asserts=[("project_id", "project"), ("opsstream_id", "opsstream")],
    ),
    "pm.work_item.update": OpSpec(
        op="pm.work_item.update",
        request_schema="iglu:org1.workman/pm.work_item.update/jsonschema/1-0-0",
        aggregate_type="work_item",
        id_prefix="wi",
        id_field="work_item_id",
        event_type="work_item.updated",
        builder=generic_pm_builder,
    ),
    "pm.work_item.cancel": OpSpec(
        op="pm.work_item.cancel",
        request_schema="iglu:org1.workman/pm.work_item.cancel/jsonschema/1-0-0",
        aggregate_type="work_item",
        id_prefix="wi",
        id_field="work_item_id",
        event_type="work_item.cancelled",
        builder=generic_pm_builder,
    ),
    # ── Deliverable ──────────────────────────────────────────
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
    "pm.deliverable.update": OpSpec(
        op="pm.deliverable.update",
        request_schema="iglu:org1.workman/pm.deliverable.update/jsonschema/1-0-0",
        aggregate_type="deliverable",
        id_prefix="del",
        id_field="deliverable_id",
        event_type="deliverable.updated",
        builder=generic_pm_builder,
    ),
    "pm.deliverable.reject": OpSpec(
        op="pm.deliverable.reject",
        request_schema="iglu:org1.workman/pm.deliverable.reject/jsonschema/1-0-0",
        aggregate_type="deliverable",
        id_prefix="del",
        id_field="deliverable_id",
        event_type="deliverable.rejected",
        builder=generic_pm_builder,
    ),
    # ── OpsStream ────────────────────────────────────────────
    "pm.opsstream.create": OpSpec(
        op="pm.opsstream.create",
        request_schema="iglu:org1.workman/pm.opsstream.create/jsonschema/1-0-0",
        aggregate_type="opsstream",
        id_prefix="ops",
        id_field="opsstream_id",
        event_type="opsstream.created",
        builder=generic_pm_builder,
        is_create=True,
    ),
    "pm.opsstream.update": OpSpec(
        op="pm.opsstream.update",
        request_schema="iglu:org1.workman/pm.opsstream.update/jsonschema/1-0-0",
        aggregate_type="opsstream",
        id_prefix="ops",
        id_field="opsstream_id",
        event_type="opsstream.updated",
        builder=generic_pm_builder,
    ),
    "pm.opsstream.close": OpSpec(
        op="pm.opsstream.close",
        request_schema="iglu:org1.workman/pm.opsstream.close/jsonschema/1-0-0",
        aggregate_type="opsstream",
        id_prefix="ops",
        id_field="opsstream_id",
        event_type="opsstream.closed",
        builder=generic_pm_builder,
    ),
    # ── Artifact ─────────────────────────────────────────────
    "pm.artifact.create": OpSpec(
        op="pm.artifact.create",
        request_schema="iglu:org1.workman/pm.artifact.create/jsonschema/1-0-0",
        aggregate_type="artifact",
        id_prefix="art",
        id_field="artifact_id",
        event_type="artifact.created",
        builder=generic_pm_builder,
        is_create=True,
        fk_asserts=[
            ("work_item_id", "work_item"),
            ("deliverable_id", "deliverable"),
            ("project_id", "project"),
            ("opsstream_id", "opsstream"),
        ],
    ),
    "pm.artifact.update": OpSpec(
        op="pm.artifact.update",
        request_schema="iglu:org1.workman/pm.artifact.update/jsonschema/1-0-0",
        aggregate_type="artifact",
        id_prefix="art",
        id_field="artifact_id",
        event_type="artifact.updated",
        builder=generic_pm_builder,
    ),
    "pm.artifact.finalize": OpSpec(
        op="pm.artifact.finalize",
        request_schema="iglu:org1.workman/pm.artifact.finalize/jsonschema/1-0-0",
        aggregate_type="artifact",
        id_prefix="art",
        id_field="artifact_id",
        event_type="artifact.finalized",
        builder=generic_pm_builder,
    ),
    "pm.artifact.deliver": OpSpec(
        op="pm.artifact.deliver",
        request_schema="iglu:org1.workman/pm.artifact.deliver/jsonschema/1-0-0",
        aggregate_type="artifact",
        id_prefix="art",
        id_field="artifact_id",
        event_type="artifact.delivered",
        builder=generic_pm_builder,
    ),
    "pm.artifact.defer": OpSpec(
        op="pm.artifact.defer",
        request_schema="iglu:org1.workman/pm.artifact.defer/jsonschema/1-0-0",
        aggregate_type="artifact",
        id_prefix="art",
        id_field="artifact_id",
        event_type="artifact.deferred",
        builder=generic_pm_builder,
    ),
    "pm.artifact.supersede": OpSpec(
        op="pm.artifact.supersede",
        request_schema="iglu:org1.workman/pm.artifact.supersede/jsonschema/1-0-0",
        aggregate_type="artifact",
        id_prefix="art",
        id_field="artifact_id",
        event_type="artifact.superseded",
        builder=generic_pm_builder,
    ),
    "pm.artifact.archive": OpSpec(
        op="pm.artifact.archive",
        request_schema="iglu:org1.workman/pm.artifact.archive/jsonschema/1-0-0",
        aggregate_type="artifact",
        id_prefix="art",
        id_field="artifact_id",
        event_type="artifact.archived",
        builder=generic_pm_builder,
    ),
    # ── AKM Links ────────────────────────────────────────────
    "link.create": OpSpec(
        op="link.create",
        request_schema="iglu:org1.workman/link.create/jsonschema/1-0-0",
        aggregate_type="link",
        id_prefix="lnk",
        id_field="link_id",
        event_type="link.created",
        builder=generic_pm_builder,
        is_create=True,
    ),
    "link.remove": OpSpec(
        op="link.remove",
        request_schema="iglu:org1.workman/link.remove/jsonschema/1-0-0",
        aggregate_type="link",
        id_prefix="lnk",
        id_field="link_id",
        event_type="link.removed",
        builder=generic_pm_builder,
    ),
}


def get_op_spec(op: str) -> OpSpec | None:
    return OP_CATALOG.get(op)
