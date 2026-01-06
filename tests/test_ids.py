"""Tests for workman.ids module."""

import re

from workman.ids import generate_id, make_idempotency_key


class TestGenerateId:
    """Tests for generate_id function."""

    def test_returns_string_with_prefix_and_ulid(self):
        """Should return a string in format {prefix}_{ulid}."""
        result = generate_id("wi")
        assert result.startswith("wi_")
        # ULID is 26 characters
        ulid_part = result[3:]
        assert len(ulid_part) == 26

    def test_ulid_format_is_valid(self):
        """ULID part should be valid Crockford Base32."""
        result = generate_id("test")
        ulid_part = result.split("_", 1)[1]
        # Crockford Base32: uppercase letters (excluding I, L, O, U) and digits
        assert re.match(r"^[0-9A-HJKMNP-TV-Z]{26}$", ulid_part)

    def test_generates_unique_ids(self):
        """Each call should produce a unique ID."""
        ids = {generate_id("wi") for _ in range(100)}
        assert len(ids) == 100

    def test_preserves_prefix_exactly(self):
        """Prefix should be preserved exactly as provided."""
        prefixes = ["wi", "op", "evt", "task_item"]
        for prefix in prefixes:
            result = generate_id(prefix)
            assert result.startswith(f"{prefix}_")


class TestMakeIdempotencyKey:
    """Tests for make_idempotency_key function."""

    def test_produces_correct_format(self):
        """Should produce {producer}:{op}:{aggregate_type}:{aggregate_id}:{correlation_id}."""
        ctx = {"producer": "api", "correlation_id": "corr-123"}
        result = make_idempotency_key(ctx, "create", "work_item", "wi_01ARZ")
        assert result == "api:create:work_item:wi_01ARZ:corr-123"

    def test_uses_unknown_for_missing_producer(self):
        """Should use 'unknown' when producer is not in context."""
        ctx = {"correlation_id": "corr-123"}
        result = make_idempotency_key(ctx, "update", "task", "task_01")
        assert result == "unknown:update:task:task_01:corr-123"

    def test_uses_unknown_for_missing_correlation_id(self):
        """Should use 'unknown' when correlation_id is not in context."""
        ctx = {"producer": "worker"}
        result = make_idempotency_key(ctx, "delete", "item", "item_99")
        assert result == "worker:delete:item:item_99:unknown"

    def test_uses_unknown_for_empty_context(self):
        """Should use 'unknown' for both when context is empty."""
        ctx = {}
        result = make_idempotency_key(ctx, "op", "type", "id")
        assert result == "unknown:op:type:id:unknown"

    def test_handles_special_characters_in_values(self):
        """Should handle special characters in provided values."""
        ctx = {"producer": "my-service", "correlation_id": "req:abc:123"}
        result = make_idempotency_key(ctx, "process", "order", "order_xyz")
        assert result == "my-service:process:order:order_xyz:req:abc:123"
