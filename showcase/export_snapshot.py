"""
Export one run of the real deterministic checks over the notional carrier as JSON,
for the showcase page (Session 12). The page only draws what this file contains;
nothing on it is typed in by hand.

    python -m showcase.export_snapshot            # writes showcase/carrier_snapshot.json
    python -m showcase.build_mockup               # inlines it into showcase/mockup.html

Same functions the graph's nodes and the daily brief call (agent_core.daily_brief.run_checks).
No LLM. Nothing is applied or approved.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from agent_core import daily_brief, named_rules
from agent_core.carrier_demo import load_carrier_dataset
from agent_core.projects import PackageStatus

OUT = Path(__file__).resolve().parent / "carrier_snapshot.json"
AS_OF = datetime(2027, 3, 15, 6, 0)


def _iso(t):
    return t.isoformat() if t is not None else None


def _rule(rid: str) -> dict:
    r = named_rules.get_rule(rid)
    return {"id": rid, "title": r.title, "contact": r.contact_role,
            "category": r.category.value if hasattr(r.category, "value") else str(r.category),
            "citations": [{"source": c.source, "verified": c.verified} for c in r.citations]}


def snapshot(as_of: datetime = AS_OF) -> dict:
    ds = load_carrier_dataset()
    run = daily_brief.run_checks(ds, as_of)
    status = run.status_by_package()
    rules = run.rules_by_package()
    pkgs = []
    for p in run.packages:
        pid = p.work_package_id
        out = run.shift_outcomes.get(pid)
        sugg = None
        if out is not None:
            s = out.suggestion
            sugg = {
                "available": s is not None,
                "crew": s.crew_id if s else None,
                "from_shift": s.from_shift_id if s else None,
                "to_shift": s.to_shift_id if s else None,
                "moves": [{"id": m.work_package_id, "start": _iso(m.suggested_start), "end": _iso(m.suggested_end)}
                          for m in s.moves] if s else [],
                "reason": out.reason,
                "rejected": [{"shift": r.shift_id, "rules": list(r.rule_ids), "reasons": list(r.reasons)}
                             for r in out.rejected],
            }
        pkgs.append({
            "id": pid, "description": p.description,
            "hazards": [str(getattr(h, "value", h)) for h in p.hazard_categories],
            "compartment": p.spatial.compartment_id, "deck": p.spatial.deck_level,
            "frame_start": p.spatial.frame_start, "frame_end": p.spatial.frame_end,
            "aloft": p.spatial.is_aloft,
            "start": _iso(p.scheduled_start), "end": _iso(p.scheduled_end),
            "crew": p.crew_id, "locked": p.locked, "lock_reason": p.lock_reason,
            "status": status[pid].value,
            "rules": [_rule(r) for r in sorted(rules[pid])],
            "why": [n.strip() for n in (p.conflict_rationale or "").split(" | ") if n.strip()],
            "conflicts": list(p.conflicts),
            "suggestion": sugg,
        })
    names = {pr.project_id: pr.name for pr in ds.projects}
    return {
        "generated_by": "showcase/export_snapshot.py (agent_core.daily_brief.run_checks; no LLM)",
        "notional": True,
        "site": ds.site,
        "as_of": _iso(as_of),
        "shifts": [{"id": s.shift_id, "name": s.name, "start": _iso(s.start), "end": _iso(s.end)}
                   for s in ds.calendar.shifts],
        "crews": [{"id": c.crew_id, "name": c.name, "contractor": c.is_contractor,
                   "windows": [{"start": _iso(w.start), "end": _iso(w.end)} for w in c.contractor_windows]}
                  for c in ds.crews],
        "packages": pkgs,
        "judgment_flags": [{"rule": f.rule_id, "packages": f.work_package_ids, "reason": f.reason,
                            "person": f.routed_to.display_name, "role": f.routed_to.role,
                            "person_id": f.routed_to.person_id} for f in run.judgment_flags],
        "certificate_findings": [{"rule": f.rule_id, "package": f.work_package_id, "message": f.message}
                                 for f in run.certificate_findings],
        "schedule_findings": [{"rule": f.rule_id, "packages": f.work_package_ids, "message": f.message}
                              for f in run.schedule_findings],
        "projects": [{"id": r.project_id, "name": names[r.project_id], "priority": r.priority.value,
                      "due": _iso(r.due_date), "status": r.overall_status.value,
                      "counts": {k.value: v for k, v in r.status_counts.items() if v},
                      "late": r.late_package_ids, "past_due": r.past_due} for r in run.rollups],
        "cleared": [p["id"] for p in pkgs if p["status"] == PackageStatus.CLEARED.value],
        "brief_text": daily_brief.render(ds, as_of=as_of),
    }


def main() -> None:
    OUT.write_text(json.dumps(snapshot(), indent=1, sort_keys=False) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
