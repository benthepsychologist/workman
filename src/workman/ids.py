"""ID generation and idempotency key construction."""

from ulid import ULID


def generate_id(prefix: str) -> str:
    """Generate a ULID-based ID with a stable prefix.

    Returns:
        '{prefix}_{ulid}'
    """

    return f"{prefix}_{ULID()}"


def make_idempotency_key(
    ctx: dict,
    op: str,
    aggregate_type: str,
    aggregate_id: str,
) -> str:
    """Construct a deterministic idempotency key.

    Format: {producer}:{op}:{aggregate_type}:{aggregate_id}:{correlation_id}
    """

    producer = ctx.get("producer", "unknown")
    correlation_id = ctx.get("correlation_id", "unknown")
    return f"{producer}:{op}:{aggregate_type}:{aggregate_id}:{correlation_id}"
