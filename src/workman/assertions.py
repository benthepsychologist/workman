"""Assertion op constructors for Storacle plans."""

from typing import Iterator

_assertion_counter: Iterator[int] = iter(range(1, 10000))


def _next_assertion_id() -> str:
    return f"a{next(_assertion_counter)}"


def reset_assertion_counter() -> None:
    global _assertion_counter
    _assertion_counter = iter(range(1, 10000))


def assert_exists(aggregate_type: str, aggregate_id: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": _next_assertion_id(),
        "method": "assert.exists",
        "params": {"aggregate_type": aggregate_type, "aggregate_id": aggregate_id},
    }


def assert_not_exists(aggregate_type: str, aggregate_id: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": _next_assertion_id(),
        "method": "assert.not_exists",
        "params": {"aggregate_type": aggregate_type, "aggregate_id": aggregate_id},
    }
