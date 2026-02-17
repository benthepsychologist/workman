"""PMIntent compilation: envelope generation and bulk operation processing.

compile_intent() accepts raw operation data and generates the PMIntent envelope
internally (intent_id + issued_at), then compiles ops against the PM schema.
Returns a CallableResult containing the generated intent, StoraclePlans,
human-readable diff strings, and a SHA256 plan hash.

Supports single-op (op_name + payload) and multi-op (ops list) modes.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

from ulid import ULID

from workman.compile import compile
from workman.errors import CompileError
from workman.catalog import get_op_spec

_REF_PATTERN = re.compile(r"^@ref:(\d+)$")

_VALID_ACTOR_TYPES = ("human", "system", "ai")


def compile_intent(
    *,
    op_name: str | None = None,
    payload: dict | None = None,
    ops: list[dict] | None = None,
    source: str,
    actor: dict,
    ctx: dict | None = None,
) -> dict:
    """Compile PM operations from raw data by constructing intent envelope and validating against schema.

    Accepts either a single op (op_name + payload) or a list of ops.
    Generates the PMIntent envelope internally (intent_id, issued_at).

    Args:
        op_name: Single-op mode — the PM operation name (e.g., 'pm.work_item.create').
        payload: Single-op mode — operation-specific payload fields.
        ops: Multi-op mode — list of {"op": str, "payload": dict} dicts.
        source: Source of the operation (e.g., 'life-cli', 'system').
        actor: Actor who initiated the operation {'actor_type': str, 'actor_id': str}.
        ctx: Optional execution context overrides.

    Returns:
        CallableResult dict with items[0] containing intent, plan, diff, plan_hash.

    Raises:
        CompileError: If parameters are invalid or compilation fails.
    """
    # Validate source
    if not source or not isinstance(source, str):
        raise CompileError("source must be a non-empty string", op="pm.compile_intent")

    # Validate actor
    if not isinstance(actor, dict):
        raise CompileError("actor must be a dict", op="pm.compile_intent")
    if "actor_type" not in actor:
        raise CompileError("actor must have actor_type field", op="pm.compile_intent")
    if "actor_id" not in actor:
        raise CompileError("actor must have actor_id field", op="pm.compile_intent")
    if actor["actor_type"] not in _VALID_ACTOR_TYPES:
        raise CompileError(
            f"actor_type must be one of {_VALID_ACTOR_TYPES}, got '{actor['actor_type']}'",
            op="pm.compile_intent",
        )

    # Resolve ops list — either from single-op params or multi-op list
    if ops is not None and op_name is not None:
        raise CompileError("Pass either (op_name, payload) or ops, not both", op="pm.compile_intent")

    if ops is not None:
        if not isinstance(ops, list) or len(ops) == 0:
            raise CompileError("ops must be a non-empty list", op="pm.compile_intent")
        intent_ops = ops
    elif op_name is not None:
        if not op_name or not isinstance(op_name, str):
            raise CompileError("op_name must be a non-empty string", op="pm.compile_intent")
        if not isinstance(payload, dict):
            raise CompileError("payload must be a dict", op="pm.compile_intent")
        intent_ops = [{"op": op_name, "payload": payload}]
    else:
        raise CompileError("Must provide either (op_name, payload) or ops", op="pm.compile_intent")

    if len(intent_ops) > 100:
        raise CompileError("PMIntent exceeds maximum of 100 ops", op="pm.compile_intent")

    # Generate intent envelope
    intent_id = f"pmi_{ULID()}"
    issued_at = datetime.now(timezone.utc).isoformat()

    intent = {
        "intent_id": intent_id,
        "ops": intent_ops,
        "source": source,
        "actor": actor,
        "issued_at": issued_at,
    }

    ops = intent["ops"]

    # Build context from intent
    intent_ctx = {
        "correlation_id": intent["intent_id"],
        "producer": intent["source"],
        "actor": intent.get("actor"),
        "occurred_at": intent.get("issued_at"),
    }
    if ctx:
        intent_ctx.update(ctx)

    plans: list[dict] = []
    diff: list[str] = []
    generated_ids: list[str] = []  # aggregate_id per op index
    prior_ops: list[tuple[str, dict, str]] = []  # (op_name, payload, aggregate_id)

    for i, op_entry in enumerate(ops):
        entry_op_name = op_entry["op"]
        entry_payload = dict(op_entry.get("payload", {}))  # shallow copy to avoid mutation

        # Resolve @ref:N references
        entry_payload = _resolve_refs(entry_payload, generated_ids, i)

        # Resolve inheritance (auto-fill parent container fields)
        _resolve_inheritance(entry_op_name, entry_payload, prior_ops)

        # Compile the individual op
        plan = compile(entry_op_name, entry_payload, intent_ctx)
        plans.append(plan)

        # Extract the aggregate_id from the plan's wal.append op
        aggregate_id = _extract_aggregate_id(plan)
        generated_ids.append(aggregate_id)
        prior_ops.append((entry_op_name, entry_payload, aggregate_id))

        # Generate diff line
        diff_line = _make_diff_line(entry_op_name, aggregate_id, entry_payload)
        diff.append(diff_line)

    # Merge all individual plans into a single StoraclePlan
    all_ops = []
    for plan in plans:
        all_ops.extend(plan["ops"])

    # Renumber IDs for uniqueness across the merged plan
    a_count = 0
    w_count = 0
    for op_entry_merged in all_ops:
        if op_entry_merged["method"].startswith("assert"):
            a_count += 1
            op_entry_merged["id"] = f"a{a_count}"
        else:
            w_count += 1
            op_entry_merged["id"] = f"w{w_count}"

    merged_plan = {
        "plan_version": "storacle.plan/1.0.0",
        "plan_id": f"ulid:{ULID()}",
        "jsonrpc": "2.0",
        "meta": {
            "source": "workman",
            "op": "pm.compile_intent",
            "correlation_id": intent["intent_id"],
        },
        "ops": all_ops,
    }

    # Compute plan hash over the merged plan
    plan_hash = _compute_plan_hash([merged_plan])

    return {
        "schema_version": "1.0",
        "items": [{
            "intent": intent,
            "plan": merged_plan,
            "diff": diff,
            "plan_hash": plan_hash,
        }],
        "stats": {
            "input": len(ops),
            "output": len(ops),
            "skipped": 0,
            "errors": 0,
        },
    }


def _resolve_refs(payload: dict, generated_ids: list[str], current_index: int) -> dict:
    """Replace @ref:N tokens with actual aggregate IDs from earlier ops."""
    resolved = {}
    for key, value in payload.items():
        if isinstance(value, str):
            match = _REF_PATTERN.match(value)
            if match:
                ref_str = match.group(0)
                try:
                    ref_index = int(match.group(1))
                except ValueError:
                    raise CompileError(
                        f"Malformed reference {ref_str} - must be @ref:N where N is integer",
                        op="pm.compile_intent",
                    )

                if ref_index >= current_index:
                    raise CompileError(
                        f"Forward reference @ref:{ref_index} not allowed in op {current_index}",
                        op="pm.compile_intent",
                    )

                if ref_index >= len(generated_ids):
                    raise CompileError(
                        f"Invalid @ref:{ref_index} in op {current_index} - only {len(generated_ids)} ops available",
                        op="pm.compile_intent",
                    )

                resolved[key] = generated_ids[ref_index]
            else:
                resolved[key] = value
        else:
            resolved[key] = value
    return resolved


def _extract_aggregate_id(plan: dict) -> str:
    """Extract the aggregate_id from a compiled plan's wal.append op."""
    for op in plan.get("ops", []):
        if op.get("method") == "wal.append":
            return op["params"]["aggregate_id"]
    raise CompileError("Plan has no wal.append op", op="pm.compile_intent")


