import json

from agent_core.events import SCHEMA_VERSION, EventBroadcaster, build_message, emit


def test_emit_with_no_listeners_does_not_raise():
    # No visualizer attached - should be a silent no-op, never block or raise.
    emit("deconfliction_result", conflicts=[])


def test_broadcaster_start_is_idempotent():
    b = EventBroadcaster(host="127.0.0.1", port=0)
    b.start()
    b.start()  # second call should not spawn a second thread or raise
    assert b._thread is not None


def test_default_host_is_the_literal_loopback_address_not_a_hostname():
    """
    Regression test for ADR-026: "localhost" is a DNS name, not an
    address. On a dual-stack machine it can resolve to a different
    address family on the Python server side than on the Godot client
    side, so both sockets open successfully and neither errors, but no
    data ever crosses -- a real bug Donnie hit running the visualizer on
    Windows, where "nothing happens" gave no error to chase. Binding to
    the literal loopback address by default removes the ambiguity.
    """
    b = EventBroadcaster()
    assert b.host == "127.0.0.1"


def test_build_message_includes_schema_version():
    """
    Every broadcast event previously went out with no version marker at
    all -- a consumer had no way to detect a breaking payload-shape change
    short of a runtime KeyError. Regression test for the fix.
    """
    raw = build_message("hitl_awaiting", 1234.5, work_package_id="WP-A")
    decoded = json.loads(raw)
    assert decoded["schema_version"] == SCHEMA_VERSION
    assert decoded["type"] == "hitl_awaiting"
    assert decoded["work_package_id"] == "WP-A"


def test_build_message_schema_version_wins_over_caller_supplied_key():
    """
    `schema_version` is a broadcaster-owned field. Regression test: an
    emit() call site that happens to pass a payload key of the same name
    must not be able to override the real value.
    """
    raw = build_message("hitl_awaiting", 1234.5, schema_version="not-a-real-version")
    decoded = json.loads(raw)
    assert decoded["schema_version"] == SCHEMA_VERSION
