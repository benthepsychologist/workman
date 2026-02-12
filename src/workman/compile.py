"""Plan compilation: the main workman entrypoint."""

from ulid import ULID

from workman.assertions import assert_exists, assert_not_exists, reset_assertion_counter
from workman.builders import build_wal_append, reset_write_counter
from workman.catalog import get_op_spec
from workman.errors import CompileError
from workman.ids import generate_id, make_idempotency_key
from workman.schema import resolve_schema, validate_payload


def compile(op: str, payload: dict, ctx: dict, pins: dict | None = None) -> dict:
    """Compile a domain operation into a Storacle execution plan.

    Note: compile() may mutate the input payload dict by injecting id_field.
    """

    reset_assertion_counter()
    reset_write_counter()

    op_spec = get_op_spec(op)
    if op_spec is None:
        raise CompileError(f"Unknown operation: {op}", op=op)

    schema = resolve_schema(op_spec.request_schema)
    validate_payload(payload, schema)

    # Artifact container FK validation: at least one container required
    if op == "pm.artifact.create":
        _CONTAINER_FKS = ("work_item_id", "deliverable_id", "project_id", "opsstream_id")
        if not any(payload.get(fk) for fk in _CONTAINER_FKS):
            from workman.errors import ValidationError
            raise ValidationError(
                "pm.artifact.create requires at least one container FK "
                "(work_item_id, deliverable_id, project_id, or opsstream_id)"
            )

    caller_supplied_id = op_spec.id_field in payload and payload[op_spec.id_field]
    if caller_supplied_id:
        aggregate_id = payload[op_spec.id_field]
    else:
        aggregate_id = pins.get("id") if pins and "id" in pins else generate_id(op_spec.id_prefix)
        payload[op_spec.id_field] = aggregate_id

    assertions: list[dict] = []
    if op_spec.is_create:
        if caller_supplied_id:
            assertions.append(assert_not_exists(op_spec.aggregate_type, aggregate_id))
    else:
        assertions.append(assert_exists(op_spec.aggregate_type, aggregate_id))

    for fk_field, fk_aggregate_type in op_spec.fk_asserts:
        if fk_field in payload and payload[fk_field]:
            assertions.append(assert_exists(fk_aggregate_type, payload[fk_field]))

    idempotency_key = make_idempotency_key(ctx, op, op_spec.aggregate_type, aggregate_id)
    wal_op = build_wal_append(
        idempotency_key=idempotency_key,
        event_type=op_spec.event_type,
        aggregate_type=op_spec.aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        ctx=ctx,
    )

    return {
        "plan_version": "storacle.plan/1.0.0",
        "plan_id": f"ulid:{ULID()}",
        "jsonrpc": "2.0",
        "meta": {"source": "workman", "op": op, "correlation_id": ctx.get("correlation_id")},
        "ops": assertions + [wal_op],
    }



