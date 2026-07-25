"""
Standalone driver that replays a realistic Watchstander graph run over
the agent_core WebSocket broadcaster - no API key required. Useful for:

- Trying out the visualizer without wiring up a real graph invocation
- Recording a demo GIF/video
- Smoke-testing the visualizer's event handling

Run this, then open visualizer/ in Godot 4 and run the main scene
(or run it headless - see README.md in this folder).

The scripted work packages below are illustrative, not drawn from the
real cases in case_data/ - they exist to exercise the deconfliction ->
reasoning -> HITL pipeline end to end for the demo.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_core import events  # noqa: E402

WORK_PACKAGES = [
    {
        "work_package_id": "HW-2201",
        "hazard_categories": ["hot_work"],
        "frame_start": 80,
        "frame_end": 96,
        "deck_level": "2nd Deck",
        "is_aloft": False,
        "is_over_side": False,
    },
    {
        "work_package_id": "CS-2202",
        "hazard_categories": ["confined_space"],
        "frame_start": 84,
        "frame_end": 92,
        "deck_level": "2nd Deck",
        "is_aloft": False,
        "is_over_side": False,
    },
    {
        "work_package_id": "ALOFT-2203",
        "hazard_categories": ["working_aloft"],
        "frame_start": 60,
        "frame_end": 78,
        "deck_level": "Main Deck",
        "is_aloft": True,
        "is_over_side": False,
    },
    {
        "work_package_id": "FALL-2204",
        "hazard_categories": ["fall_protection"],
        "frame_start": 140,
        "frame_end": 156,
        "deck_level": "3rd Deck",
        "is_aloft": False,
        "is_over_side": False,
    },
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
        # Matches the real hitl_gate_node payload shape (see agent_core/hitl.py):
        # the parsed, structural disposition -- never the reviewer's raw free-text
        # answer, which stays off the wire per events.py's own broadcast policy.
        {"work_package_id": "HW-2201", "disposition": "rejected", "cleared_for_execution": False},
    ),
]


def main() -> None:
    broadcaster = events.get_broadcaster()
    broadcaster.start()
    print("Waiting for the visualizer to connect on ws://localhost:8081 ...")
    time.sleep(3)
    print("Replaying demo sequence.")
    for event_type, payload in SCRIPT:
        broadcaster.emit(event_type, **payload)
        # Paced to match the visualizer's minimum bubble read time (3s floor)
        # so a human watching the demo - or the recorded GIF - can actually
        # read each one before it's replaced.
        time.sleep(3.2)
    print("Done.")


if __name__ == "__main__":
    main()
