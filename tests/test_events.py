from agent_core.events import EventBroadcaster, emit


def test_emit_with_no_listeners_does_not_raise():
    # No visualizer attached - should be a silent no-op, never block or raise.
    emit("deconfliction_result", conflicts=[])


def test_broadcaster_start_is_idempotent():
    b = EventBroadcaster(host="localhost", port=0)
    b.start()
    b.start()  # second call should not spawn a second thread or raise
    assert b._thread is not None
