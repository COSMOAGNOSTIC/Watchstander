"""
Standalone driver that replays a realistic Watchstander graph run over
the agent_core WebSocket broadcaster - no API key required. Useful for:

- Trying out the visualizer without wiring up a real graph invocation
- Recording a demo GIF/video
- Smoke-testing the visualizer's event handling

Run this, then open visualizer/ in Godot 4 and run the main scene
(or run it headless - see README.md in this folder).

Compartment names, deck levels, AND frame ranges below are real, read
directly off USCG Cutter ACUSHNET / ex-USS SHACKLE (ARS-9)'s HAER
(Historic American Engineering Record) drawing, Sheet 5 of 10 ("Deck
Plans") -- Library of Congress HABS/AK-49, public domain (HABS/HAER/HALS
documentation is "available to the public without restriction" per
NPS). Not from case_data/ -- this is illustrative demo staging, not a
sourced incident or a real work order. Full sourcing detail, including
the frame-range estimation caveat (~+/-2-3 frames, read from tick-mark
proximity, not digitized coordinates) and the standard-frame-spacing
assumption used to interpret them, is in
docs/uscg-acushnet-ars9-source.md -- this supersedes the earlier Turner
Joy source (docs/uss-turner-joy-dd951-source.md, kept for history),
which had real compartment names but no printed frame numbers at all.

Spatial linkage for the flagged pair below comes from the shared
compartment_id ("Electric & Machine Shop (B-2)"), which
deconfliction._same_compartment() supports independently of frame
ranges -- the frame numbers additionally place both packages in a
genuinely overlapping span this time, not just the same named space.
ACUSHNET is an active Coast Guard cutter, not a Navy shipyard work site
-- governing_installation is deliberately left unset here, since
tagging her "PSNS" would misrepresent where she actually is.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_core import events  # noqa: E402
from agent_core.demo_fixtures import acushnet_demo_work_packages  # noqa: E402

# Flattened from the same real WorkPackageState objects reviewer/ runs
# through the actual graph (agent_core/demo_fixtures.py) into the raw
# event-payload dict shape this scripted sequence broadcasts -- one
# source of truth for the ACUSHNET compartment/frame data, so this demo
# path and the real-graph reviewer demo path can't quietly drift apart.
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
    for wp in acushnet_demo_work_packages()
]

SCRIPT = [
    ("deconfliction_start", {"work_packages": WORK_PACKAGES}),
    (
        "deconfliction_result",
        {
            "conflicts": [
                {
                    "work_package_id": "HW-2201",
                    "conflicts_with": ["CS-2202"],
                    "hazard_categories": ["hot_work", "confined_space"],
                },
                {
                    "work_package_id": "CS-2202",
                    "conflicts_with": ["HW-2201"],
                    "hazard_categories": ["confined_space", "hot_work"],
                },
            ]
        },
    ),
    ("reasoning_start", {"work_package_ids": ["HW-2201", "CS-2202"]}),
    (
        "reasoning_result",
        {
            "briefs": [
                {"work_package_id": "HW-2201", "provenance": "[SOURCE: DETERMINISTIC FALLBACK - LLM OFFLINE]"},
                {"work_package_id": "CS-2202", "provenance": "[SOURCE: DETERMINISTIC FALLBACK - LLM OFFLINE]"},
            ]
        },
    ),
    (
        "hitl_awaiting",
        {
            "work_package_id": "HW-2201",
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
        {"work_package_id": "HW-2201", "disposition": "rejected", "cleared_for_execution": False},
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
