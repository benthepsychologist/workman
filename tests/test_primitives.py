def test_generate_id_prefix():
    from workman.ids import generate_id

    value = generate_id("proj")
    assert value.startswith("proj_")
    assert len(value) > 10


def test_make_idempotency_key():
    from workman.ids import make_idempotency_key

    ctx = {"producer": "life", "correlation_id": "c1"}
    key = make_idempotency_key(ctx, "pm.project.create", "project", "proj_123")
    assert key == "life:pm.project.create:project:proj_123:c1"


def test_assertion_ids_increment():
    from workman.assertions import assert_exists, reset_assertion_counter

    reset_assertion_counter()
    a1 = assert_exists("project", "proj_1")
    a2 = assert_exists("project", "proj_2")
    assert a1["id"] == "a1"
    assert a2["id"] == "a2"


def test_write_ids_increment():
    from workman.builders import build_wal_append, reset_write_counter

    reset_write_counter()
    ctx = {"producer": "life", "correlation_id": "c1", "actor": {"id": "u1"}}

    w1 = build_wal_append(
        idempotency_key="k1",
        event_type="project.created",
        aggregate_type="project",
        aggregate_id="proj_1",
        payload={"project_id": "proj_1"},
        ctx=ctx,
    )
    w2 = build_wal_append(
        idempotency_key="k2",
        event_type="project.created",
        aggregate_type="project",
        aggregate_id="proj_2",
        payload={"project_id": "proj_2"},
        ctx=ctx,
    )

    assert w1["id"] == "w1"
    assert w2["id"] == "w2"


def test_catalog_has_pm_ops():
    from workman.catalog import get_op_spec

    spec = get_op_spec("pm.project.create")
    assert spec is not None
    assert spec.id_field == "project_id"
    assert spec.is_create is True
