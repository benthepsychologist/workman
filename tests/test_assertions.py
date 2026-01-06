"""Tests for workman.assertions module."""

from workman.assertions import (
    assert_exists,
    assert_not_exists,
    reset_assertion_counter,
)


class TestAssertExists:
    """Tests for assert_exists function."""

    def setup_method(self):
        """Reset counter before each test."""
        reset_assertion_counter()

    def test_returns_jsonrpc_2_0(self):
        """Should return jsonrpc version 2.0."""
        result = assert_exists("work_item", "wi_01ARZ")
        assert result["jsonrpc"] == "2.0"

    def test_returns_method_assert_exists(self):
        """Should return method 'assert.exists'."""
        result = assert_exists("work_item", "wi_01ARZ")
        assert result["method"] == "assert.exists"

    def test_returns_params_with_aggregate_type_and_id(self):
        """Should return params with aggregate_type and aggregate_id."""
        result = assert_exists("work_item", "wi_01ARZ")
        assert result["params"] == {
            "aggregate_type": "work_item",
            "aggregate_id": "wi_01ARZ",
        }

    def test_returns_unique_id_starting_with_a(self):
        """Should return id starting with 'a' followed by number."""
        result = assert_exists("work_item", "wi_01ARZ")
        assert result["id"].startswith("a")
        assert result["id"][1:].isdigit()

    def test_returns_sequential_ids(self):
        """Should return sequential ids a1, a2, a3, etc."""
        result1 = assert_exists("type1", "id1")
        result2 = assert_exists("type2", "id2")
        result3 = assert_exists("type3", "id3")
        assert result1["id"] == "a1"
        assert result2["id"] == "a2"
        assert result3["id"] == "a3"


class TestAssertNotExists:
    """Tests for assert_not_exists function."""

    def setup_method(self):
        """Reset counter before each test."""
        reset_assertion_counter()

    def test_returns_jsonrpc_2_0(self):
        """Should return jsonrpc version 2.0."""
        result = assert_not_exists("work_item", "wi_01ARZ")
        assert result["jsonrpc"] == "2.0"

    def test_returns_method_assert_not_exists(self):
        """Should return method 'assert.not_exists'."""
        result = assert_not_exists("work_item", "wi_01ARZ")
        assert result["method"] == "assert.not_exists"

    def test_returns_params_with_aggregate_type_and_id(self):
        """Should return params with aggregate_type and aggregate_id."""
        result = assert_not_exists("work_item", "wi_01ARZ")
        assert result["params"] == {
            "aggregate_type": "work_item",
            "aggregate_id": "wi_01ARZ",
        }

    def test_returns_unique_id_starting_with_a(self):
        """Should return id starting with 'a' followed by number."""
        result = assert_not_exists("work_item", "wi_01ARZ")
        assert result["id"].startswith("a")
        assert result["id"][1:].isdigit()

    def test_returns_sequential_ids(self):
        """Should return sequential ids a1, a2, a3, etc."""
        result1 = assert_not_exists("type1", "id1")
        result2 = assert_not_exists("type2", "id2")
        result3 = assert_not_exists("type3", "id3")
        assert result1["id"] == "a1"
        assert result2["id"] == "a2"
        assert result3["id"] == "a3"


class TestAssertionIdCounter:
    """Tests for shared assertion ID counter."""

    def setup_method(self):
        """Reset counter before each test."""
        reset_assertion_counter()

    def test_both_functions_share_counter(self):
        """assert_exists and assert_not_exists should share the same counter."""
        result1 = assert_exists("type1", "id1")
        result2 = assert_not_exists("type2", "id2")
        result3 = assert_exists("type3", "id3")
        assert result1["id"] == "a1"
        assert result2["id"] == "a2"
        assert result3["id"] == "a3"

    def test_reset_counter_restarts_sequence(self):
        """reset_assertion_counter should restart the sequence from a1."""
        assert_exists("type1", "id1")
        assert_exists("type2", "id2")
        reset_assertion_counter()
        result = assert_exists("type3", "id3")
        assert result["id"] == "a1"