def _make_diff_line(op_name: str, aggregate_id: str, payload: dict) -> str:
    """Generate a human-readable diff line for an operation."""
    op_spec = get_op_spec(op_name)
    if op_spec is None:
        return f"UNKNOWN {op_name} {aggregate_id}"

    # Determine verb from op action
    action = op_name.rsplit(".", 1)[-1] if "." in op_name else op_name
    verb = action.upper()

    # Build summary of key payload fields (exclude the ID field itself)
    parts = []
    for key, value in payload.items():
        if key == op_spec.id_field:
            continue
        if isinstance(value, str) and len(value) > 50:
            value = value[:47] + "..."
        parts.append(f"{key}={value!r}")

    summary = ", ".join(parts[:6])  # cap at 6 fields for readability
    return f"{verb} {op_spec.aggregate_type} {aggregate_id} ({summary})"


def _compute_plan_hash(plans: list[dict]) -> str:
    """Compute SHA256 hash of serialized plans for integrity verification."""
    serialized = json.dumps(plans, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _resolve_inheritance(op_name: str, payload: dict, prior_ops: list[tuple[str, dict, str]]) -> None:
    """Anchor-based container inheritance (ADR-002).

    Hierarchy: OpsStream -> Project -> Deliverable -> WorkItem
    Rule: your lowest assigned container is your anchor. You can change at or
    below your anchor (higher containers auto-fill), but you cannot set any
    container field above your anchor.
    """

    if op_name in ("pm.work_item.create", "pm.work_item.move"):
        del_id = payload.get("deliverable_id")
        if del_id:
            # Deliverable is the anchor — auto-fill project (overwrites any explicit value).
            # If the deliverable has no project, clear the work item's project too.
            found, parent_project = _find_parent_field(prior_ops, del_id, "project_id")
            if found:
                if parent_project:
                    payload["project_id"] = parent_project
                else:
                    payload.pop("project_id", None)

    if op_name == "pm.work_item.move":
        # Reverse check: can't reassign above your anchor
        wi_id = payload.get("work_item_id")
        if wi_id and not payload.get("deliverable_id"):
            # No deliverable in this move — check if work item has one from prior ops
            current_del = _find_entity_field(prior_ops, wi_id, "deliverable_id")
            if current_del:
                if payload.get("project_id"):
                    raise CompileError(
                        f"Cannot reassign project: work_item {wi_id} is anchored to "
                        f"deliverable {current_del}. Change deliverable instead, or "
                        f"detach first.",
                        op=op_name,
                    )
                if payload.get("opsstream_id"):
                    raise CompileError(
                        f"Cannot reassign opsstream: work_item {wi_id} is anchored "
                        f"to deliverable {current_del}. Change deliverable instead, "
                        f"or detach first.",
                        op=op_name,
                    )

        if wi_id and not payload.get("deliverable_id") and not payload.get("project_id"):
            # No deliverable or project in this move — check if work item has a project
            current_proj = _find_entity_field(prior_ops, wi_id, "project_id")
            if current_proj and payload.get("opsstream_id"):
                raise CompileError(
                    f"Cannot reassign opsstream: work_item {wi_id} is anchored to "
                    f"project {current_proj}. Change project instead, or detach first.",
                    op=op_name,
                )

    if op_name in ("pm.work_item.create", "pm.work_item.move",
                    "pm.deliverable.create"):
        # project → opsstream auto-fill
        proj_id = payload.get("project_id")
        if proj_id:
            found, parent_ops = _find_parent_field(prior_ops, proj_id, "opsstream_id")
            if found:
                if parent_ops:
                    payload["opsstream_id"] = parent_ops
                else:
                    payload.pop("opsstream_id", None)


def _find_parent_field(prior_ops: list[tuple[str, dict, str]], entity_id: str, field_name: str) -> tuple[bool, str | None]:
    """Look up a field from a prior op's payload by aggregate_id.

    Returns (found, value) — found=True means the entity exists in prior_ops,
    value may be None if the entity doesn't have that field.
    """
    for prev_op_name, prev_payload, prev_aggregate_id in prior_ops:
        if prev_aggregate_id == entity_id:
            return True, prev_payload.get(field_name)
    return False, None


def _find_entity_field(prior_ops: list[tuple[str, dict, str]], entity_id: str, field_name: str) -> str | None:
    """Find the most recent value of a field for an entity across prior ops."""
    result = None
    for _, prev_payload, prev_aggregate_id in prior_ops:
        if prev_aggregate_id == entity_id and field_name in prev_payload:
            result = prev_payload[field_name]
    return result
