"""Execute: Callable Protocol interface for workman.

Returns CallableResult with domain event items.
workman is the keeper of work primitives - it knows domain event shapes
but does NOT know storage semantics.
"""

from workman.catalog import get_op_spec
from workman.errors import CompileError
from workman.ids import generate_id, make_idempotency_key
from workman.schema import resolve_schema, validate_payload


def execute(params: dict) -> dict:
    """Process domain operation and return domain event items.

    Args:
        params: {
            "op": "pm.project.create",
            "payload": {...},
            "ctx": {"correlation_id": "...", "actor": "...", "producer": "..."}
        }

    Returns:
        CallableResult dict with domain event items:
        {
            "schema_version": "1.0",
            "items": [
                {
                    "event_type": "project.created",
                    "aggregate_type": "project",
                    "aggregate_id": "proj_01ABC...",
                    "payload": {...},
                    "idempotency_key": "...",
                    "is_create": True,
                    "fk_refs": [...]
                }
            ],
            "stats": {"input": 1, "output": 1, "skipped": 0, "errors": 0}
        }

    Raises:
        CompileError: Unknown operation
        ValidationError: Schema/payload validation failure
    """
    op = params["op"]

    # Route meta-ops that aren't individual PM catalog entries
    if op == "pm.compile_intent":
        from workman.intent import compile_intent
        kwargs = {
            "source": params["source"],
            "actor": params["actor"],
            "ctx": params.get("ctx"),
        }
        if "ops" in params:
            kwargs["ops"] = params["ops"]
        else:
            kwargs["op_name"] = params["op_name"]
            kwargs["payload"] = params["payload"]
        return compile_intent(**kwargs)

    payload = params["payload"]
    ctx = params.get("ctx", {})

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

    # Generate aggregate ID if not provided
    caller_supplied_id = bool(op_spec.id_field in payload and payload[op_spec.id_field])
    if caller_supplied_id:
        aggregate_id = payload[op_spec.id_field]
    else:
        aggregate_id = generate_id(op_spec.id_prefix)
        payload[op_spec.id_field] = aggregate_id

    idempotency_key = make_idempotency_key(ctx, op, op_spec.aggregate_type, aggregate_id)

    # Build FK refs for lorchestra to use for assertions
    fk_refs = []
    for fk_field, fk_aggregate_type in op_spec.fk_asserts:
        if fk_field in payload and payload[fk_field]:
            fk_refs.append({
                "aggregate_type": fk_aggregate_type,
                "aggregate_id": payload[fk_field],
            })

    # Build domain event item (NOT a StoraclePlan op)
    event_item = {
        "event_type": op_spec.event_type,
        "aggregate_type": op_spec.aggregate_type,
        "aggregate_id": aggregate_id,
        "payload": payload,
        "idempotency_key": idempotency_key,
        "is_create": op_spec.is_create,
        "caller_supplied_id": caller_supplied_id,
        "fk_refs": fk_refs,
    }

    return {
        "schema_version": "1.0",
        "items": [event_item],
        "stats": {"input": 1, "output": 1, "skipped": 0, "errors": 0},
    }
