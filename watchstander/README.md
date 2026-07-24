# watchstander

[![tests](https://github.com/COSMOAGNOSTIC/watchstander/actions/workflows/tests.yml/badge.svg)](https://github.com/COSMOAGNOSTIC/watchstander/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A LangGraph-based multi-agent system for **OSHA 1915 (Shipyard Employment)** spatial and temporal safety deconfliction. Built by a 26-year Navy watchstander — this agent graph stands watch over shipyard safety the same way sailors stand watch over their ship.

## What it does

Shipyard work packages (jobs, permits, tasks) carry spatial metadata — compartment, frame range, deck level, whether the work is aloft or over-the-side. The **Spatial Deconfliction Agent** evaluates concurrent work packages for hazardous overlap — hot work near an uncleared confined space, aloft work directly above unprotected personnel — and routes anything flagged to a mandatory **Human-in-the-Loop safety gate** before it can proceed.

Case grounding is sourced entirely from public OSHA/DOL records — real shipyard incidents, not synthetic examples. See `case_data/cases_v1.json` and `PASSDOWN.md` for sourcing detail and scope notes.

## Architecture

```
entry -> deconfliction_node -> hitl_gate_node -> END
```

- **`agent_core/state.py`** — `WorkPackageState` schema: hazard categories, spatial coordinates, required permits, risk level.
- **`agent_core/deconfliction.py`** — deterministic, testable overlap detection between work packages. Geometry-based, not LLM-dependent, so conflicts are auditable and repeatable.
- **`agent_core/hitl.py`** — LangGraph `interrupt()`-based human review gate. Genuinely pauses graph execution; does not simulate review.
- **`agent_core/graph.py`** — graph assembly.
- **`case_data/`** — sourced OSHA/DOL case histories, tagged by hazard category, used to ground future rationale-generation passes.

## Installation

```bash
pip install -e ".[dev]"
```

## Testing

```bash
pytest -v
```

GitHub Actions runs the full suite on Python 3.11 and 3.12 for every push and pull request.

## Scope (v1)

Public-domain, civilian shipyard OSHA data only. No Navy mishap data — deliberately excluded to avoid classification/aggregation concerns, not an oversight. See `PASSDOWN.md` Section 7 for the full out-of-scope list.

## License

MIT — see [LICENSE](LICENSE).
