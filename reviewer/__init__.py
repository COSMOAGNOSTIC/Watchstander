"""
Real HITL reviewer web app -- the human-facing counterpart to the
Godot visualizer, which deliberately never shows why a package was
flagged (see agent_core/events.py's broadcast policy). This package
runs the real graph, persists real interrupt() state across HTTP
requests via a local SqliteSaver, and lets a human actually approve or
reject a flagged work package -- not simulate it.

See reviewer/README.md for how to run it and ARCHITECTURE.md ADR-024
for the design decision.
"""
