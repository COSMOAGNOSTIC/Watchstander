"""
Lightweight event broadcaster used to drive the live 2D spatial visualizer
(see visualizer/). Runs a tiny WebSocket server on a background thread and
broadcasts JSON events as the graph moves through deconfliction, reasoning,
and the HITL gate.

Ported from cosmoai-adept's agent_core/events.py (COSMOAGNOSTIC org) —
same design, same guarantees:

- Zero impact when no visualizer is attached (server just sits idle).
- Never raises into the graph - a broadcast failure is swallowed.
- No external event-loop coupling - graph.py stays synchronous.

Never broadcasts full work-package descriptions, case text, or safety-brief
prose - only ids, hazard categories, conflict flags, and provenance tags.
See ARCHITECTURE.md Section 8.

Runs on a different port (8081) than cosmoai-adept's broadcaster (8080) so
both can run side by side on the same machine without colliding.
"""
import json
import threading
import time
from typing import Any

try:
    import asyncio
    import websockets
    _HAS_WEBSOCKETS = True
except ImportError:  # pragma: no cover - optional dependency
    _HAS_WEBSOCKETS = False

# Bump when the *shape* of broadcast payloads changes in a way a consumer
# (the visualizer, a future non-Godot client) would need to branch on --
# new required keys, renamed keys, changed value types. Adding an
# additional optional key to one event's payload is not by itself a
# reason to bump this. Previously every event went out with no version
# marker at all, so a consumer had no way to detect a breaking payload
# change short of a runtime KeyError.
SCHEMA_VERSION = 1


def build_message(event_type: str, ts: float, **payload: Any) -> str:
    """
    Pure message-construction, split out of `EventBroadcaster.emit` so the
    JSON shape (including `schema_version`) is unit-testable without
    standing up a real WebSocket client -- `emit()` itself only runs the
    send path when at least one client is connected, which made the
    payload shape untestable in isolation before this split.

    `schema_version` is placed after `**payload` so it always wins over an
    accidental caller-supplied key of the same name.
    """
    return json.dumps({"type": event_type, "ts": ts, **payload, "schema_version": SCHEMA_VERSION})


class EventBroadcaster:
    """
    Singleton-ish broadcaster. One instance per process, started lazily on
    first emit() so importing agent_core never opens a socket by itself.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8081):
        # "localhost" is a DNS name, not an address -- on a dual-stack
        # machine (very common on Windows) it can resolve to the IPv6
        # loopback (::1) for the server side and the IPv4 loopback
        # (127.0.0.1) for the client side (or vice versa), depending on
        # resolver order, and the two sides then never actually reach
        # each other: the server socket exists, the client socket exists,
        # neither errors, and no data ever crosses. Binding to the literal
        # loopback address removes that ambiguity. See visualizer/Main.gd
        # and ARCHITECTURE.md ADR-026 for the client-side half of this fix.
        self.host = host
        self.port = port
        self._clients: set = set()
        self._loop: "asyncio.AbstractEventLoop | None" = None
        self._thread: threading.Thread | None = None
        self._started = threading.Event()

    def start(self) -> None:
        if not _HAS_WEBSOCKETS or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._started.wait(timeout=2)

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        async def handler(websocket):
            self._clients.add(websocket)
            try:
                await websocket.wait_closed()
            finally:
                self._clients.discard(websocket)

        async def main():
            try:
                async with websockets.serve(handler, self.host, self.port):
                    self._started.set()
                    await asyncio.Future()  # run forever
            except OSError:
                # Port already in use (e.g. another process owns it) -
                # visualizer will just connect to that one instead.
                self._started.set()

        try:
            self._loop.run_until_complete(main())
        except Exception:
            self._started.set()

    def emit(self, event_type: str, **payload: Any) -> None:
        """Fire-and-forget broadcast. Safe to call with no listeners."""
        if not _HAS_WEBSOCKETS:
            return
        self.start()
        if self._loop is None or not self._clients:
            return
        message = build_message(event_type, time.time(), **payload)

        async def _send():
            dead = []
            for ws in list(self._clients):
                try:
                    await ws.send(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._clients.discard(ws)

        try:
            asyncio.run_coroutine_threadsafe(_send(), self._loop)
        except Exception:
            pass


_broadcaster: EventBroadcaster | None = None


def get_broadcaster() -> EventBroadcaster:
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = EventBroadcaster()
    return _broadcaster


def emit(event_type: str, **payload: Any) -> None:
    """Module-level convenience: agent_core.events.emit('deconfliction_result', ...)."""
    get_broadcaster().emit(event_type, **payload)
