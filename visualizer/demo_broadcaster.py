"""
Standalone driver that replays a realistic Watchstander graph run over
the agent_core WebSocket broadcaster - no API key required. Useful for:

- Trying out the visualizer without wiring up a real graph invocation
- Recording a demo GIF/video
- Smoke-testing the visualizer's event handling

Run this, then open visualizer/ in Godot 4 and run the main scene
(or run it headless - see README.md in this folder).

Session 10 (ADR-049): the data is the notional carrier dataset
(case_data/carrier_notional_v1.json), invented end to end per AGENTS.md
rule 6. The real-ship demo data this used before was
deleted. The deconfliction_result payload below lists exactly the
conflicts the real deconfliction finds on that dataset;
tests/test_session10.py checks the two still match.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_core import events  # noqa: E402
from agent_core.carrier_demo import load_carrier_dataset  # noqa: E402

# Flattened from the same WorkPackageState objects the reviewer's demo runs
# through the real graph, into the raw event-payload dict shape this script sends.
WORK_PACKAGES = [
    {
        "work_package_id": wp.work_package_id,
        "hazard_categories": [h.value if hasattr(h, "value") else h for h in wp.hazard_categories],
        "compartment_id": wp.spatial.compartment_id,
        "deck_level": wp.spatial.deck_level,
        "frame_start": wp.spatial.frame_start,
        "frame_end": wp.spatial.frame_end,
        "is_aloft": wp.spatial.is_aloft,
        "is_over_side": wp.spatial.is_over_side,
    }
    for wp in load_carrier_dataset().packages
]

SCRIPT = [
    ("deconfliction_start", {"work_packages": WORK_PACKAGES}),
    (
        "deconfliction_result",
        {
            "conflicts": [
                {"work_package_id": "HW-101", "conflicts_with": ["CS-102"],
                 "hazard_categories": ["hot_work", "confined_space"]},
                {"work_package_id": "CS-102", "conflicts_with": ["HW-101"],
                 "hazard_categories": ["confined_space", "hot_work"]},
                {"work_package_id": "ALOFT-105", "conflicts_with": ["DECK-106"],
                 "hazard_categories": ["working_aloft"]},
                {"work_package_id": "DECK-106", "conflicts_with": ["ALOFT-105"],
                 "hazard_categories": []},
            ]
        },
    ),
    ("reasoning_start", {"work_package_ids": ["HW-101", "CS-102", "ALOFT-105", "DECK-106"]}),
    (
        "reasoning_result",
        {
            "briefs": [
                {"work_package_id": "HW-101", "provenance": "[SOURCE: DETERMINISTIC FALLBACK - LLM OFFLINE]"},
                {"work_package_id": "CS-102", "provenance": "[SOURCE: DETERMINISTIC FALLBACK - LLM OFFLINE]"},
                {"work_package_id": "ALOFT-105", "provenance": "[SOURCE: DETERMINISTIC FALLBACK - LLM OFFLINE]"},
                {"work_package_id": "DECK-106", "provenance": "[SOURCE: DETERMINISTIC FALLBACK - LLM OFFLINE]"},
            ]
        },
    ),
    (
        "hitl_awaiting",
        {
            "work_package_id": "HW-101",
            "hazard_categories": ["hot_work"],
            "risk_level": "high",
            "safety_brief_provenance": "[SOURCE: DETERMINISTIC FALLBACK - LLM OFFLINE]",
        },
    ),
    (
        "hitl_decided",
        # Matches the real hitl_gate_single_node payload shape (see agent_core/hitl.py):
        # the parsed, structural disposition -- never the reviewer's raw free-text
        # answer, which stays off the wire per events.py's own broadcast policy.
        {"work_package_id": "HW-101", "disposition": "rejected", "cleared_for_execution": False},
    ),
]


CONNECT_TIMEOUT_SECONDS = 30.0
POLL_INTERVAL_SECONDS = 0.2


def _wait_for_a_client(broadcaster: "events.EventBroadcaster", timeout: float) -> bool:
    """
    Block until at least one WebSocket client (the visualizer) is actually
    connected, or the timeout elapses. Replaces a blind `time.sleep(3)` --
    that fixed wait assumed the visualizer would always connect within 3
    seconds of the server starting, which silently breaks the moment a
    human is switching windows/apps in between (a real report: a
    broadcaster run finished and its daemon-thread server died *before*
    the Godot editor was even open) -- broadcasting into an empty
    `_clients` set is a silent no-op (see EventBroadcaster.emit), so the
    whole demo would replay into the void with no error and no visual
    sign anything was wrong, indistinguishable from the ADR-026
    connectivity bug this project already hit once.
    """
    waited = 0.0
    while waited < timeout:
        if broadcaster._clients:
            return True
        time.sleep(POLL_INTERVAL_SECONDS)
        waited += POLL_INTERVAL_SECONDS
    return False


def main() -> None:
    broadcaster = events.get_broadcaster()
    broadcaster.start()
    print("Waiting for the visualizer to connect on ws://127.0.0.1:8081 ...")
    print("(open visualizer/ in Godot and run Main.tscn now, if it isn't already running)")
    if not _wait_for_a_client(broadcaster, CONNECT_TIMEOUT_SECONDS):
        print(
            "No visualizer connected within %.0f seconds -- broadcasting anyway, but "
            "nothing will be visible until one connects (this is a silent no-op, not an "
            "error, by design)." % CONNECT_TIMEOUT_SECONDS
        )
    else:
        print("Visualizer connected.")

    print("Replaying demo sequence.")
    for event_type, payload in SCRIPT:
        broadcaster.emit(event_type, **payload)
        # Paced to match the visualizer's minimum bubble read time (3s floor)
        # so a human watching the demo - or the recorded GIF - can actually
        # read each one before it's replaced.
        time.sleep(3.2)
    print("Done replaying. Server stays up -- press Ctrl+C to exit, or Enter to replay again.")

    # The server runs on a daemon thread (agent_core/events.py) -- once this
    # process's main thread exits, that thread is killed immediately,
    # closing the WebSocket server out from under a still-open visualizer.
    # Staying alive here (instead of returning right after the last emit)
    # means a slow window-switch, a paused demo, or just wanting to look at
    # the final state longer never costs the connection.
    try:
        while True:
            input()
            print("Replaying demo sequence.")
            for event_type, payload in SCRIPT:
                broadcaster.emit(event_type, **payload)
                time.sleep(3.2)
            print("Done replaying. Press Enter to replay again, or Ctrl+C to exit.")
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")


if __name__ == "__main__":
    main()
