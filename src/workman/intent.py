"""PMIntent compilation: bulk operation processing with diff and plan hashing.

compile_intent() takes a PMIntent dict and returns a CallableResult
containing StoraclePlans, human-readable diff strings, and a SHA256 plan hash.
"""

from __future__ import annotations

import hashlib
import json
import re

from workman.compile import compile
from workman.errors import CompileError
from workman.catalog import get_op_spec

_REF_PATTERN = re.compile(r"^@ref:(\d+)$")

_REQUIRED_INTENT_FIELDS = ("intent_id", "ops", "source", "actor", "issued_at")


def compile_intent(intent: dict, ctx: dict | None = None) -> dict:
    """Compile a PMIntent into a CallableResult.

    Args:
        intent: PMIntent dict with intent_id, ops[], source, actor, issued_at.
        ctx: Optional execution context overrides.

    Returns:
        CallableResult dict:
        {
            "schema_version": "1.0",
            "items": [StoraclePlan, ...],
            "stats": {"input": N, "output": N, "skipped": 0, "errors": 0},
            "diff": ["CREATE work_item wi_01ABC (title='Fix bug', ...)"],
            "plan_hash": "sha256hex..."
        }

    Raises:
        CompileError: Invalid intent structure or unknown operation.
        ValidationError: Missing required fields or invalid payload.
    """
    _validate_intent_structure(intent)

    ops = intent["ops"]
    if len(ops) > 100:
        raise CompileError("PMIntent exceeds maximum of 100 ops", op="pm.compile_intent")

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

    for i, op_entry in enumerate(ops):
        op_name = op_entry["op"]
        payload = dict(op_entry.get("payload", {}))  # shallow copy to avoid mutation

        # Resolve @ref:N references
        payload = _resolve_refs(payload, generated_ids, i)

        # Compile the individual op
        plan = compile(op_name, payload, intent_ctx)
        plans.append(plan)

        # Extract the aggregate_id from the plan's wal.append op
        aggregate_id = _extract_aggregate_id(plan)
        generated_ids.append(aggregate_id)

        # Generate diff line
        diff_line = _make_diff_line(op_name, aggregate_id, payload)
        diff.append(diff_line)

    # Compute plan hash
    plan_hash = _compute_plan_hash(plans)

    return {
        "schema_version": "1.0",
        "items": plans,
        "stats": {
            "input": len(ops),
            "output": len(plans),
            "skipped": 0,
            "errors": 0,
        },
        "diff": diff,
        "plan_hash": plan_hash,
    }


def _validate_intent_structure(intent: dict) -> None:
    """Validate required PMIntent fields."""
    for field in _REQUIRED_INTENT_FIELDS:
        if field not in intent:
            raise CompileError(
                f"PMIntent missing required field: {field}",
                op="pm.compile_intent",
            )

    if not isinstance(intent["ops"], list) or len(intent["ops"]) == 0:
        raise CompileError(
            "PMIntent.ops must be a non-empty list",
            op="pm.compile_intent",
        )

    actor = intent.get("actor", {})
    if not isinstance(actor, dict) or "actor_type" not in actor or "actor_id" not in actor:
        raise CompileError(
            "PMIntent.actor must have actor_type and actor_id",
            op="pm.compile_intent",
        )

    for i, op_entry in enumerate(intent["ops"]):
        if "op" not in op_entry:
            raise CompileError(
                f"PMIntent.ops[{i}] missing 'op' field",
                op="pm.compile_intent",
            )
        if "payload" not in op_entry:
            raise CompileError(
                f"PMIntent.ops[{i}] missing 'payload' field",
                op="pm.compile_intent",
            )


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
