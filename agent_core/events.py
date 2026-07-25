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


class EventBroadcaster:
    """
    Singleton-ish broadcaster. One instance per process, started lazily on
    first emit() so importing agent_core never opens a socket by itself.
    """

    def __init__(self, host: str = "localhost", port: int = 8081):
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
        message = json.dumps({"type": event_type, "ts": time.time(), **payload})

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
