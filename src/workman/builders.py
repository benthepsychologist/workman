"""Builders for Storacle plan ops."""

from typing import Iterator

_write_counter: Iterator[int] = iter(range(1, 10000))


def _next_write_id() -> str:
    return f"w{next(_write_counter)}"


def reset_write_counter() -> None:
    global _write_counter
    _write_counter = iter(range(1, 10000))


def build_wal_append(
    *,
    idempotency_key: str,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict,
    ctx: dict,
) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": _next_write_id(),
        "method": "wal.append",
        "params": {
            "idempotency_key": idempotency_key,
            "event_type": event_type,
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "occurred_at": ctx.get("occurred_at"),
            "actor": ctx.get("actor"),
            "correlation_id": ctx.get("correlation_id"),
            "producer": ctx.get("producer"),
            "payload": payload,
        },
    }
